import { expect, test, type Page } from '@playwright/test';
const id = (n: number) =>
  `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
function locker(
  n: number,
  label: string | null = `Locker ${n}`,
  coordinates: unknown = { latitude: 40.4168, longitude: -3.7038 },
) {
  return {
    id: id(n),
    location_id: label,
    active: true,
    address: null,
    coordinates,
    compartments: [{ enabled: true, occupied: false }],
  };
}
async function tiles(page: Page, fail = false) {
  await page.route('https://tile.openstreetmap.org/**', (route) =>
    fail
      ? route.abort()
      : route.fulfill({
          contentType: 'image/png',
          body: Buffer.from(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aG1kAAAAASUVORK5CYII=',
            'base64',
          ),
        }),
  );
}
async function data(page: Page, payload: unknown, open = true) {
  await tiles(page);
  await page.route('http://127.0.0.1:8765/lockers', (route) =>
    route.fulfill({ json: payload }),
  );
  await page.goto('/');
  if (open) await openPanel(page);
}
async function openPanel(page: Page) {
  await page.locator('#skip-results').focus();
  await page.keyboard.press('Enter');
}
const photon = 'https://photon.komoot.io/**';
function place(
  label = 'Madrid',
  longitude = -3.7038,
  latitude = 40.4168,
  countrycode = 'ES',
) {
  return {
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [longitude, latitude] },
    properties: { name: label, countrycode },
  };
}
const places = (...features: unknown[]) => ({
  type: 'FeatureCollection',
  features,
});
async function markerHit(page: Page) {
  return page.locator('.search-location').evaluate((node) => {
    const box = node.getBoundingClientRect();
    return (
      document
        .elementFromPoint(box.x + box.width / 2, box.y + box.height / 2)
        ?.closest('.search-location') === node
    );
  });
}

for (const viewport of [
  { width: 1280, height: 800, name: 'desktop' },
  { width: 375, height: 480, name: 'mobile-short' },
]) {
  test(`one compact menu and selectable autocomplete ${viewport.name}`, async ({
    page,
  }) => {
    await page.setViewportSize({
      width: viewport.width,
      height: viewport.height,
    });
    let lockerReads = 0;
    let geoReads = 0;
    let queryUrl: URL | null = null;
    await tiles(page);
    await page.route('http://127.0.0.1:8765/lockers', (route) => {
      lockerReads++;
      return route.fulfill({ json: [locker(1)] });
    });
    await page.route(photon, (route) => {
      geoReads++;
      queryUrl = new URL(route.request().url());
      return route.fulfill({
        json: places(place('01001 Vitoria', -2.6727, 42.8467)),
      });
    });
    await page.goto('/');
    await expect(page.locator('#available-count')).toHaveText('1');
    await expect(page.locator('#map-panels .panel')).toHaveCount(1);
    expect(
      await page
        .locator('#quote-view')
        .evaluate((node) =>
          node.lastElementChild?.classList.contains('metrics'),
        ),
    ).toBe(true);
    await expect(
      page.getByRole('button', { name: 'Buscar', exact: true }),
    ).toHaveCount(0);
    await expect(page.locator('#search-provider, #parcel-note')).toHaveCount(0);
    expect(
      await page.locator('[aria-describedby]').evaluateAll((nodes) =>
        nodes.every((node) =>
          node
            .getAttribute('aria-describedby')!
            .split(/\s+/)
            .every((id) => document.getElementById(id)),
        ),
      ),
    ).toBe(true);
    await page.screenshot({
      path: `test-results/${viewport.name}-menu-closed.png`,
    });
    await page.getByRole('spinbutton', { name: 'Largo (cm)' }).fill('25.5');
    const query = page.getByRole('combobox', {
      name: 'Dirección de entrega',
    });
    const before = await page
      .locator('.leaflet-map-pane')
      .getAttribute('style');
    await query.fill(' 01001 ');
    expect(geoReads).toBe(0);
    await expect(page.locator('#delivery-results button')).toHaveCount(1);
    await expect(page.locator('.search-location')).toHaveCount(0);
    expect(await page.locator('.leaflet-map-pane').getAttribute('style')).toBe(
      before,
    );
    expect(queryUrl!.pathname).toBe('/structured');
    expect(queryUrl!.searchParams.get('postcode')).toBe('01001');
    expect(queryUrl!.searchParams.get('countrycode')).toBe('ES');
    expect(queryUrl!.searchParams.get('limit')).toBe('5');
    await expect(query).toHaveAttribute('aria-expanded', 'true');
    await page.screenshot({
      path: `test-results/${viewport.name}-menu-suggestions.png`,
    });
    await query.press('ArrowDown');
    await expect(
      page.locator('#delivery-results button').first(),
    ).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(query).toHaveValue('01001 Vitoria');
    await expect(query).toBeFocused();
    await expect(query).toHaveAttribute('aria-expanded', 'false');
    expect(
      await page
        .locator('#delivery-suggestions')
        .evaluate((node: HTMLElement) => node.inert),
    ).toBe(true);
    await expect(page.locator('#delivery-suggestions')).toBeHidden();
    expect(await markerHit(page)).toBe(true);
    await expect(page.locator('#results')).toBeHidden();
    await page.waitForTimeout(400);
    expect(geoReads).toBe(1);
    await page.screenshot({
      path: `test-results/${viewport.name}-menu-selected.png`,
    });
    await openPanel(page);
    await page.unroute(photon);
    await page.route(photon, (route) => {
      geoReads++;
      queryUrl = new URL(route.request().url());
      return route.fulfill({
        json: places(
          place('Plaza de España, Madrid'),
          place('Plaza Mayor, Madrid'),
          ...Array.from({ length: 5 }, (_, i) => place(`Plaza ${i}`)),
        ),
      });
    });
    await query.fill('Plaza');
    await expect(page.locator('#delivery-results button')).toHaveCount(5);
    await page.locator('#delivery-results button').nth(1).click();
    await expect(query).toHaveValue('Plaza Mayor, Madrid');
    await expect(page.locator('#delivery-suggestions')).toBeHidden();
    expect(await markerHit(page)).toBe(true);
    await expect(page.locator('#results')).toBeVisible();
    await expect(
      page.getByRole('spinbutton', { name: 'Largo (cm)' }),
    ).toHaveValue('25.5');
    expect(lockerReads).toBe(1);
    expect(geoReads).toBe(2);
    await page.screenshot({
      path: `test-results/${viewport.name}-menu-selected-list-open.png`,
    });
  });
}

test('autocomplete debounces edits, ignores short text and never duplicates Enter', async ({
  page,
}) => {
  await data(page, [locker(1)], false);
  let requests = 0;
  await page.route(photon, (route) => {
    requests++;
    return route.fulfill({ json: places(place('Madrid')) });
  });
  await page.clock.install();
  await page.clock.pauseAt(new Date(Date.now() + 100));
  const query = page.getByRole('combobox', {
    name: 'Dirección de entrega',
  });
  await query.fill('  ab ');
  await page.clock.fastForward(500);
  expect(requests).toBe(0);
  await query.fill('Mad');
  await page.clock.fastForward(200);
  await query.fill('Madrid');
  await query.press('Enter');
  await page.clock.fastForward(349);
  expect(requests).toBe(0);
  await page.clock.fastForward(1);
  await expect.poll(() => requests).toBe(1);
  await expect(page.locator('#delivery-results button')).toHaveCount(1);
  await query.press('Enter');
  await page.clock.fastForward(700);
  expect(requests).toBe(1);
  await expect(page.locator('.search-location')).toHaveCount(0);
  await page.clock.resume();
});

test('geographic errors, empty, malformed and timeout retain independent retry', async ({
  page,
}) => {
  await data(page, [locker(1)], false);
  let call = 0;
  await page.route(photon, (route) => {
    call++;
    if (call === 1) return route.fulfill({ status: 503, body: 'down' });
    if (call === 2)
      return route.fulfill({ json: places(place('France', 2, 48, 'FR')) });
    if (call === 3) return route.fulfill({ json: { invalid: true } });
    return route.fulfill({ json: places(place('Madrid')) });
  });
  const query = page.getByRole('combobox', {
    name: 'Dirección de entrega',
  });
  await query.fill('Madrid');
  await expect(page.locator('#delivery-status')).toContainText('HTTP 503');
  await expect(page.locator('#status')).toBeHidden();
  await expect(page.locator('#available-count')).toHaveText('1');
  await page.getByRole('button', { name: 'Reintentar búsqueda' }).click();
  await expect(page.locator('#delivery-status')).toContainText(
    'No se han encontrado',
  );
  await query.fill('Madrid centro');
  await expect(page.locator('#delivery-status')).toContainText(
    'respuesta no válida',
  );
  await page.getByRole('button', { name: 'Reintentar búsqueda' }).focus();
  await page.keyboard.press('Enter');
  await expect(
    page.getByRole('combobox', { name: 'Dirección de entrega' }),
  ).toBeFocused();
  await expect(page.locator('#delivery-results button')).toHaveCount(1);
  await page.locator('#delivery-results button').click();
  await page.unroute(photon);
  await page.route(photon, () => {});
  await query.fill('Tardará');
  await expect(page.locator('#delivery-status')).toContainText(
    'cinco segundos',
    {
      timeout: 7000,
    },
  );
  await expect(page.locator('#delivery-retry')).toBeVisible();
  await expect(page.locator('#available-count')).toHaveText('1');
  await expect(page.locator('#retry')).toBeHidden();
});

test('Escape, blur and later edits discard even a transport that ignores cancellation', async ({
  page,
}) => {
  await page.addInitScript(() => {
    const original = window.fetch;
    window.fetch = (input, init) => {
      if (
        String(input).includes('photon.komoot.io') &&
        new URL(String(input)).searchParams.get('q')?.startsWith('Anterior')
      ) {
        return new Promise((resolve) => {
          Reflect.set(window, 'completeOldSearch', () =>
            resolve(
              new Response(
                JSON.stringify({
                  type: 'FeatureCollection',
                  features: [
                    {
                      type: 'Feature',
                      geometry: { type: 'Point', coordinates: [2.65, 39.57] },
                      properties: { name: 'Anterior', countrycode: 'ES' },
                    },
                  ],
                }),
              ),
            ),
          );
        });
      }
      return original(input, init);
    };
  });
  await data(page, [locker(1)], false);
  await page.route(photon, (route) =>
    route.fulfill({ json: places(place('Última ubicación')) }),
  );
  const query = page.getByRole('combobox', {
    name: 'Dirección de entrega',
  });
  const before = await page.locator('.leaflet-map-pane').getAttribute('style');
  for (const [index, close] of ['escape', 'blur'].entries()) {
    await query.fill(`Anterior ${index}`);
    await expect(page.locator('#delivery-search')).toHaveAttribute(
      'aria-busy',
      'true',
    );
    if (close === 'escape') await query.press('Escape');
    else await page.getByRole('spinbutton', { name: 'Largo (cm)' }).focus();
    await page.evaluate(() => Reflect.get(window, 'completeOldSearch')());
    await expect(page.locator('#delivery-suggestions')).toBeHidden();
    await expect(query).toHaveAttribute('aria-expanded', 'false');
    expect(await page.locator('.leaflet-map-pane').getAttribute('style')).toBe(
      before,
    );
  }
  await query.fill('Anterior otra');
  await expect(page.locator('#delivery-search')).toHaveAttribute(
    'aria-busy',
    'true',
  );
  await query.fill('Última');
  await expect(page.locator('#delivery-results button')).toHaveText(
    'Última ubicación',
  );
  await page.evaluate(() => Reflect.get(window, 'completeOldSearch')());
  await expect(page.locator('#delivery-results button')).toHaveText(
    'Última ubicación',
  );
  await expect(page.locator('.search-location')).toHaveCount(0);
});

test('suggestion animation can be interrupted and closed options immediately lose focus access', async ({
  page,
}) => {
  await data(page, [locker(1)], false);
  await page.route(photon, (route) =>
    route.fulfill({
      json: places(place('Madrid centro'), place('Madrid norte')),
    }),
  );
  const query = page.getByRole('combobox', {
    name: 'Dirección de entrega',
  });
  await query.fill('Madrid');
  await expect(page.locator('#delivery-results button')).toHaveCount(2);
  await query.press('ArrowDown');
  await expect(page.locator('#delivery-results button').first()).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(query).toBeFocused();
  expect(
    await page
      .locator('#delivery-suggestions')
      .evaluate((node: HTMLElement) => node.inert),
  ).toBe(true);
  await page
    .locator('#delivery-results button')
    .first()
    .evaluate((node) => node.focus());
  await expect(query).toBeFocused();
  await query.press('Tab');
  await expect(
    page.getByRole('spinbutton', { name: 'Largo (cm)' }),
  ).toBeFocused();
  await query.fill('Madrid nuevo');
  await expect(page.locator('#delivery-results button')).toHaveCount(2);
  await expect(query).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('#delivery-suggestions')).toHaveCSS('opacity', '1');
  await expect(page.locator('#delivery-suggestions')).not.toHaveAttribute(
    'hidden',
  );
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(page.locator('#delivery-suggestions')).toHaveCSS(
    'transition-duration',
    '0s',
  );
  await query.press('Escape');
  expect(
    await page
      .locator('#delivery-suggestions')
      .evaluate((node: HTMLElement) => node.hidden && node.inert),
  ).toBe(true);
});

test('touching a suggestion selects before blur and does not trigger another search', async ({
  browser,
}) => {
  const context = await browser.newContext({
    baseURL: 'http://127.0.0.1:4321',
    viewport: { width: 375, height: 480 },
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();
  try {
    await data(page, [locker(1)], false);
    let requests = 0;
    await page.route(photon, (route) => {
      requests++;
      return route.fulfill({ json: places(place('Gran Vía, Madrid')) });
    });
    const query = page.getByRole('combobox', {
      name: 'Dirección de entrega',
    });
    await query.fill('Gran Vía');
    await expect(page.locator('#delivery-results button')).toHaveCount(1);
    await page.locator('#delivery-results button').tap();
    await expect(query).toHaveValue('Gran Vía, Madrid');
    await expect(query).toBeFocused();
    await expect(page.locator('#delivery-suggestions')).toBeHidden();
    expect(await markerHit(page)).toBe(true);
    await page.waitForTimeout(400);
    expect(requests).toBe(1);
  } finally {
    await context.close();
  }
});

test('duplicate suggestion labels retain the selected candidate coordinates', async ({
  page,
}) => {
  await data(page, [locker(1)], false);
  await page.route(photon, (route) =>
    route.fulfill({
      json: places(place('Centro', -3.7, 40.4), place('Centro', 2.65, 39.57)),
    }),
  );
  const query = page.getByRole('combobox', {
    name: 'Dirección de entrega',
  });
  await query.fill('Centro');
  await expect(page.locator('#delivery-results button')).toHaveCount(2);
  await page.locator('#delivery-results button').nth(1).click();
  await expect(query).toHaveValue('Centro');
  await expect(page.locator('#delivery-suggestions')).toBeHidden();
  expect(await markerHit(page)).toBe(true);
});
const address = {
  country_code: 'ES',
  postal_code: '01001',
  province: 'Álava',
  city: 'Vitoria',
  street: 'Calle Mayor',
  street_number: '2',
};
async function fillShipping(page: Page, manual = true) {
  for (const [id, value] of [
    ['length', '25.5'],
    ['width', '15'],
    ['height', '10'],
    ['weight', '1.001'],
  ])
    await page.locator(`#parcel-${id}`).fill(value!);
  await page.locator('#origin-postal').fill('28001');
  if (manual) await page.locator('#destination-postal').fill('01001');
}
const quoteId = id(101);
function quote(request: unknown, status = 'COMPLETED') {
  return {
    id: quoteId,
    request,
    status,
    created_at: '2026-10-17T12:00:00Z',
    finished_at: status === 'COMPLETED' ? '2026-10-17T12:00:02Z' : null,
    process_error_code: null,
    results:
      status === 'COMPLETED'
        ? [
            {
              provider_code: 'sim-economy',
              status: 'QUOTED',
              error_code: null,
              offers: [
                {
                  service_code: 'economy',
                  currency: 'EUR',
                  price_cents: 1234,
                  transit_days_min: 2,
                  transit_days_max: 4,
                },
              ],
            },
            {
              provider_code: 'sim-standard',
              status: 'NOT_COVERED',
              error_code: null,
              offers: [],
            },
            {
              provider_code: 'sim-express',
              status: 'FAILED',
              error_code: 'PROVIDER_TIMEOUT',
              offers: [],
            },
          ]
        : [],
  };
}
test('real cross-origin FastAPI completes POST/preflight and polling without interception', async ({
  page,
  context,
}) => {
  await tiles(page);
  const response = page.waitForResponse('http://127.0.0.1:8765/lockers');
  await page.goto('/');
  await expect(page.locator('#available-count')).toHaveText('1');
  expect((await response).headers()['access-control-allow-origin']).toBe(
    'http://127.0.0.1:4321',
  );
  await openPanel(page);
  await page.locator('#destination-locker').selectOption(id(1));
  await fillShipping(page, false);
  await expect(page.locator('#destination-postal')).toHaveValue('01001');
  const post = page.waitForResponse(
    (r) => r.request().method() === 'POST' && r.url().endsWith('/quotations'),
  );
  await page.locator('#compare-shipping').click();
  expect((await post).status()).toBe(202);
  await expect(page.locator('#quotation-status')).toContainText('finalizada');
  await expect(page.locator('#quotation-offers')).toContainText('12,34');
  await expect(page.locator('#quotation-offers')).toContainText(
    'Sin cobertura',
  );
  await expect(page.locator('#quotation-offers')).toContainText(
    'tiempo de respuesta',
  );
  const denied = await context.newPage();
  await tiles(denied);
  await denied.goto('http://localhost:4321/');
  await expect(denied.locator('#retry')).toBeVisible();
  await expect(denied.locator('#status')).toContainText('conectar');
});
for (const viewport of [
  { width: 1280, height: 800, name: 'desktop' },
  { width: 375, height: 480, name: 'mobile-short' },
]) {
  test(`destination form and simulated offers ${viewport.name}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    let reads = 0;
    let posts = 0;
    let submitted: any;
    let gets = 0;
    await tiles(page);
    await page.route('http://127.0.0.1:8765/lockers', (r) => {
      reads++;
      return r.fulfill({
        json: [
          { ...locker(1, 'Madrid'), address },
          locker(2, 'Sin coordenadas', null),
          locker(3, 'Madrid'),
        ],
      });
    });
    await page.route('http://127.0.0.1:8765/quotations', (r) => {
      posts++;
      submitted = r.request().postDataJSON();
      return r.fulfill({
        status: 202,
        json: { id: quoteId, status: 'PENDING' },
      });
    });
    await page.route(`http://127.0.0.1:8765/quotations/${quoteId}`, (r) => {
      gets++;
      return r.fulfill({
        json: quote(submitted, gets === 1 ? 'PENDING' : 'COMPLETED'),
      });
    });
    await page.goto('/');
    await expect(page.locator('#available-count')).toHaveText('3');
    await expect(page.locator('#results')).toBeHidden();
    await expect(page.locator('#status')).toBeHidden();
    await expect(
      page.getByRole('button', { name: 'Ver lockers', exact: true }),
    ).toHaveCount(0);
    await page.screenshot({
      path: `test-results/shipping-${viewport.name}-initial.png`,
    });
    await openPanel(page);
    await expect(page.locator('#destination-locker')).toBeFocused();
    await page.locator('#destination-locker').selectOption(id(2));
    await expect(page.locator('#destination-position')).toBeVisible();
    await expect(page.locator('#destination-postal-note')).toContainText(
      'no registrado',
    );
    await fillShipping(page);
    await page.screenshot({
      path: `test-results/shipping-${viewport.name}-form.png`,
    });
    await page.locator('#compare-shipping').click();
    await expect(page.locator('#quotation-status')).toContainText('finalizada');
    expect(posts).toBe(1);
    expect(reads).toBe(1);
    expect(gets).toBe(2);
    expect(submitted).toEqual({
      origin_country_code: 'ES',
      origin_postal_code: '28001',
      destination_country_code: 'ES',
      destination_postal_code: '01001',
      weight_grams: 1001,
      dimensions: { depth_mm: 255, width_mm: 150, height_mm: 100 },
    });
    await expect(page.locator('#quotation-offers')).toContainText('12,34');
    await expect(page.locator('.demo-note')).toContainText('simulados');
    await page.locator('.offer-card').first().scrollIntoViewIfNeeded();
    await page.screenshot({
      path: `test-results/shipping-${viewport.name}-offers.png`,
    });
    await page.locator('#destination-locker').selectOption(id(1));
    await expect(page.locator('#quotation-offers')).toBeEmpty();
    await expect(page.locator('#destination-postal')).toHaveValue('01001');
    await expect(page.locator('#destination-postal')).toHaveAttribute(
      'readonly',
      '',
    );
    await expect(page.locator('#origin-postal')).toHaveValue('28001');
    const marker = page.locator('.locker-marker[title="Madrid · 1"]');
    expect(
      await marker.evaluate((node) => {
        const r = node.getBoundingClientRect();
        return (
          document
            .elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)
            ?.closest('.locker-marker') === node
        );
      }),
    ).toBe(true);
    await page.locator('#destination-locker').focus();
    await page.keyboard.press('Escape');
    await expect(page.locator('#results')).toBeHidden();
    await expect(page.locator('#skip-results')).toBeFocused();
  });
}
test('destination selector preserves duplicates and literal unsafe text without exposing identifiers', async ({
  page,
}) => {
  await data(page, [
    locker(1, '<img src=x onerror=alert(1)>'),
    locker(2, 'Same', null),
    locker(3, 'Same', null),
  ]);
  await expect(page.locator('#destination-locker')).toContainText(
    '<img src=x onerror=alert(1)>',
  );
  await expect(page.locator('#destination-locker option')).toHaveCount(4);
  await page.locator('#destination-locker').selectOption(id(3));
  await expect(page.locator('#destination-locker option:checked')).toHaveText(
    'Same · 2',
  );
  await expect(page.locator('#results img')).toHaveCount(0);
  await expect(page.locator('#results')).not.toContainText(id(3));
});
test('invalid exact units focus field and prevent POST, destination change resets only manual postal', async ({
  page,
}) => {
  let posts = 0;
  await data(page, [locker(1), locker(2, null, null)]);
  await page.route('**/quotations', (r) => {
    posts++;
    return r.abort();
  });
  await page.locator('#destination-locker').selectOption(id(1));
  await fillShipping(page);
  await page.locator('#parcel-length').fill('1.01');
  await page.locator('#compare-shipping').click();
  await expect(page.locator('#parcel-length')).toBeFocused();
  await expect(page.locator('#parcel-length-error')).toContainText(
    'milímetros',
  );
  expect(posts).toBe(0);
  await page.locator('#destination-locker').selectOption(id(2));
  await expect(page.locator('#destination-postal')).toHaveValue('');
  await expect(page.locator('#origin-postal')).toHaveValue('28001');
  await expect(page.locator('#parcel-length')).toHaveValue('1.01');
});
test('GET failure resumes same reference without duplicate POST', async ({
  page,
}) => {
  let posts = 0;
  let reads = 0;
  let input: any;
  await data(page, [locker(1)]);
  await page.route('**/quotations', (r) => {
    posts++;
    input = r.request().postDataJSON();
    return r.fulfill({ status: 202, json: { id: quoteId, status: 'PENDING' } });
  });
  await page.route(`**/quotations/${quoteId}`, (r) => {
    reads++;
    return reads === 1
      ? r.fulfill({ status: 503, json: { detail: 'unavailable' } })
      : r.fulfill({ json: quote(input) });
  });
  await page.locator('#destination-locker').selectOption(id(1));
  await fillShipping(page);
  await page.locator('#compare-shipping').click();
  await expect(page.locator('#quotation-resume')).toBeVisible();
  await page.locator('#quotation-resume').click();
  await expect(page.locator('#quotation-status')).toContainText('finalizada');
  expect(posts).toBe(1);
  expect(reads).toBe(2);
});
test('late accepted POST cannot reopen closed panel or attach stale quotation after edit', async ({
  page,
}) => {
  await page.addInitScript(() => {
    const original = window.fetch;
    window.fetch = (input, init) =>
      String(input).endsWith('/quotations')
        ? new Promise((resolve) =>
            Reflect.set(window, 'finishPost', () =>
              resolve(
                new Response(
                  JSON.stringify({
                    id: '00000000-0000-4000-8000-000000000101',
                    status: 'PENDING',
                  }),
                  { status: 202 },
                ),
              ),
            ),
          )
        : original(input, init);
  });
  await data(page, [locker(1)]);
  await page.locator('#destination-locker').selectOption(id(1));
  await fillShipping(page);
  await page.locator('#compare-shipping').click();
  await expect(page.locator('#quotation-status')).toContainText('Creando');
  await page.locator('#close-results').click();
  await page.evaluate(() => Reflect.get(window, 'finishPost')());
  await expect(page.locator('#results')).toBeHidden();
  await openPanel(page);
  await expect(page.locator('#quotation-status')).toContainText(
    'creación no se ha podido confirmar',
  );
  await expect(page.locator('#quotation-reference')).toBeHidden();
  await expect(page.locator('#quotation-offers')).toBeEmpty();
});
test('availability failure and tile warning are independent; retry clears stale data', async ({
  page,
}) => {
  await tiles(page, true);
  let count = 0;
  await page.route('**/lockers', (r) => {
    count++;
    return count === 1
      ? r.fulfill({ status: 500, json: {} })
      : r.fulfill({ json: [locker(1)] });
  });
  await page.goto('/');
  await expect(page.locator('#retry')).toBeVisible();
  await expect(page.locator('#tile-warning')).toBeVisible();
  await page.locator('#retry').click();
  await expect(page.locator('#available-count')).toHaveText('1');
  await expect(page.locator('#status')).toBeHidden();
});
test('wheel zoom stays isolated from the parcel menu', async ({ page }) => {
  await data(page, [locker(1)], false);
  const marker = page.locator('.locker-marker');
  const initial = await marker.boundingBox();
  await page.mouse.move(700, 500);
  await page.mouse.wheel(0, -400);
  await page.waitForTimeout(400);
  expect(await marker.boundingBox()).not.toEqual(initial);
  const before = await page.locator('.leaflet-map-pane').getAttribute('style');
  await page.locator('.parcel-panel').hover();
  await page.mouse.wheel(0, 300);
  await page.waitForTimeout(300);
  expect(await page.locator('.leaflet-map-pane').getAttribute('style')).toBe(
    before,
  );
});
test('retained POST blocks duplicates, edit discards its late acceptance', async ({
  page,
}) => {
  await page.addInitScript(() => {
    const original = window.fetch;
    let count = 0;
    window.fetch = (input, init) => {
      if (String(input).endsWith('/quotations')) {
        Reflect.set(window, 'postCount', ++count);
        return new Promise((resolve) =>
          Reflect.set(window, 'finishPost', () =>
            resolve(
              new Response(
                JSON.stringify({
                  id: '00000000-0000-4000-8000-000000000101',
                  status: 'PENDING',
                }),
                { status: 202 },
              ),
            ),
          ),
        );
      }
      return original(input, init);
    };
  });
  await data(page, [locker(1)]);
  await page.locator('#destination-locker').selectOption(id(1));
  await fillShipping(page);
  await page.locator('#compare-shipping').click();
  await expect(page.locator('#compare-shipping')).toBeDisabled();
  await page.locator('#shipping-form').evaluate((node) => {
    node.dispatchEvent(
      new Event('submit', { bubbles: true, cancelable: true }),
    );
    node.dispatchEvent(
      new Event('submit', { bubbles: true, cancelable: true }),
    );
  });
  expect(await page.evaluate(() => Reflect.get(window, 'postCount'))).toBe(1);
  await page.locator('#origin-postal').fill('28002');
  await page.evaluate(() => Reflect.get(window, 'finishPost')());
  await expect(page.locator('#quotation-status')).toBeEmpty();
  await expect(page.locator('#quotation-resume')).toBeHidden();
  await expect(page.locator('#compare-shipping')).toBeEnabled();
});
test('late GET after editing or closing cannot restore offers; terminal reopen preserves final result', async ({
  page,
}) => {
  await page.addInitScript(() => {
    const original = window.fetch;
    window.fetch = (input, init) => {
      if (/\/quotations\/[a-f0-9-]+$/.test(String(input)))
        return new Promise((resolve) =>
          Reflect.set(window, 'finishRead', (payload: unknown) =>
            resolve(new Response(JSON.stringify(payload))),
          ),
        );
      return original(input, init);
    };
  });
  let snapshot: any;
  await data(page, [locker(1)]);
  await page.route('**/quotations', (r) => {
    snapshot = r.request().postDataJSON();
    return r.fulfill({ status: 202, json: { id: quoteId, status: 'PENDING' } });
  });
  await page.locator('#destination-locker').selectOption(id(1));
  await fillShipping(page);
  for (const action of ['edit', 'close', 'complete']) {
    await page.locator('#compare-shipping').click();
    await expect
      .poll(() => page.evaluate(() => typeof Reflect.get(window, 'finishRead')))
      .toBe('function');
    if (action === 'edit') await page.locator('#parcel-weight').fill('2');
    if (action === 'close') await page.locator('#close-results').click();
    await page.evaluate((payload) => {
      Reflect.get(window, 'finishRead')(payload);
      Reflect.deleteProperty(window, 'finishRead');
    }, quote(snapshot));
    if (action !== 'complete') {
      await expect(page.locator('#quotation-offers')).toBeEmpty();
      if (action === 'close') await openPanel(page);
    } else {
      await expect(page.locator('#quotation-status')).toContainText(
        'finalizada',
      );
      await page.locator('#close-results').click();
      await openPanel(page);
      await expect(page.locator('#quotation-status')).toContainText(
        'finalizada',
      );
      await expect(page.locator('#quotation-resume')).toBeHidden();
      await expect(page.locator('#quotation-offers')).toContainText('12,34');
    }
  }
});
test('keyboard marker opens public destination and close restores marker focus', async ({
  page,
}) => {
  await data(page, [locker(1, 'Madrid')], false);
  const marker = page.locator('.locker-marker');
  await marker.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#results')).toBeVisible();
  await expect(page.locator('#destination-locker')).toBeFocused();
  await expect(page.locator('#destination-locker')).toHaveValue(id(1));
  await page.keyboard.press('Escape');
  await expect(page.locator('#results')).toBeHidden();
  await expect(marker).toBeFocused();
});
test('unknown provider and service identities remain distinct literal text', async ({
  page,
}) => {
  let snapshot: any;
  await data(page, [locker(1)]);
  await page.route('**/quotations', (r) => {
    snapshot = r.request().postDataJSON();
    return r.fulfill({ status: 202, json: { id: quoteId, status: 'PENDING' } });
  });
  await page.route(`**/quotations/${quoteId}`, (r) => {
    const payload = quote(snapshot);
    payload.results = [
      {
        provider_code: '<img src=x onerror=alert(1)>',
        status: 'QUOTED',
        error_code: null,
        offers: [
          {
            service_code: '<script>evil()</script>',
            currency: 'EUR',
            price_cents: 1234,
            transit_days_min: 4,
            transit_days_max: 4,
          },
        ],
      },
      {
        provider_code: 'other-provider',
        status: 'QUOTED',
        error_code: null,
        offers: [
          {
            service_code: 'other-service',
            currency: 'EUR',
            price_cents: 2000,
            transit_days_min: 2,
            transit_days_max: 2,
          },
        ],
      },
    ];
    return r.fulfill({ json: payload });
  });
  await page.locator('#destination-locker').selectOption(id(1));
  await fillShipping(page);
  await page.locator('#compare-shipping').click();
  await expect(page.locator('#quotation-offers')).toContainText(
    '<img src=x onerror=alert(1)>',
  );
  await expect(page.locator('#quotation-offers')).toContainText(
    '<script>evil()</script>',
  );
  await expect(page.locator('#quotation-offers')).toContainText(
    'other-provider',
  );
  await expect(page.locator('#quotation-offers')).toContainText(
    'other-service',
  );
  await expect(page.locator('#quotation-offers')).toContainText('4 días');
  await expect(page.locator('#quotation-offers')).not.toContainText('4–4');
  await expect(
    page.locator('#quotation-offers img, #quotation-offers script'),
  ).toHaveCount(0);
});
const trackingId = (n: number) =>
  `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
function tracked(
  n = 1001,
  status = 'AWAITING_PICKUP',
  kind = 'delivery',
  relation = status === 'AWAITING_PICKUP' || status === 'AWAITING_CARRIER'
    ? 'current'
    : 'last_known',
) {
  return {
    id: trackingId(n),
    kind,
    status,
    locker_relation: relation,
    locker_id: id(2),
    locker: {
      location_id: 'Locker de seguimiento',
      address: null,
      coordinates: { latitude: 40.4168, longitude: -3.7038 } as {
        latitude: number;
        longitude: number;
      } | null,
    },
  };
}
async function track(page: Page, n: number) {
  await page.locator('#tracking-id').fill(trackingId(n));
  await page.locator('#tracking-id').press('Enter');
}
test('pickup derives only structured CP and delivery independently explores without selecting destination', async ({
  page,
}) => {
  let posts = 0;
  await data(page, [locker(1)]);
  await page.route('**/quotations', (r) => {
    posts++;
    return r.abort();
  });
  await page.route(photon, (r) => {
    const q = new URL(r.request().url()).searchParams.get('q');
    const feature = place(q ?? '01001');
    return r.fulfill({
      json: places({
        ...feature,
        properties: {
          ...feature.properties,
          ...(q === 'Recogida' ? { postcode: '01001' } : {}),
        },
      }),
    });
  });
  await page.locator('#destination-locker').selectOption(id(1));
  await page.locator('#destination-postal').fill('08001');
  const before = await page.locator('.leaflet-map-pane').getAttribute('style');
  await page.locator('#pickup-query').fill('Recogida');
  await expect(page.locator('#pickup-results button')).toHaveCount(1);
  await page.locator('#pickup-results button').click();
  await expect(page.locator('#origin-postal')).toHaveValue('01001');
  expect(await page.locator('.leaflet-map-pane').getAttribute('style')).toBe(
    before,
  );
  await expect(page.locator('#delivery-query')).toHaveValue('');
  await page.locator('#delivery-query').fill('Entrega');
  await expect(page.locator('#delivery-results button')).toHaveCount(1);
  await page.locator('#delivery-results button').click();
  await expect(page.locator('#pickup-query')).toHaveValue('Recogida, 01001');
  await expect(page.locator('#origin-postal')).toHaveValue('01001');
  await expect(page.locator('#destination-postal')).toHaveValue('08001');
  await expect(page.locator('#destination-locker')).toHaveValue(id(1));
  await page.locator('#pickup-query').fill('Recogida editada');
  await expect(page.locator('#origin-postal')).toHaveValue('');
  await page.locator('#origin-postal').fill('28001');
  await page.locator('#pickup-query').fill('Sin código');
  await expect(page.locator('#origin-postal')).toHaveValue('28001');
  await expect(page.locator('#pickup-results button')).toHaveCount(1);
  await page.locator('#pickup-results button').click();
  await expect(page.locator('#origin-postal')).toHaveValue('');
  expect(posts).toBe(0);
});
test('tabs have keyboard relationships, preserve inputs and cancel pending autocomplete and quotation', async ({
  page,
}) => {
  await page.addInitScript(() => {
    const original = window.fetch;
    window.fetch = (input, init) =>
      String(input).endsWith('/quotations')
        ? new Promise((resolve) =>
            Reflect.set(window, 'finishTabPost', () =>
              resolve(
                new Response(
                  JSON.stringify({
                    id: '00000000-0000-4000-8000-000000000101',
                    status: 'PENDING',
                  }),
                  { status: 202 },
                ),
              ),
            ),
          )
        : original(input, init);
  });
  await data(page, [locker(1)]);
  await page.locator('#destination-locker').selectOption(id(1));
  await fillShipping(page);
  await page.locator('#compare-shipping').click();
  await expect(page.locator('#compare-shipping')).toBeDisabled();
  await page.locator('#quote-tab').focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('#tracking-tab')).toBeFocused();
  await expect(page.locator('#tracking-tab')).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await expect(page.locator('#quote-view')).toBeHidden();
  expect(
    await page
      .locator('#quote-view')
      .evaluate((node: HTMLElement) => node.inert),
  ).toBe(true);
  await expect(page.locator('#results')).toBeHidden();
  await page.evaluate(() => Reflect.get(window, 'finishTabPost')());
  await page.locator('#tracking-id').fill(trackingId(1001));
  await page.locator('#tracking-tab').focus();
  await page.keyboard.press('Home');
  await expect(page.locator('#quote-tab')).toBeFocused();
  await expect(page.locator('#tracking-view')).toBeHidden();
  await expect(page.locator('#parcel-weight')).toHaveValue('1.001');
  await expect(page.locator('#destination-locker')).toHaveValue(id(1));
  await page.route(photon, () => {});
  await page.locator('#pickup-query').fill('Pendiente');
  await expect(page.locator('#pickup-search')).toHaveAttribute(
    'aria-busy',
    'true',
  );
  await page.locator('#tracking-tab').click();
  await expect(page.locator('#pickup-query')).toHaveAttribute(
    'aria-expanded',
    'false',
  );
  await expect(page.locator('#tracking-id')).toHaveValue(trackingId(1001));
  await page.locator('#skip-results').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#quote-tab')).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await expect(page.locator('#results')).toBeVisible();
  await expect(page.locator('#destination-locker')).toBeFocused();
  await expect(page.locator('#quotation-status')).not.toContainText('Creando');
});
for (const viewport of [
  { width: 1280, height: 800, name: 'desktop' },
  { width: 375, height: 480, name: 'mobile-short' },
]) {
  test(`tracking real CORS stays independent from availability ${viewport.name}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await tiles(page);
    const apiRequests: string[] = [];
    page.on('request', (r) => {
      if (r.url().startsWith('http://127.0.0.1:8765/'))
        apiRequests.push(`${r.method()} ${new URL(r.url()).pathname}`);
    });
    await page.goto('/');
    await expect(page.locator('#available-count')).toHaveText('1');
    await page.screenshot({
      path: `test-results/tabs-${viewport.name}-quotation.png`,
    });
    await page.locator('#tracking-tab').click();
    await page.locator('#tracking-id').fill('invalid');
    await page.locator('#tracking-submit').click();
    await expect(page.locator('#tracking-error')).toBeVisible();
    expect(apiRequests.filter((r) => r.includes('/tracking/'))).toHaveLength(0);
    const response = page.waitForResponse(
      `http://127.0.0.1:8765/tracking/${trackingId(1001)}`,
    );
    await track(page, 1001);
    expect((await response).headers()['access-control-allow-origin']).toBe(
      'http://127.0.0.1:4321',
    );
    await expect(page.locator('#tracking-result')).toContainText(
      'Pendiente de recogida',
    );
    await expect(page.locator('#tracking-result')).toContainText(
      'Locker actual',
    );
    await expect(page.locator('.tracking-marker')).toHaveCount(1);
    expect(
      await page.locator('.tracking-marker').evaluate((node) => {
        const b = node.getBoundingClientRect();
        return (
          document
            .elementFromPoint(b.x + b.width / 2, b.y + b.height / 2)
            ?.closest('.tracking-marker') === node
        );
      }),
    ).toBe(true);
    await page.locator('.tracking-marker').click();
    await page
      .locator('.locker-marker')
      .evaluate((node) => (node as HTMLElement).click());
    await expect(page.locator('#results')).toBeHidden();
    await expect(page.locator('#tracking-tab')).toHaveAttribute(
      'aria-selected',
      'true',
    );
    await expect(page.locator('#available-count')).toHaveText('1');
    await expect(page.locator('#destination-locker')).toHaveValue('');
    await page.locator('#tracking-result').scrollIntoViewIfNeeded();
    await page.screenshot({
      path: `test-results/tabs-${viewport.name}-tracking-current.png`,
    });
    await track(page, 1002);
    await expect(page.locator('#tracking-result')).toContainText(
      'Entregado al transportista',
    );
    await expect(page.locator('#tracking-result')).toContainText(
      'Último locker registrado',
    );
    await expect(page.locator('#tracking-result')).toContainText(
      'ya ha salido',
    );
    await page.locator('#tracking-result').scrollIntoViewIfNeeded();
    await page.screenshot({
      path: `test-results/tabs-${viewport.name}-tracking-last.png`,
    });
    for (const [n, label] of [
      [1006, 'Recogido'],
      [1007, 'Devuelto al transportista'],
      [1008, 'Pendiente de entrega al transportista'],
    ] as const) {
      await track(page, n);
      await expect(page.locator('#tracking-result h2')).toHaveText(label);
    }
    await track(page, 1003);
    await expect(page.locator('#tracking-result')).toContainText(
      'Sin locker asignado',
    );
    await expect(page.locator('.tracking-marker')).toHaveCount(0);
    await track(page, 1005);
    await expect(page.locator('#tracking-result')).toContainText(
      'Datos del locker no disponibles',
    );
    await expect(page.locator('.tracking-marker')).toHaveCount(0);
    await track(page, 9999);
    await expect(page.locator('#tracking-status')).toContainText(
      'No se ha encontrado',
    );
    await expect(page.locator('#tracking-retry')).toBeVisible();
    await page.locator('#tracking-retry').focus();
    const repeated = page.waitForResponse(
      `http://127.0.0.1:8765/tracking/${trackingId(9999)}`,
    );
    await page.keyboard.press('Enter');
    await repeated;
    await expect(page.locator('#tracking-id')).toBeFocused();
    await expect(page.locator('#tracking-status')).toContainText(
      'No se ha encontrado',
    );

    await track(page, 1004);
    await expect(page.locator('#tracking-status')).toContainText('ambiguo');
    const requestCount = apiRequests.length;
    await page.locator('#quote-tab').click();
    await page.locator('#tracking-tab').click();
    await expect(page.locator('#tracking-result')).toBeHidden();
    await expect(page.locator('#tracking-status')).toBeEmpty();
    await expect(page.locator('#tracking-id')).toHaveValue(trackingId(1004));
    expect(apiRequests.length).toBe(requestCount);
    expect(
      apiRequests.every(
        (r) => r === 'GET /lockers' || r.startsWith('GET /tracking/'),
      ),
    ).toBe(true);
    expect(apiRequests.filter((r) => r === 'GET /lockers')).toHaveLength(1);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBe(viewport.width);
    expect(await page.locator('#map').boundingBox()).toMatchObject({
      x: 0,
      y: 0,
      width: viewport.width,
      height: viewport.height,
    });
  });
}
test('tracking displays all five custody states and null coordinates despite availability/tile errors', async ({
  page,
}) => {
  await tiles(page, true);
  await page.route('**/lockers', (r) => r.fulfill({ status: 503, json: {} }));
  await page.route('**/tracking/*', (r) => {
    const n = Number(r.request().url().slice(-4));
    const states = [
      ['delivery', 'AWAITING_PICKUP'],
      ['delivery', 'COLLECTED'],
      ['delivery', 'RETURNED_TO_CARRIER'],
      ['return', 'AWAITING_CARRIER'],
      ['return', 'HANDED_OVER'],
    ];
    const [kind, status] = states[n - 2001]!;
    const payload = tracked(n, status, kind);
    payload.locker.coordinates = null;
    return r.fulfill({ json: payload });
  });
  await page.goto('/');
  await expect(page.locator('#retry')).toBeVisible();
  await page.locator('#tracking-tab').click();
  for (const [i, label] of [
    'Pendiente de recogida',
    'Recogido',
    'Devuelto al transportista',
    'Pendiente de entrega al transportista',
    'Entregado al transportista',
  ].entries()) {
    await track(page, 2001 + i);
    await expect(page.locator('#tracking-result h2')).toHaveText(label);
    await expect(page.locator('#tracking-result')).toContainText(
      'Ubicación no disponible',
    );
    await expect(page.locator('.tracking-marker')).toHaveCount(0);
  }
  await expect(page.locator('#tracking-tile-warning')).toBeVisible();
});
test('tracking cancels stale reads on edit/new attempt/tab change even when abort is ignored', async ({
  page,
}) => {
  await page.addInitScript(() => {
    const original = window.fetch;
    window.fetch = (input, init) =>
      String(input).includes('/tracking/')
        ? new Promise((resolve) =>
            Reflect.set(window, 'finishTracking', (payload: unknown) =>
              resolve(new Response(JSON.stringify(payload))),
            ),
          )
        : original(input, init);
  });
  await data(page, [locker(1)], false);
  await page.locator('#tracking-tab').click();
  for (const action of ['edit', 'new', 'tab']) {
    await track(page, 1001);
    await expect(page.locator('#tracking-form')).toHaveAttribute(
      'aria-busy',
      'true',
    );
    const previous = await page
      .locator('.leaflet-map-pane')
      .getAttribute('style');
    if (action === 'edit')
      await page.locator('#tracking-id').fill(trackingId(1002));
    if (action === 'new') {
      await page.evaluate(() =>
        Reflect.set(
          window,
          'finishOlderTracking',
          Reflect.get(window, 'finishTracking'),
        ),
      );
      await track(page, 1002);
    }
    if (action === 'tab') await page.locator('#quote-tab').click();
    await page.evaluate(
      ({ payload, older }) =>
        Reflect.get(
          window,
          older ? 'finishOlderTracking' : 'finishTracking',
        )(payload),
      { payload: tracked(), older: action === 'new' },
    );
    await expect(page.locator('#tracking-result')).toBeHidden();
    await expect(page.locator('.tracking-marker')).toHaveCount(0);
    expect(await page.locator('.leaflet-map-pane').getAttribute('style')).toBe(
      previous,
    );
    if (action === 'new') {
      await page.evaluate(
        (payload) => Reflect.get(window, 'finishTracking')(payload),
        tracked(1002, 'COLLECTED'),
      );
      await expect(page.locator('#tracking-result')).toContainText('Recogido');
    }
    if (action === 'tab') {
      await page.locator('#tracking-tab').click();
      await expect(page.locator('#tracking-id')).toHaveValue(trackingId(1001));
      await expect(page.locator('#tracking-form')).not.toHaveAttribute(
        'aria-busy',
        'true',
      );
    }
  }
});
test('late pickup suggestions cannot overwrite delivery candidates or a manual origin', async ({
  page,
}) => {
  await page.addInitScript(() => {
    const original = window.fetch;
    window.fetch = (input, init) =>
      String(input).includes('photon.komoot.io') &&
      new URL(String(input)).searchParams.get('q') === 'Anterior recogida'
        ? new Promise((resolve) =>
            Reflect.set(window, 'finishPickup', () =>
              resolve(
                new Response(
                  JSON.stringify({
                    type: 'FeatureCollection',
                    features: [
                      {
                        type: 'Feature',
                        geometry: { type: 'Point', coordinates: [-2, 42] },
                        properties: {
                          name: 'Obsoleta',
                          countrycode: 'ES',
                          postcode: '01001',
                        },
                      },
                    ],
                  }),
                ),
              ),
            ),
          )
        : original(input, init);
  });
  await data(page, [locker(1)]);
  await page.locator('#origin-postal').fill('28001');
  await page.route(photon, (r) =>
    r.fulfill({ json: places(place('Entrega vigente')) }),
  );
  await page.locator('#pickup-query').fill('Anterior recogida');
  await expect(page.locator('#pickup-search')).toHaveAttribute(
    'aria-busy',
    'true',
  );
  await page.locator('#delivery-query').fill('Entrega');
  await expect(page.locator('#delivery-results button')).toHaveText(
    'Entrega vigente',
  );
  const before = await page.locator('.leaflet-map-pane').getAttribute('style');
  await page.evaluate(() => Reflect.get(window, 'finishPickup')());
  await expect(page.locator('#pickup-query')).toHaveAttribute(
    'aria-expanded',
    'false',
  );
  await expect(page.locator('#delivery-results button')).toHaveText(
    'Entrega vigente',
  );
  await expect(page.locator('#origin-postal')).toHaveValue('28001');
  expect(await page.locator('.leaflet-map-pane').getAttribute('style')).toBe(
    before,
  );
});
