import { expect, test, type Page } from '@playwright/test';
const id = (n: number) =>
  `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const knownLabels = new Map<string, string>();
function locker(
  n: number,
  label: string | null = `Locker ${n}`,
  coordinates: unknown = { latitude: 40.4168, longitude: -3.7038 },
) {
  knownLabels.set(id(n), label ?? `Locker ${n}`);
  return {
    id: id(n),
    location_id: label,
    active: true,
    address: { ...address },
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
  await showMenu(page);
  if (open) await openPanel(page);
}
async function showMenu(page: Page) {
  const toggle = page.locator('#menu-toggle');
  if (
    (await toggle.isVisible()) &&
    (await toggle.getAttribute('aria-expanded')) === 'false'
  )
    await toggle.click();
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
  test(`separate geography and quote menu with selectable autocomplete ${viewport.name}`, async ({
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
    await showMenu(page);
    await expect(page.locator('#available-count')).toHaveText('1');
    await expect(page.locator('#map-panels .panel')).toHaveCount(2);
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
      name: 'Dirección o código postal',
    });
    const before = await page
      .locator('.leaflet-map-pane')
      .getAttribute('style');
    await query.fill(' 01001 ');
    expect(geoReads).toBe(0);
    await expect(page.locator('#location-results button')).toHaveCount(1);
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
      page.locator('#location-results button').first(),
    ).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(query).toHaveValue('01001 Vitoria');
    await expect(query).toBeFocused();
    await expect(query).toHaveAttribute('aria-expanded', 'false');
    expect(
      await page
        .locator('#location-suggestions')
        .evaluate((node: HTMLElement) => node.inert),
    ).toBe(true);
    await expect(page.locator('#location-suggestions')).toBeHidden();
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
    await expect(page.locator('#location-results button')).toHaveCount(5);
    await page.locator('#location-results button').nth(1).click();
    await expect(query).toHaveValue('Plaza Mayor, Madrid');
    await expect(page.locator('#location-suggestions')).toBeHidden();
    expect(await markerHit(page)).toBe(true);
    await expect(page.locator('#results')).toBeHidden();
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
    name: 'Dirección o código postal',
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
  await expect(page.locator('#location-results button')).toHaveCount(1);
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
    name: 'Dirección o código postal',
  });
  await query.fill('Madrid');
  await expect(page.locator('#location-status')).toContainText('HTTP 503');
  await expect(page.locator('#status')).toBeHidden();
  await expect(page.locator('#available-count')).toHaveText('1');
  await page.getByRole('button', { name: 'Reintentar búsqueda' }).click();
  await expect(page.locator('#location-status')).toContainText(
    'No se han encontrado',
  );
  await query.fill('Madrid centro');
  await expect(page.locator('#location-status')).toContainText(
    'respuesta no válida',
  );
  await page.getByRole('button', { name: 'Reintentar búsqueda' }).focus();
  await page.keyboard.press('Enter');
  await expect(
    page.getByRole('combobox', { name: 'Dirección o código postal' }),
  ).toBeFocused();
  await expect(page.locator('#location-results button')).toHaveCount(1);
  await page.locator('#location-results button').click();
  await page.unroute(photon);
  await page.route(photon, () => {});
  await query.fill('Tardará');
  await expect(page.locator('#location-status')).toContainText(
    'cinco segundos',
    {
      timeout: 7000,
    },
  );
  await expect(page.locator('#location-retry')).toBeVisible();
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
    name: 'Dirección o código postal',
  });
  const before = await page.locator('.leaflet-map-pane').getAttribute('style');
  for (const [index, close] of ['escape', 'blur'].entries()) {
    await query.fill(`Anterior ${index}`);
    await expect(page.locator('#location-search')).toHaveAttribute(
      'aria-busy',
      'true',
    );
    if (close === 'escape') await query.press('Escape');
    else await page.getByRole('spinbutton', { name: 'Largo (cm)' }).focus();
    await page.evaluate(() => Reflect.get(window, 'completeOldSearch')());
    await expect(page.locator('#location-suggestions')).toBeHidden();
    await expect(query).toHaveAttribute('aria-expanded', 'false');
    expect(await page.locator('.leaflet-map-pane').getAttribute('style')).toBe(
      before,
    );
  }
  await query.fill('Anterior otra');
  await expect(page.locator('#location-search')).toHaveAttribute(
    'aria-busy',
    'true',
  );
  await query.fill('Última');
  await expect(page.locator('#location-results button')).toHaveText(
    'Última ubicación',
  );
  await page.evaluate(() => Reflect.get(window, 'completeOldSearch')());
  await expect(page.locator('#location-results button')).toHaveText(
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
    name: 'Dirección o código postal',
  });
  await query.fill('Madrid');
  await expect(page.locator('#location-results button')).toHaveCount(2);
  await query.press('ArrowDown');
  await expect(page.locator('#location-results button').first()).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(query).toBeFocused();
  expect(
    await page
      .locator('#location-suggestions')
      .evaluate((node: HTMLElement) => node.inert),
  ).toBe(true);
  await page
    .locator('#location-results button')
    .first()
    .evaluate((node) => node.focus());
  await expect(query).toBeFocused();
  await query.press('Tab');
  await expect(page.locator('#location-suggestions')).toBeHidden();
  await query.fill('Madrid nuevo');
  await expect(page.locator('#location-results button')).toHaveCount(2);
  await expect(query).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('#location-suggestions')).toHaveCSS('opacity', '1');
  await expect(page.locator('#location-suggestions')).not.toHaveAttribute(
    'hidden',
  );
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(page.locator('#location-suggestions')).toHaveCSS(
    'transition-duration',
    '0s',
  );
  await query.press('Escape');
  expect(
    await page
      .locator('#location-suggestions')
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
      name: 'Dirección o código postal',
    });
    await query.fill('Gran Vía');
    await expect(page.locator('#location-results button')).toHaveCount(1);
    await page.locator('#location-results button').tap();
    await expect(query).toHaveValue('Gran Vía, Madrid');
    await expect(query).toBeFocused();
    await expect(page.locator('#location-suggestions')).toBeHidden();
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
    name: 'Dirección o código postal',
  });
  await query.fill('Centro');
  await expect(page.locator('#location-results button')).toHaveCount(2);
  await page.locator('#location-results button').nth(1).click();
  await expect(query).toHaveValue('Centro');
  await expect(page.locator('#location-suggestions')).toBeHidden();
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
async function selectRole(page: Page, role: 'pickup' | 'delivery', n: number) {
  await showMenu(page);
  const input = page.locator(`#${role}-locker`);
  if ((await input.getAttribute('readonly')) !== null)
    await page.locator(`#${role}-clear`).click();
  await input.fill(knownLabels.get(id(n)) ?? 'Locker');
  await page
    .locator(`#${role}-options [role="option"][data-id="${id(n)}"]`)
    .click();
  await expect(input).toHaveAttribute('data-selected-id', id(n));
}
async function fillShipping(page: Page) {
  if (!(await page.locator('#pickup-locker').getAttribute('data-selected-id')))
    await selectRole(page, 'pickup', 1);
  if (
    !(await page.locator('#delivery-locker').getAttribute('data-selected-id'))
  )
    await selectRole(page, 'delivery', 1);
  for (const [field, value] of [
    ['length', '25.5'],
    ['width', '15'],
    ['height', '10'],
    ['weight', '1.001'],
  ])
    await page.locator(`#parcel-${field}`).fill(value!);
}
async function reopenResults(page: Page) {
  await page.locator('#reopen-results').click();
}
async function expectRoleUncovered(page: Page, role: 'pickup' | 'delivery') {
  await expect
    .poll(() =>
      page.locator(`#${role}-clear`).evaluate((input) => {
        const box = input.getBoundingClientRect();
        const panel = input.closest('.left-stack')!.getBoundingClientRect();
        const tabs = document
          .querySelector('.mode-tabs')!
          .getBoundingClientRect();
        return {
          hit:
            document
              .elementFromPoint(box.x + box.width / 2, box.y + box.height / 2)
              ?.closest('button') === input,
          contained:
            box.top >= Math.max(panel.top, tabs.bottom, 0) - 1 &&
            box.bottom <= Math.min(panel.bottom, window.innerHeight) + 1 &&
            box.left >= 0 &&
            box.right <= window.innerWidth,
        };
      }),
    )
    .toEqual({ hit: true, contained: true });
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
  knownLabels.set(id(1), 'Locker CORS');
  await tiles(page);
  const response = page.waitForResponse('http://127.0.0.1:8765/lockers');
  await page.goto('/');
  await showMenu(page);
  await expect(page.locator('#available-count')).toHaveText('1');
  expect((await response).headers()['access-control-allow-origin']).toBe(
    'http://127.0.0.1:4321',
  );
  await openPanel(page);
  await selectRole(page, 'delivery', 1);
  await fillShipping(page);
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
    await showMenu(page);
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
    await expect(page.locator('#pickup-locker')).toBeFocused();
    await selectRole(page, 'pickup', 2);
    await selectRole(page, 'delivery', 2);
    await expect(page.locator('#delivery-options')).toBeHidden();
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
      origin_postal_code: '01001',
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
    const beforeChange = await page
      .locator('.leaflet-map-pane')
      .getAttribute('style');
    await selectRole(page, 'delivery', 1);
    await expect(page.locator('#quotation-offers')).toBeEmpty();
    await expect(page.locator('.locker-route,.route-endpoint')).toHaveCount(0);
    await expect(page.locator('#route-status')).toContainText(
      'locker de origen',
    );
    await page.waitForTimeout(450);
    expect(
      await page.locator('.leaflet-map-pane').getAttribute('style'),
    ).toEqual(beforeChange);
    await expect(page.locator('#results')).toBeHidden();
  });
}
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
  await selectRole(page, 'delivery', 1);
  await fillShipping(page);
  await page.locator('#compare-shipping').click();
  await expect(page.locator('#quotation-resume')).toBeVisible();
  await page.locator('#close-results').click();
  await expect(page.locator('#results')).toBeHidden();
  await reopenResults(page);
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
  await selectRole(page, 'delivery', 1);
  await fillShipping(page);
  await page.locator('#compare-shipping').click();
  await expect(page.locator('#quotation-status')).toContainText('Creando');
  await page.locator('#close-results').click();
  await page.evaluate(() => Reflect.get(window, 'finishPost')());
  await expect(page.locator('#results')).toBeHidden();
  await reopenResults(page);
  await expect(page.locator('#quotation-status')).toContainText(
    'creación no se ha podido confirmar',
  );
  await expect(page.locator('#quotation-reference')).toHaveCount(0);
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
  await showMenu(page);
  await expect(page.locator('#retry')).toBeVisible();
  await expect(page.locator('#tile-warning')).toBeVisible();
  await page.locator('#retry').click();
  await expect(page.locator('#available-count')).toHaveText('1');
  await expect(page.locator('#status')).toBeHidden();
});
test('wheel zoom stays isolated from the parcel menu', async ({ page }) => {
  await data(page, [locker(1)], false);
  const tileState = () =>
    page
      .locator('.leaflet-tile-container')
      .evaluateAll((nodes) =>
        nodes.map((node) => (node as HTMLElement).style.transform),
      );
  const initial = await tileState();
  await page.mouse.move(700, 500);
  await page.mouse.wheel(0, -400);
  await page.waitForTimeout(400);
  expect(await tileState()).not.toEqual(initial);
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
  await selectRole(page, 'delivery', 1);
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
  await showMenu(page);
  await page.locator('#parcel-weight').fill('1.002');
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
  await selectRole(page, 'delivery', 1);
  await fillShipping(page);
  for (const action of ['edit', 'close', 'complete']) {
    await page.locator('#compare-shipping').click();
    await expect
      .poll(() => page.evaluate(() => typeof Reflect.get(window, 'finishRead')))
      .toBe('function');
    if (action === 'edit') {
      await showMenu(page);
      await page.locator('#parcel-weight').fill('2');
    }
    if (action === 'close') await page.locator('#close-results').click();
    await page.evaluate((payload) => {
      Reflect.get(window, 'finishRead')(payload);
      Reflect.deleteProperty(window, 'finishRead');
    }, quote(snapshot));
    if (action !== 'complete') {
      await expect(page.locator('#quotation-offers')).toBeEmpty();
      if (action === 'close') await reopenResults(page);
    } else {
      await expect(page.locator('#quotation-status')).toContainText(
        'finalizada',
      );
      await page.locator('#close-results').click();
      await reopenResults(page);
      await expect(page.locator('#quotation-status')).toContainText(
        'finalizada',
      );
      await expect(page.locator('#quotation-resume')).toBeHidden();
      await expect(page.locator('#quotation-offers')).toContainText('12,34');
    }
  }
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
  await selectRole(page, 'delivery', 1);
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
  await showMenu(page);
  await page.locator('#tracking-id').fill(trackingId(n));
  await page.locator('#tracking-id').press('Enter');
}
for (const viewport of [
  { width: 1280, height: 800, name: 'desktop' },
  { width: 375, height: 480, name: 'mobile-short' },
]) {
  test(`removed tracking returns a real CORS-readable 404 ${viewport.name}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await tiles(page);
    knownLabels.set(id(1), 'Locker CORS');
    const apiRequests: string[] = [];
    page.on('request', (r) => {
      if (r.url().startsWith('http://127.0.0.1:8765/'))
        apiRequests.push(`${r.method()} ${new URL(r.url()).pathname}`);
    });
    await page.goto('/');
    await showMenu(page);
    await expect(page.locator('#available-count')).toHaveText('1');
    await fillShipping(page);
    await showMenu(page);
    await page.locator('#tracking-tab').click();
    await showMenu(page);
    await page.locator('#tracking-id').fill('invalid');
    await page.locator('#tracking-submit').click();
    await expect(page.locator('#tracking-error')).toBeVisible();
    expect(apiRequests.filter((r) => r.includes('/tracking/'))).toHaveLength(0);
    const url = `http://127.0.0.1:8765/tracking/${trackingId(1001)}`;
    const response = page.waitForResponse(url);
    await track(page, 1001);
    const missing = await response;
    expect(missing.status()).toBe(404);
    expect(missing.headers()['access-control-allow-origin']).toBe(
      'http://127.0.0.1:4321',
    );
    expect(await missing.json()).toEqual({ detail: 'Not Found' });
    await expect(page.locator('#tracking-status')).toContainText(
      'No se ha encontrado',
    );
    await expect(page.locator('#tracking-result')).toBeHidden();
    await expect(page.locator('.tracking-marker')).toHaveCount(0);
    await expect(page.locator('#available-count')).toHaveText('1');
    await page.locator('#tracking-retry').focus();
    const repeated = page.waitForResponse(url);
    await page.keyboard.press('Enter');
    expect((await repeated).status()).toBe(404);
    await expect(page.locator('#tracking-id')).toBeFocused();
    await expect(page.locator('#tracking-status')).toContainText(
      'No se ha encontrado',
    );
    const requestCount = apiRequests.length;
    await showMenu(page);
    await page.locator('#quote-tab').click();
    await expect(page.locator('#pickup-locker')).toHaveAttribute(
      'data-selected-id',
      id(1),
    );
    await expect(page.locator('#delivery-locker')).toHaveAttribute(
      'data-selected-id',
      id(1),
    );
    await expect(page.locator('#parcel-weight')).toHaveValue('1.001');
    await expect(page.locator('#compare-shipping')).toBeEnabled();
    await showMenu(page);
    await page.locator('#tracking-tab').click();
    await expect(page.locator('#tracking-result')).toBeHidden();
    await expect(page.locator('#tracking-status')).toBeEmpty();
    await expect(page.locator('#tracking-id')).toHaveValue(trackingId(1001));
    expect(apiRequests.length).toBe(requestCount);
    expect(
      apiRequests.every(
        (r) => r === 'GET /lockers' || r.startsWith('GET /tracking/'),
      ),
    ).toBe(true);
    expect(apiRequests.filter((r) => r === 'GET /lockers')).toHaveLength(1);
    expect(
      apiRequests.filter((r) => r.startsWith('GET /tracking/')),
    ).toHaveLength(2);
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
  await showMenu(page);
  await expect(page.locator('#retry')).toBeVisible();
  await showMenu(page);
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
  await showMenu(page);
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
    if (action === 'edit') {
      await showMenu(page);
      await page.locator('#tracking-id').fill(trackingId(1002));
    }
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
    if (action === 'tab') {
      await showMenu(page);
      await page.locator('#quote-tab').click();
    }
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
      await showMenu(page);
      await page.locator('#tracking-tab').click();
      await expect(page.locator('#tracking-id')).toHaveValue(trackingId(1001));
      await expect(page.locator('#tracking-form')).not.toHaveAttribute(
        'aria-busy',
        'true',
      );
    }
  }
});

test('roles require registered postal codes and no independent postal controls exist', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  let posts = 0,
    reads = 0;
  await tiles(page);
  await page.route('**/lockers', (r) => {
    reads++;
    return r.fulfill({
      json: [
        {
          ...locker(1, 'Completo'),
          address: { ...address, postal_code: '01001' },
        },
        { ...locker(2, 'Sin CP', null), address: null },
        {
          ...locker(3, 'Inválido'),
          address: { ...address, postal_code: '１２３４５' },
        },
        {
          ...locker(4, 'Extranjero'),
          address: { ...address, country_code: 'FR' },
        },
      ],
    });
  });
  await page.route('**/quotations', (r) => {
    posts++;
    return r.abort();
  });
  await page.goto('/');
  await showMenu(page);
  await expect(
    page.getByRole('combobox', { name: 'Locker de origen', exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('combobox', { name: 'Locker de destino', exact: true }),
  ).toBeVisible();
  await expect(
    page.locator('#origin-postal,#destination-postal,input[type=hidden]'),
  ).toHaveCount(0);
  await expect(page.locator('[aria-describedby]')).not.toHaveCount(0);
  await fillShipping(page);
  await expect(page.locator('#compare-shipping')).toBeEnabled();
  await expect(page.locator('#pickup-locker')).not.toHaveAccessibleDescription(
    /no tiene un CP/,
  );
  await expect(
    page.locator('#delivery-locker'),
  ).not.toHaveAccessibleDescription(/no tiene un CP/);
  for (const role of ['pickup', 'delivery'] as const) {
    for (const n of [2, 3, 4]) {
      await selectRole(page, role, n);
      await expect(page.locator(`#${role}-postal-warning`)).toHaveText(
        'Este locker no tiene un CP válido. Elige otro',
      );
      await expect(page.locator(`#${role}-postal-warning`)).toBeVisible();

      await expect(page.locator(`#${role}-locker`)).toHaveAccessibleDescription(
        /no tiene un CP/,
      );
      await expect(page.locator('#compare-shipping')).toBeDisabled();
      await page
        .locator('#shipping-form')
        .evaluate((form) =>
          form.dispatchEvent(
            new Event('submit', { bubbles: true, cancelable: true }),
          ),
        );
      await expect(page.locator(`#${role}-clear`)).toBeFocused();
      expect(posts).toBe(0);
      await selectRole(page, role, 1);
      await expect(page.locator(`#${role}-postal-warning`)).toBeHidden();
      await expect(page.locator('#compare-shipping')).toBeEnabled();
      await expect(
        page.locator('#pickup-locker'),
      ).not.toHaveAccessibleDescription(/no tiene un CP/);
      await expect(
        page.locator('#delivery-locker'),
      ).not.toHaveAccessibleDescription(/no tiene un CP/);
    }
  }
  await page.locator('#delivery-clear').click();
  await page.locator('#delivery-locker').fill('Completo');
  await expect(page.locator('#delivery-locker')).toHaveAttribute(
    'data-selected-id',
    '',
  );
  await expect(page.locator('#compare-shipping')).toBeDisabled();
  await expect(page.locator('#pickup-locker')).toHaveAttribute(
    'data-selected-id',
    id(1),
  );
  await expect(page.locator('#parcel-length')).toHaveValue('25.5');
  expect(reads).toBe(1);
  expect(posts).toBe(0);
});

test('local candidates preserve duplicates, unmapped identities and safe literal labels', async ({
  page,
}) => {
  await data(
    page,
    [
      locker(1, '<img src=x onerror=alert(1)>'),
      ...Array.from({ length: 12 }, (_, i) => locker(i + 2, 'Duplicado', null)),
      {
        ...locker(20, 'Postal'),
        address: { ...address, postal_code: '07009' },
      },
    ],
    false,
  );
  await page.locator('#delivery-locker').fill('Duplicado');
  await expect(page.locator('#delivery-options [role=option]')).toHaveCount(12);
  await page.locator(`#delivery-options [data-id="${id(13)}"]`).click();
  await expect(page.locator('#delivery-locker')).toHaveAttribute(
    'data-selected-id',
    id(13),
  );
  await page.locator('#pickup-locker').fill('07009');
  await expect(page.locator('#pickup-options [role=option]')).toHaveCount(1);
  await page.locator('#pickup-options [role=option]').click();
  await expect(page.locator('#pickup-locker')).toHaveAttribute(
    'data-selected-id',
    id(20),
  );
  await page.locator('#delivery-clear').click();
  await page.locator('#delivery-locker').fill('<img');
  await expect(page.locator('#delivery-options')).toContainText(
    '<img src=x onerror=alert(1)>',
  );
  await expect(
    page.locator('#delivery-options img, #delivery-options script'),
  ).toHaveCount(0);
  await page.locator('#delivery-locker').press('ArrowDown');
  await expect(page.locator('#delivery-options [role=option]')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.locator('#delivery-locker')).toBeFocused();
  await expect(page.locator('#delivery-suggestions')).toBeHidden();
});

test('map geography remains above both tabs without supplying role postal input', async ({
  page,
}) => {
  await data(page, [locker(1), locker(2)], false);
  await selectRole(page, 'pickup', 1);
  await selectRole(page, 'delivery', 2);
  await fillShipping(page);
  await page.route(photon, (r) =>
    r.fulfill({
      json: places({
        ...place('Mapa independiente'),
        properties: {
          name: 'Mapa independiente',
          countrycode: 'ES',
          postcode: '99999',
        },
      }),
    }),
  );
  await showMenu(page);
  await page.locator('#tracking-tab').click();
  await showMenu(page);
  await page.locator('#location-query').fill('Madrid');
  await page.locator('#location-results button').click();
  await expect(page.locator('#tracking-tab')).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await expect(page.locator('#location-query')).toHaveValue(
    'Mapa independiente, 99999',
  );
  await expect(page.locator('.search-location')).toHaveCount(1);
  await showMenu(page);
  await page.locator('#quote-tab').click();
  await expect(page.locator('#pickup-locker')).toHaveAttribute(
    'data-selected-id',
    id(1),
  );
  await expect(page.locator('#delivery-locker')).toHaveAttribute(
    'data-selected-id',
    id(2),
  );
});

for (const viewport of [
  { width: 1280, height: 800, name: 'desktop' },
  { width: 375, height: 480, name: 'mobile-short' },
]) {
  test(`popup inspection and explicit role actions preserve keyboard focus ${viewport.name}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await data(page, [locker(1, 'Popup seguro')], false);
    await showMenu(page);
    await page.locator('#tracking-tab').click();
    const marker = page.locator('.locker-marker');
    await marker.focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('.leaflet-popup')).toContainText('Popup seguro');
    await expect(page.locator('#tracking-tab')).toHaveAttribute(
      'aria-selected',
      'true',
    );
    await expect(page.locator('#results')).toBeHidden();
    await expect(page.locator('#delivery-locker')).toHaveAttribute(
      'data-selected-id',
      '',
    );
    const delivery = page.getByRole('button', {
        name: 'Locker de destino',
        exact: true,
      }),
      pickup = page.getByRole('button', {
        name: 'Locker de origen',
        exact: true,
      });
    await expect(delivery).toBeVisible();
    await expect(pickup).toBeVisible();
    await page.screenshot({
      path: `test-results/roles-${viewport.name}-popup.png`,
    });
    await pickup.focus();
    await page.keyboard.press('Escape');
    await expect(page.locator('.leaflet-popup')).toHaveCount(0);
    await expect(marker).toBeFocused();
    await page.keyboard.press('Enter');
    await delivery.click();
    await expect(page.locator('#quote-tab')).toHaveAttribute(
      'aria-selected',
      'true',
    );
    await expect(page.locator('#delivery-locker')).toHaveAttribute(
      'data-selected-id',
      id(1),
    );
    await expect(page.locator('#delivery-clear')).toBeFocused();
    await expectRoleUncovered(page, 'delivery');
    await expect(page.locator('#pickup-locker')).toHaveAttribute(
      'data-selected-id',
      '',
    );
    await expect(page.locator('#results')).toBeHidden();
    await marker.focus();
    await page.keyboard.press('Enter');
    await pickup.click();
    await expect(page.locator('#pickup-locker')).toHaveAttribute(
      'data-selected-id',
      id(1),
    );
    await expect(page.locator('#delivery-locker')).toHaveAttribute(
      'data-selected-id',
      id(1),
    );
    await expect(page.locator('#pickup-clear')).toBeFocused();
    await expectRoleUncovered(page, 'pickup');
    // Selecting a role must reveal its input after the menu has been scrolled.
    await page
      .locator(viewport.width <= 760 ? '#menu-content' : '.left-stack')
      .evaluate((panel) => {
        panel.scrollTop = panel.scrollHeight;
      });
    if (viewport.height === 480)
      expect(
        await page
          .locator(viewport.width <= 760 ? '#menu-content' : '.left-stack')
          .evaluate((panel) => panel.scrollTop),
      ).toBeGreaterThan(0);
    await marker.focus();
    await page.keyboard.press('Enter');
    await delivery.click();
    await expect(page.locator('#delivery-locker')).toHaveAttribute(
      'data-selected-id',
      id(1),
    );
    await expect(page.locator('#delivery-clear')).toBeFocused();
    await expectRoleUncovered(page, 'delivery');
    await page
      .locator(viewport.width <= 760 ? '#menu-content' : '.left-stack')
      .evaluate((panel) => {
        panel.scrollTop = panel.scrollHeight;
      });
    if (viewport.height === 480)
      expect(
        await page
          .locator(viewport.width <= 760 ? '#menu-content' : '.left-stack')
          .evaluate((panel) => panel.scrollTop),
      ).toBeGreaterThan(0);
    await marker.focus();
    await page.keyboard.press('Enter');
    await pickup.click();
    await expect(page.locator('#pickup-clear')).toBeFocused();
    await expectRoleUncovered(page, 'pickup');
    await page.screenshot({
      path: `test-results/roles-${viewport.name}-selected.png`,
    });
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

test('changing either UUID invalidates a completed result even with identical postal codes', async ({
  page,
}) => {
  let posts = 0;
  let snapshot: unknown;
  await data(
    page,
    [
      { ...locker(1, 'Uno'), address },
      { ...locker(2, 'Dos'), address },
      { ...locker(3, 'Tres'), address },
    ],
    false,
  );
  await page.route('**/quotations', (r) => {
    posts++;
    snapshot = r.request().postDataJSON();
    return r.fulfill({ status: 202, json: { id: quoteId, status: 'PENDING' } });
  });
  await page.route(`**/quotations/${quoteId}`, (r) =>
    r.fulfill({ json: quote(snapshot) }),
  );
  await selectRole(page, 'pickup', 1);
  await selectRole(page, 'delivery', 2);
  await fillShipping(page);
  await page.locator('#compare-shipping').click();
  await expect(page.locator('#quotation-offers')).toContainText('12,34');
  await expect(
    page.locator(
      '#results input, #results select, #results form, #results #compare-shipping',
    ),
  ).toHaveCount(0);
  await page.locator('#close-results').click();
  await reopenResults(page);
  await expect(page.locator('#quotation-offers')).toContainText('12,34');
  expect(posts).toBe(1);
  await selectRole(page, 'pickup', 3);
  await expect(page.locator('#results')).toBeHidden();
  await expect(page.locator('#quotation-offers')).toBeEmpty();
  await expect(page.locator('#reopen-results')).toBeHidden();
  await page.locator('#compare-shipping').click();
  await expect(page.locator('#quotation-offers')).toContainText('12,34');
  expect(posts).toBe(2);
  await selectRole(page, 'delivery', 1);
  await expect(page.locator('#quotation-offers')).toBeEmpty();
  await expect(page.locator('#reopen-results')).toBeHidden();
  expect(posts).toBe(2);
});

test('exact parcel limits disable Compare until correction without a write', async ({
  page,
}) => {
  let posts = 0;
  await data(page, [locker(1)], false);
  await page.route('**/quotations', (r) => {
    posts++;
    return r.abort();
  });
  await fillShipping(page);
  for (const [field, value] of [
    ['length', '1.01'],
    ['weight', '0.0001'],
    ['height', '201'],
    ['weight', '31'],
  ]) {
    await page.locator(`#parcel-${field}`).fill(value!);
    await expect(page.locator('#compare-shipping')).toBeDisabled();
    await fillShipping(page);
    await expect(page.locator('#compare-shipping')).toBeEnabled();
  }
  expect(posts).toBe(0);
});

test('tabs preserve both role identities and parcel data while cancelling pending POST', async ({
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
  await data(page, [locker(1), locker(2)], false);
  await selectRole(page, 'pickup', 1);
  await selectRole(page, 'delivery', 2);
  await fillShipping(page);
  await page.locator('#compare-shipping').click();
  await expect(page.locator('#compare-shipping')).toBeDisabled();
  await showMenu(page);
  await page.locator('#quote-tab').focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('#tracking-tab')).toBeFocused();
  await expect(page.locator('#quote-view')).toBeHidden();
  expect(
    await page.locator('#quote-view').evaluate((n: HTMLElement) => n.inert),
  ).toBe(true);
  await expect(page.locator('#results')).toBeHidden();
  await page.evaluate(() => Reflect.get(window, 'finishTabPost')());
  await showMenu(page);
  await page.locator('#tracking-id').fill(trackingId(1001));
  await showMenu(page);
  await page.locator('#tracking-tab').focus();
  await page.keyboard.press('Home');
  await expect(page.locator('#quote-tab')).toBeFocused();
  await expect(page.locator('#pickup-locker')).toHaveAttribute(
    'data-selected-id',
    id(1),
  );
  await expect(page.locator('#delivery-locker')).toHaveAttribute(
    'data-selected-id',
    id(2),
  );
  await expect(page.locator('#parcel-weight')).toHaveValue('1.001');
  await page.locator('#skip-results').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#pickup-clear')).toBeFocused();
  await expect(page.locator('#results')).toBeHidden();
});
for (const viewport of [
  { width: 1280, height: 800, name: 'desktop' },
  { width: 375, height: 480, name: 'mobile-short' },
]) {
  test(`bounded local suggestions for both roles ${viewport.name}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    let apiReads = 0,
      otherReads = 0;
    await tiles(page);
    const payload = Array.from({ length: 21 }, (_, index) =>
      locker(
        index + 1,
        index === 20 ? 'Zeta Grupo' : `Veinte ${index + 1} Grupo`,
        null,
      ),
    );
    await page.route('**/lockers', (r) => {
      apiReads++;
      return r.fulfill({ json: payload });
    });
    page.on('request', (r) => {
      if (
        r.url().includes('/quotations') ||
        r.url().includes('photon.komoot.io')
      )
        otherReads++;
    });
    await page.goto('/');
    await showMenu(page);
    await expect(page.locator('#available-count')).toHaveText('21');
    for (const role of ['pickup', 'delivery'] as const) {
      const input = page.locator(`#${role}-locker`),
        suggestions = page.locator(`#${role}-suggestions`),
        options = page.locator(`#${role}-options [role=option]`),
        status = page.locator(`#${role}-search-status`);
      for (const [query, message] of [
        ['', ''],
        ['  ', ''],
        ['Ausente', 'Sin coincidencias'],
        ['Grupo', 'Concreta la búsqueda'],
      ]) {
        await input.fill(query!);
        for (const action of [
          'focus',
          'click',
          'Enter',
          'ArrowDown',
          'ArrowUp',
        ]) {
          if (action === 'focus') await input.focus();
          else if (action === 'click') await input.click();
          else await input.press(action);
          await expect(input).toHaveAttribute('aria-expanded', 'false');
          expect(
            await suggestions.evaluate((node: HTMLElement) => node.inert),
          ).toBe(true);
          await expect(options).toHaveCount(0);
        }
        if (message) await expect(status).toHaveText(message);
        else await expect(status).toBeHidden();
      }
      await input.fill('Veinte');
      await expect(options).toHaveCount(20);
      await expect(input).toHaveAttribute('aria-expanded', 'true');
      await input.press('ArrowUp');
      await expect(options.last()).toBeFocused();
      await page.keyboard.press('Enter');
      await expect(input).toHaveAttribute('data-selected-id', id(20));
      await expect(suggestions).toBeHidden();
      await expect(input).toHaveAttribute('readonly', '');
      await expect(page.locator(`#${role}-clear`)).toBeFocused();
      await input.click();
      await input.press('ArrowDown');
      await input.press('Enter');
      await expect(input).toHaveAttribute('aria-expanded', 'false');
      await expect(suggestions).toBeHidden();
      await expect(input).toHaveAttribute('data-selected-id', id(20));
      await page.locator(`#${role}-clear`).click();
      await expect(input).toBeFocused();
      await input.fill('Veinte');
      await input.fill('Grupo');
      await expect(input).toHaveAttribute('aria-expanded', 'false');
      await expect(status).toHaveText('Concreta la búsqueda');
      await input.fill('Z');
      await expect(options).toHaveCount(1);
      await page.waitForTimeout(200);
      await expect(suggestions).toBeVisible();
      await input.press('Escape');
      await expect(input).toBeFocused();
      await expect(suggestions).toBeHidden();
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await input.fill('Z');
      await expect(options).toHaveCount(1);
      await input.fill('');
      expect(
        await suggestions.evaluate((node) => (node as HTMLElement).hidden),
      ).toBe(true);
      await page.emulateMedia({ reducedMotion: 'no-preference' });
    }
    expect(apiReads).toBe(1);
    expect(otherReads).toBe(0);
  });
}
async function popupGap(page: Page, markerSelector: string) {
  return page.evaluate((selector) => {
    const marker = document.querySelector(selector)!,
      popup = document.querySelector('.leaflet-popup')!,
      tip = document.querySelector('.leaflet-popup-tip-container')!;
    const icon = marker.getBoundingClientRect(),
      span = marker.querySelector('span')?.getBoundingClientRect(),
      box = popup.getBoundingClientRect(),
      point = tip.getBoundingClientRect();
    return {
      gap:
        Math.min(icon.top, span?.top ?? icon.top) -
        Math.max(box.bottom, point.bottom),
      popup: { x: box.x, y: box.y, right: box.right, bottom: box.bottom },
      icon: { x: icon.x, y: icon.y, right: icon.right, bottom: icon.bottom },
      viewport: { width: innerWidth, height: innerHeight },
    };
  }, markerSelector);
}
for (const viewport of [
  { width: 1280, height: 800, name: 'desktop' },
  { width: 375, height: 480, name: 'mobile-short' },
  { width: 320, height: 568, name: 'mobile-narrow' },
  { width: 667, height: 375, name: 'mobile-landscape' },
]) {
  for (const kind of ['available', 'tracking'] as const) {
    test(`popup clears real ${kind} icon after map changes ${viewport.name}`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);
      await data(
        page,
        [
          locker(1, 'Geometría segura'),
          ...(kind === 'available'
            ? [
                locker(2, 'Segundo popup', {
                  latitude: 40.42,
                  longitude: -3.71,
                }),
              ]
            : []),
        ],
        false,
      );
      if (kind === 'available') await selectRole(page, 'pickup', 1);
      const selector =
        kind === 'available'
          ? '.locker-marker[title="Geometría segura"]'
          : '.tracking-marker';
      if (kind === 'tracking') {
        await page.route('**/tracking/*', (r) =>
          r.fulfill({ json: tracked() }),
        );
        await showMenu(page);
        await page.locator('#tracking-tab').click();
        await track(page, 1001);
        await expect(page.locator('.tracking-marker')).toHaveCount(1);
      }
      const marker = page.locator(selector);
      await marker.focus();
      await marker.press('Enter');
      await expect(page.locator('.leaflet-popup')).toBeVisible();
      if (kind === 'available') {
        await expect(page.locator('.locker-popup')).toContainText(
          'Seleccionar como:',
        );
        await expect(
          page.getByRole('button', { name: 'Locker de destino', exact: true }),
        ).toBeVisible();
        await expect(
          page.getByRole('button', { name: 'Locker de origen', exact: true }),
        ).toBeVisible();
        await expect(page.locator('.locker-popup')).not.toContainText(
          'Seleccionar como locker',
        );
      } else {
        await expect(page.locator('.locker-popup')).toContainText(
          'Locker actual',
        );
        await expect(page.locator('.locker-popup button')).toHaveCount(0);
      }
      async function assertGap() {
        await page.waitForTimeout(350);
        const geometry = await popupGap(page, selector);
        expect(geometry.gap).toBeGreaterThanOrEqual(4);
        expect(
          await marker.evaluate((node) => {
            const r = node.getBoundingClientRect();
            return (
              document
                .elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)
                ?.closest('.locker-marker,.tracking-marker') === node
            );
          }),
        ).toBe(true);

        expect(geometry.popup.x).toBeGreaterThanOrEqual(0);
        expect(geometry.popup.y).toBeGreaterThanOrEqual(0);
        expect(geometry.popup.right).toBeLessThanOrEqual(
          geometry.viewport.width,
        );
        expect(geometry.popup.bottom).toBeLessThanOrEqual(
          geometry.viewport.height,
        );
        expect(geometry.icon.y).toBeGreaterThanOrEqual(0);
        expect(geometry.icon.bottom).toBeLessThanOrEqual(
          geometry.viewport.height,
        );
      }
      await assertGap();
      await page.screenshot({
        path: `test-results/popup-gap-${kind}-${viewport.name}.png`,
      });
      await page.mouse.move(viewport.width - 15, viewport.height - 50);
      await page.mouse.down();
      await page.mouse.move(viewport.width - 40, viewport.height - 65, {
        steps: 5,
      });
      await page.mouse.up();
      await page.waitForTimeout(250);
      await assertGap();
      await page.mouse.move(viewport.width - 15, viewport.height - 50);
      await page.mouse.wheel(0, 120);
      await page.waitForTimeout(400);
      await assertGap();
      await page.setViewportSize({
        width: viewport.width + (kind === 'available' ? 10 : 20),
        height: viewport.height + 30,
      });
      await page.waitForTimeout(200);
      await assertGap();
      await page.locator('.leaflet-popup-close-button').focus();
      await page.keyboard.press('Escape');
      await expect(page.locator('.leaflet-popup')).toHaveCount(0);
      await expect(marker).toBeFocused();
      expect(
        await marker.evaluate((node) =>
          node.parentElement?.classList.contains('leaflet-marker-pane'),
        ),
      ).toBe(true);
      await marker.press('Enter');
      await expect(
        page.locator('.inspection-pane').locator(selector),
      ).toHaveCount(1);
      if (kind === 'available') {
        await page
          .getByRole('button', { name: 'Locker de destino', exact: true })
          .click();
        await expect(page.locator('#delivery-locker')).toHaveAttribute(
          'data-selected-id',
          id(1),
        );
        await expect(page.locator('#delivery-clear')).toBeFocused();
        expect(
          await marker.evaluate((node) =>
            node.parentElement?.classList.contains('leaflet-marker-pane'),
          ),
        ).toBe(true);
        await marker.press('Enter');
        const other = page.locator('.locker-marker[title="Segundo popup"]');
        await other.focus();
        await other.press('Enter');
        expect(
          await marker.evaluate((node) =>
            node.parentElement?.classList.contains('leaflet-marker-pane'),
          ),
        ).toBe(true);
        expect(
          await other.evaluate((node) =>
            node.parentElement?.classList.contains('inspection-pane'),
          ),
        ).toBe(true);
        await page.reload();
        await expect(page.locator('#available-count')).toHaveText('2');
        await expect(
          page.locator('.inspection-pane .locker-marker'),
        ).toHaveCount(0);
        await expect(
          page.locator('.leaflet-marker-pane .locker-marker'),
        ).toHaveCount(0);
        await expect(page.locator('.locker-cluster')).toHaveText('2');
      } else {
        await showMenu(page);
        await page.locator('#quote-tab').click();
        await expect(
          page.locator('.inspection-pane .tracking-marker'),
        ).toHaveCount(0);
      }
    });
  }
}

test('postal request uses the selected origin and destination records with leading zeroes', async ({
  page,
}) => {
  const captured: unknown[] = [];
  let snapshot: unknown;
  await data(
    page,
    [
      {
        ...locker(1, 'Origen registrado'),
        address: { ...address, postal_code: '01001' },
      },
      {
        ...locker(2, 'Destino registrado'),
        address: { ...address, postal_code: '28009' },
      },
    ],
    false,
  );
  await page.route('**/quotations', (r) => {
    snapshot = r.request().postDataJSON();
    captured.push(snapshot);
    return r.fulfill({ status: 202, json: { id: quoteId, status: 'PENDING' } });
  });
  await page.route(`**/quotations/${quoteId}`, (r) =>
    r.fulfill({ json: quote(snapshot) }),
  );
  await selectRole(page, 'pickup', 1);
  await selectRole(page, 'delivery', 2);
  await fillShipping(page);
  await page.locator('#compare-shipping').click();
  await expect(page.locator('#quotation-status')).toContainText('finalizada');
  expect(captured[0]).toEqual({
    origin_country_code: 'ES',
    origin_postal_code: '01001',
    destination_country_code: 'ES',
    destination_postal_code: '28009',
    weight_grams: 1001,
    dimensions: { depth_mm: 255, width_mm: 150, height_mm: 100 },
  });
  await page.locator('#close-results').click();
  await selectRole(page, 'pickup', 2);
  await selectRole(page, 'delivery', 1);
  await page.locator('#compare-shipping').click();
  await expect(page.locator('#quotation-status')).toContainText('finalizada');
  expect(captured[1]).toMatchObject({
    origin_postal_code: '28009',
    destination_postal_code: '01001',
  });
});

async function routeGeometry(page: Page, labels: string[]) {
  await expect(page.locator('.leaflet-map-pane')).not.toHaveClass(
    /leaflet-zoom-anim/,
  );
  await page.waitForTimeout(350);
  const badges = page.locator('.route-endpoint');
  await expect(badges).toHaveCount(labels.length);
  for (const [index, label] of labels.entries()) {
    const readGeometry = () =>
      badges.nth(index).evaluate((node, title) => {
        const box = node.getBoundingClientRect();
        const menu = document
          .querySelector('#map-panels')!
          .getBoundingClientRect();
        const pin = document
          .querySelector(`.locker-marker[title="${title}"]`)!
          .getBoundingClientRect();
        return {
          x: box.x,
          right: box.right,
          y: box.y,
          bottom: box.bottom,
          menuRight: innerWidth <= 760 ? 12 : menu.right,
          menuBottom: innerWidth <= 760 ? menu.bottom : 78,
          width: innerWidth,
          height: innerHeight,
          dx: Math.abs((box.left + box.right) / 2 - (pin.left + pin.right) / 2),
          dy: Math.abs((box.top + box.bottom) / 2 - pin.bottom),
          interactive: getComputedStyle(node).pointerEvents,
        };
      }, label);
    await expect
      .poll(async () => {
        const g = await readGeometry();
        return (
          g.x >= g.menuRight &&
          g.right <= g.width &&
          g.y >= Math.max(90, g.menuBottom) &&
          g.bottom <= g.height - 16 &&
          g.dx <= 1 &&
          g.dy <= 1
        );
      })
      .toBe(true);
    const geometry = await readGeometry();
    expect(geometry.x).toBeGreaterThanOrEqual(geometry.menuRight);
    expect(geometry.right).toBeLessThanOrEqual(geometry.width);
    expect(geometry.y).toBeGreaterThanOrEqual(90);
    expect(geometry.bottom).toBeLessThanOrEqual(geometry.height - 16);
    expect(geometry.dx).toBeLessThanOrEqual(1);
    expect(geometry.dy).toBeLessThanOrEqual(1);
    expect(geometry.interactive).toBe('none');
  }
  const ends = await page.locator('.locker-route').evaluate((node) => {
    const path = node as SVGPathElement,
      matrix = path.getScreenCTM()!;
    return [0, path.getTotalLength()].map((length) => {
      const point = path.getPointAtLength(length).matrixTransform(matrix);
      return { x: point.x, y: point.y };
    });
  });
  const centers = await badges.evaluateAll((nodes) =>
    nodes.map((node) => {
      const box = node.getBoundingClientRect();
      return { x: (box.left + box.right) / 2, y: (box.top + box.bottom) / 2 };
    }),
  );
  for (const end of ends)
    expect(centers.some((c) => Math.hypot(end.x - c.x, end.y - c.y) <= 2)).toBe(
      true,
    );
}
for (const viewport of [
  { width: 1280, height: 800, name: 'desktop' },
  { width: 375, height: 480, name: 'mobile-short' },
  { width: 320, height: 568, name: 'mobile-narrow' },
  { width: 667, height: 375, name: 'mobile-landscape' },
]) {
  test(`illustrative route preserves real endpoints and independent navigation ${viewport.name}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    const records = [
      locker(1, 'Origen visual'),
      locker(2, 'Destino visual', { latitude: 28.1248, longitude: -15.43 }),
      locker(3, 'Sin ubicación', null),
      locker(4, 'Mismo punto'),
      locker(5, 'Cercano', { latitude: 40.416801, longitude: -3.703801 }),
      locker(6, 'Separables', { latitude: 40.4168, longitude: -3.7028 }),
    ];
    let reads = 0,
      writes = 0;
    await tiles(page);
    await page.route('**/lockers', (r) => {
      reads++;
      return r.fulfill({ json: records });
    });
    await page.route('**/tracking/*', (r) => r.fulfill({ json: tracked() }));
    await page.route('**/quotations', (r) => {
      writes++;
      return r.fulfill({ status: 500, json: {} });
    });
    await page.route(photon, (r) =>
      r.fulfill({ json: places(place('Barcelona', 2.17, 41.39)) }),
    );
    await page.goto('/');
    await showMenu(page);
    await expect(page.locator('#available-count')).toHaveText('6');
    await selectRole(page, 'pickup', 1);
    await expect(page.locator('.locker-route')).toHaveCount(0);
    // An open inspection must not fight the subsequent pair framing.
    const pin = page.locator('.locker-marker[title="Origen visual"]');
    await pin.focus();
    await pin.press('Enter');
    await selectRole(page, 'delivery', 2);
    await expect(page.locator('.leaflet-popup')).toHaveCount(0);
    await expect(page.locator('#delivery-clear')).toBeFocused();
    await expect(page.locator('#route-status')).toHaveText(
      'Trayecto orientativo · O origen · D destino',
    );
    await routeGeometry(page, ['Origen visual', 'Destino visual']);
    await expect(page.locator('.route-endpoint').first()).toHaveAccessibleName(
      'Origen: Origen visual',
    );
    await expect(page.locator('.route-endpoint').last()).toHaveAccessibleName(
      'Destino: Destino visual',
    );
    await page.screenshot({ path: `test-results/route-${viewport.name}.png` });
    const origin = page.locator('.route-endpoint').first();
    const beforePan = await origin.boundingBox();
    await page.mouse.move(viewport.width - 35, viewport.height / 2);
    await page.mouse.down();
    await page.mouse.move(viewport.width - 35, viewport.height / 2 + 60, {
      steps: 8,
    });
    await page.mouse.up();
    await page.waitForTimeout(300);
    const afterPan = await origin.boundingBox();
    expect(afterPan).not.toEqual(beforePan);
    await page.waitForTimeout(200);
    expect(await origin.boundingBox()).toEqual(afterPan);
    await showMenu(page);
    await page.locator('#location-query').fill('Barcelona');
    await page.locator('#location-results button').click();
    await expect(page.locator('.search-location')).toHaveCount(1);
    await expect(page.locator('.locker-route')).toHaveCount(1);
    const afterGeo = await origin.boundingBox();
    await page.waitForTimeout(200);
    expect(await origin.boundingBox()).toEqual(afterGeo);
    await showMenu(page);
    await page.locator('#tracking-tab').click();
    await expect(page.locator('.route-endpoint,.locker-route')).toHaveCount(0);
    await track(page, 1001);
    await expect(page.locator('.tracking-marker')).toHaveCount(1);
    await showMenu(page);
    await page.locator('#quote-tab').click();
    await routeGeometry(page, ['Origen visual', 'Destino visual']);
    await expect(page.locator('.tracking-marker')).toHaveCount(0);
    await selectRole(page, 'delivery', 3);
    await expect(page.locator('.route-endpoint,.locker-route')).toHaveCount(0);
    await expect(page.locator('#route-status')).toContainText(
      'locker de destino',
    );
    await fillShipping(page);
    await expect(page.locator('#compare-shipping')).toBeEnabled();
    await selectRole(page, 'delivery', 4);
    await routeGeometry(page, ['Mismo punto']);
    await expect(page.locator('.route-endpoint')).toHaveAccessibleName(
      'Origen y destino en el mismo punto',
    );
    const zooms = await page
      .locator('.leaflet-tile')
      .evaluateAll((nodes) =>
        nodes.map((node) =>
          Number((node as HTMLImageElement).src.match(/\.org\/(\d+)\//)?.[1]),
        ),
      );
    expect(Math.max(...zooms)).toBeLessThanOrEqual(14);
    await selectRole(page, 'delivery', 5);
    await expect(page.locator('.route-endpoint')).toHaveText('O/D');
    await expect(page.locator('.route-endpoint')).toHaveAccessibleName(
      'Origen y destino agrupados en esta vista',
    );
    await expect(page.locator('#route-status')).toContainText(
      'origen y destino agrupados en esta vista',
    );
    await expect(page.locator('#route-status')).not.toContainText(
      'mismo punto',
    );
    await page.screenshot({
      path: `test-results/route-close-${viewport.name}.png`,
    });
    await selectRole(page, 'delivery', 6);
    await expect(page.locator('.route-endpoint')).toHaveText('O/D');
    await page
      .getByRole('button', { name: 'Acercar mapa', exact: true })
      .click();
    await expect(page.locator('.leaflet-map-pane')).toHaveClass(
      /leaflet-zoom-anim/,
    );
    await expect(page.locator('.leaflet-map-pane')).not.toHaveClass(
      /leaflet-zoom-anim/,
    );
    await page
      .getByRole('button', { name: 'Acercar mapa', exact: true })
      .click();
    await expect(page.locator('.leaflet-map-pane')).toHaveClass(
      /leaflet-zoom-anim/,
    );
    await expect(page.locator('.leaflet-map-pane')).not.toHaveClass(
      /leaflet-zoom-anim/,
    );
    await expect(page.locator('.route-endpoint')).toHaveText(['O', 'D']);
    await page
      .getByRole('button', { name: 'Alejar mapa', exact: true })
      .click();
    await expect(page.locator('.leaflet-map-pane')).toHaveClass(
      /leaflet-zoom-anim/,
    );
    await expect(page.locator('.leaflet-map-pane')).not.toHaveClass(
      /leaflet-zoom-anim/,
    );
    await page
      .getByRole('button', { name: 'Alejar mapa', exact: true })
      .click();
    await expect(page.locator('.leaflet-map-pane')).toHaveClass(
      /leaflet-zoom-anim/,
    );
    await expect(page.locator('.leaflet-map-pane')).not.toHaveClass(
      /leaflet-zoom-anim/,
    );
    await expect(page.locator('.route-endpoint')).toHaveText('O/D');
    await page.locator('#delivery-clear').click();
    await page.locator('#delivery-locker').fill('');
    await expect(page.locator('.route-endpoint,.locker-route')).toHaveCount(0);
    await expect(page.locator('#route-status')).toBeHidden();
    await expect(page.locator('#pickup-locker')).toHaveAttribute(
      'data-selected-id',
      id(1),
    );
    expect(reads).toBe(1);
    expect(writes).toBe(0);
  });
}

async function basePosition(page: Page, label: string) {
  return page.locator(`.locker-marker[title="${label}"]`).evaluate((node) => {
    const box = node.getBoundingClientRect();
    return { x: box.x, y: box.y };
  });
}
async function expectPositionStopped(page: Page, label: string) {
  const reference = (await page.locator('.search-location').count())
    ? page.locator('.search-location')
    : page.locator(`.locker-marker[title="${label}"]`);
  const position = () =>
    reference.evaluate((node) => {
      const r = node.getBoundingClientRect();
      return { x: r.x, y: r.y };
    });
  const before = await position();
  await page.waitForTimeout(450);
  const after = await position();
  expect(
    Math.hypot(after.x - before.x, after.y - before.y),
  ).toBeLessThanOrEqual(1);
}
async function samplePopup(page: Page) {
  await page.evaluate(() => {
    const samples: { x: number; y: number }[] = [];
    Reflect.set(window, 'popupSamples', samples);
    const until = performance.now() + 650;
    function frame() {
      const box = document
        .querySelector('.leaflet-popup')
        ?.getBoundingClientRect();
      if (box) samples.push({ x: box.x, y: box.y });
      if (performance.now() < until) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  });
}
for (const viewport of [
  { width: 1280, height: 800, name: 'desktop' },
  { width: 375, height: 480, name: 'mobile-short' },
]) {
  test(`locked role clears explicitly without camera movement ${viewport.name}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await data(
      page,
      [
        locker(1, 'Origen animado'),
        locker(2, 'Destino animado', { latitude: 28.12, longitude: -15.43 }),
      ],
      false,
    );
    const initial = await basePosition(page, 'Origen animado');
    await selectRole(page, 'pickup', 1);
    await expect(page.locator('#pickup-clear')).toBeFocused();
    expect(await basePosition(page, 'Origen animado')).toEqual(initial);
    const input = page.locator('#pickup-locker');
    await input.focus();
    await input.click();
    await input.pressSequentially('otro');
    for (const key of ['Enter', 'ArrowDown', 'ArrowUp']) await input.press(key);
    await expect(input).toHaveValue('Origen animado');
    await expect(input).toHaveAttribute('data-selected-id', id(1));
    await expect(input).toHaveAttribute('readonly', '');
    await expect(input).not.toBeDisabled();
    await expect(page.locator('#pickup-suggestions')).toBeHidden();
    await expect(input).toHaveAttribute('aria-expanded', 'false');
    await page.locator('#pickup-clear').focus();
    await page.screenshot({ path: `test-results/locked-${viewport.name}.png` });
    await page.locator('#pickup-clear').press('Enter');
    await expect(input).toBeFocused();
    await expect(input).toBeEditable();
    await expect(input).toHaveValue('');
    await expect(page.locator('#pickup-clear')).toBeHidden();
    await expect(page.locator('#pickup-suggestions')).toBeHidden();
    await expectPositionStopped(page, 'Origen animado');
    await selectRole(page, 'pickup', 1);
    await showMenu(page);
    await page.locator('#parcel-weight').fill('1.001');
    await selectRole(page, 'delivery', 2);
    // Observe an in-flight fractional zoom before cancelling it with X.
    await expect
      .poll(
        () =>
          page.locator('.leaflet-tile-container').evaluateAll((nodes) =>
            nodes.some((node) => {
              const scale = new DOMMatrixReadOnly(
                getComputedStyle(node).transform,
              ).a;
              return Math.abs(scale - Math.round(scale)) > 0.01;
            }),
          ),
        { intervals: [10], timeout: 250 },
      )
      .toBe(true);
    await page.locator('#delivery-clear').dispatchEvent('click');
    await expect(page.locator('#delivery-locker')).toBeFocused();
    await expect(page.locator('.locker-route,.route-endpoint')).toHaveCount(0);
    await expectPositionStopped(page, 'Origen animado');
    await expect(page.locator('#pickup-locker')).toHaveAttribute(
      'data-selected-id',
      id(1),
    );
    await expect(page.locator('#parcel-weight')).toHaveValue('1.001');
  });
  for (const reduced of [false, true]) {
    test(`popup camera is continuous and cancellable ${viewport.name} reduced=${reduced}`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);
      await page.emulateMedia({
        reducedMotion: reduced ? 'reduce' : 'no-preference',
      });
      await page.route(photon, (route) =>
        route.fulfill({ json: places(place('Barcelona', 2.17, 41.39)) }),
      );
      await data(
        page,
        [
          locker(1, 'Origen animado'),
          locker(2, 'Otro popup', { latitude: 41.39, longitude: 2.17 }),
        ],
        false,
      );
      const marker = page.locator('.locker-marker[title="Origen animado"]');
      await samplePopup(page);
      await marker.focus();
      await marker.press('Enter');
      await page.waitForTimeout(700);
      const points = await page.evaluate(
        () => Reflect.get(window, 'popupSamples') as { x: number; y: number }[],
      );
      const unique = new Set(
        points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`),
      );
      if (reduced) expect(unique.size).toBe(1);
      else {
        expect(unique.size).toBeGreaterThan(3);
        const steps = points
          .slice(1)
          .map((p, i) => Math.hypot(p.x - points[i]!.x, p.y - points[i]!.y));
        const distance = Math.hypot(
          points.at(-1)!.x - points[0]!.x,
          points.at(-1)!.y - points[0]!.y,
        );
        expect(Math.max(...steps)).toBeLessThan(distance * 0.65);
        expect(Math.max(...steps.slice(-5))).toBeLessThan(1);
      }
      await expect(page.locator('.popup-role-actions button')).toHaveText([
        'Locker de origen',
        'Locker de destino',
      ]);
      await page.screenshot({
        path: `test-results/camera-${viewport.name}-${reduced ? 'reduced' : 'normal'}.png`,
      });
      await page.keyboard.press('Escape');
      await expect(page.locator('.leaflet-popup')).toHaveCount(0);
      const otherForEscape = page.locator('.locker-marker[title="Otro popup"]');
      const beforeOpening = await basePosition(page, 'Otro popup');
      await otherForEscape.focus();
      await otherForEscape.press('Enter');
      if (!reduced) {
        await page.waitForTimeout(60);
        const duringOpening = await basePosition(page, 'Otro popup');
        expect(
          Math.hypot(
            duringOpening.x - beforeOpening.x,
            duringOpening.y - beforeOpening.y,
          ),
        ).toBeGreaterThan(1);
      }
      await page.keyboard.press('Escape');
      await expect(otherForEscape).toBeFocused();
      await expectPositionStopped(page, 'Origen animado');
      await marker.press('Enter');
      const other = page.locator('.locker-marker[title="Otro popup"]');
      await other.focus();
      await other.press('Enter');
      await page.waitForTimeout(400);
      await expect(page.locator('.locker-popup strong')).toHaveText(
        'Otro popup',
      );
      await expectPositionStopped(page, 'Origen animado');
      await marker.focus();
      await marker.press('Enter');
      await showMenu(page);
      await page.locator('#location-query').fill('Barcelona');
      await expectPositionStopped(page, 'Origen animado');
      await page.locator('#location-results button').click();
      await expect(page.locator('.search-location')).toHaveCount(1);
      await expectPositionStopped(page, 'Origen animado');
      await other.focus();
      await other.press('Enter');
      await page.mouse.move(viewport.width - 16, viewport.height * 0.55);
      await page.mouse.down();
      await page.mouse.move(viewport.width - 16, viewport.height * 0.55 + 20, {
        steps: 5,
      });
      await page.mouse.up();
      await page.waitForTimeout(350);
      await expectPositionStopped(page, 'Origen animado');
      await other.focus();
      await other.press('Enter');
      await showMenu(page);
      await page.locator('#tracking-tab').click();
      await expect(page.locator('.leaflet-popup')).toHaveCount(0);
      await expectPositionStopped(page, 'Origen animado');
    });
  }
}

for (const viewport of [
  { width: 1280, height: 800, name: 'desktop' },
  { width: 375, height: 480, name: 'mobile-short' },
]) {
  test(`dense viewport clusters retain full collection and role emphasis ${viewport.name}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const records = Array.from({ length: 5000 }, (_, n) =>
      locker(n + 1, `Denso ${String(n + 1).padStart(5, '0')}`, {
        latitude: 36 + Math.floor(n / 100) * 0.15,
        longitude: -9 + (n % 100) * 0.12,
      }),
    );
    await data(page, records, false);
    await expect(page.locator('#available-count')).toHaveText('5000');
    await expect(page.locator('#positioned-count')).toHaveText('5000');
    await expect(page.locator('.locker-cluster').first()).toBeAttached();
    expect(
      await page.locator('.locker-marker,.locker-cluster').count(),
    ).toBeLessThan(500);
    const represented = () =>
      page
        .locator('.locker-marker,.locker-cluster')
        .evaluateAll((nodes) =>
          nodes.reduce(
            (sum, node) =>
              sum +
              (node.classList.contains('locker-cluster')
                ? Number(node.textContent)
                : 1),
            0,
          ),
        );
    expect(await represented()).toBe(5000);
    await selectRole(page, 'pickup', 1);
    await expect(page.locator('.locker-marker.is-role')).toHaveCount(1);
    expect(await represented()).toBe(5000);
    await selectRole(page, 'delivery', 5000);
    await expect(page.locator('.locker-marker.is-role')).toHaveCount(2);
    await expect(page.locator('.locker-cluster').first()).toHaveCSS(
      'opacity',
      '0.3',
    );
    for (const pin of await page.locator('.locker-marker.is-role').all()) {
      await expect(pin).toHaveCSS('opacity', '1');
      await expect(pin.locator('svg')).toHaveCount(1);
      await expect(pin.locator('svg g rect')).toHaveAttribute('x', '10');
    }
    await expect(page.locator('.route-endpoint')).toHaveCount(2);
    await page.screenshot({
      path: `test-results/clusters-${viewport.name}-route.png`,
    });
    const group = page.locator('.locker-cluster').first();
    await group.focus();
    await group.press('Escape');
    await expect(group).toHaveCSS('opacity', '1');
    await showMenu(page);
    await page.locator('#tracking-tab').click();
    await expect(page.locator('.locker-cluster').first()).toHaveCSS(
      'opacity',
      '1',
    );
    await showMenu(page);
    await page.locator('#quote-tab').click();
    await expect(page.locator('.locker-cluster').first()).toHaveCSS(
      'opacity',
      '0.3',
    );
    await page.locator('#pickup-clear').click();
    await expect(page.locator('.locker-cluster').first()).toHaveCSS(
      'opacity',
      '1',
    );
    await expect(page.locator('#available-count')).toHaveText('5000');
    expect(
      await page.locator('.locker-marker,.locker-cluster').count(),
    ).toBeLessThan(500);
  });
  test(`coincident groups expose every UUID in bounded pages with safe current actions ${viewport.name}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const records = Array.from({ length: 45 }, (_, n) =>
      locker(n + 1, '<img src=x> Repetido'),
    );
    let reads = 0;
    await tiles(page);
    await page.route('**/lockers', (r) => {
      reads++;
      return r.fulfill({ json: records });
    });
    await page.goto('/');
    await showMenu(page);
    await expect(page.locator('#available-count')).toHaveText('45');
    await expect(page.locator('.locker-cluster')).toHaveText('45');
    await expect(page.locator('.locker-marker')).toHaveCount(0);
    await page.locator('.locker-cluster').focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('.cluster-members')).toHaveCount(0);
    await page.locator('.locker-cluster').focus();
    await page.keyboard.press(' ');
    await expect(page.locator('.cluster-member-list button')).toHaveCount(20);
    await page.locator('.leaflet-popup-close-button').focus();
    await page.keyboard.press('Escape');
    await expect(page.locator('.cluster-members')).toHaveCount(0);
    await expect(page.locator('.locker-cluster')).toBeFocused();
    await page.keyboard.press('Enter');
    const ids: string[] = [];
    for (let pageNumber = 1; pageNumber <= 3; pageNumber++) {
      await expect(page.locator('.cluster-members')).toContainText(
        `Página ${pageNumber} de 3`,
      );
      ids.push(
        ...(await page
          .locator('.cluster-member-list button')
          .evaluateAll((nodes) =>
            nodes.map((n) => (n as HTMLElement).dataset.id!),
          )),
      );
      if (pageNumber < 3)
        await page
          .getByRole('button', { name: 'Siguiente', exact: true })
          .click();
    }
    expect(new Set(ids).size).toBe(45);
    expect(new Set(ids)).toEqual(new Set(records.map((x) => x.id)));
    await expect(page.locator('.cluster-member-list button')).toHaveCount(5);
    await expect(
      page.locator('.cluster-members img,.cluster-members script'),
    ).toHaveCount(0);
    await page.screenshot({
      path: `test-results/clusters-${viewport.name}-members.png`,
    });
    const last = page.locator('.cluster-member-list button').last(),
      firstId = await last.getAttribute('data-id');
    await last.click();
    await expect(page.locator('.locker-popup strong')).toContainText(
      '<img src=x> Repetido',
    );
    await page.keyboard.press('Escape');
    await expect(
      page.locator(`.locker-marker[data-id="${firstId}"]`),
    ).toBeFocused();
    await expect(page.locator('.locker-cluster')).toHaveText('44');
    await page.keyboard.press('Enter');
    await page
      .getByRole('button', { name: 'Locker de origen', exact: true })
      .click();
    await expect(page.locator('#pickup-locker')).toHaveAttribute(
      'data-selected-id',
      firstId!,
    );
    await page.locator('.locker-cluster').focus();
    await page.keyboard.press('Enter');
    const second = page.locator('.cluster-member-list button').first(),
      secondId = await second.getAttribute('data-id');
    expect(secondId).not.toBe(firstId);
    await second.click();
    await page
      .getByRole('button', { name: 'Locker de destino', exact: true })
      .click();
    await expect(page.locator('#delivery-locker')).toHaveAttribute(
      'data-selected-id',
      secondId!,
    );
    await expect(page.locator('#pickup-locker')).toHaveAttribute(
      'data-selected-id',
      firstId!,
    );
    await expect(page.locator('.locker-marker.is-role')).toHaveCount(2);
    await expect(page.locator('.locker-cluster')).toHaveText('43');
    const openMembers = async () => {
      await page.locator('.locker-cluster').focus();
      await page.keyboard.press('Enter');
      if (!(await page.locator('.cluster-members').count())) {
        await page.locator('.locker-cluster').focus();
        await page.keyboard.press('Enter');
      }
      await expect(page.locator('.cluster-members')).toHaveCount(1);
    };
    await openMembers();
    await expect(
      page.locator('.cluster-member-list button').first(),
    ).toBeFocused();
    await expect(page.locator('.locker-cluster')).toHaveCSS('opacity', '1');
    await page.locator('.leaflet-popup-close-button').focus();
    await page.keyboard.press('Escape');
    await expect(page.locator('.locker-cluster')).toBeFocused();
    await showMenu(page);
    await page.locator('#parcel-weight').focus();
    await expect(page.locator('.locker-cluster')).toHaveCSS('opacity', '0.3');
    await openMembers();
    await showMenu(page);
    await page.locator('#tracking-tab').focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('.cluster-members')).toHaveCount(0);
    await showMenu(page);
    await page.locator('#quote-tab').click();
    await expect(page.locator('.locker-cluster')).toHaveCSS('opacity', '0.3');
    await openMembers();
    await page.mouse.click(viewport.width - 5, viewport.height - 55);
    await expect(page.locator('.cluster-members')).toHaveCount(0);
    await showMenu(page);
    await page.locator('#parcel-weight').focus();
    await expect(page.locator('.locker-cluster')).toHaveCSS('opacity', '0.3');
    await page.locator('#pickup-clear').click();
    await expect(page.locator('.locker-cluster')).toHaveText('44');
    await openMembers();
    const currentIds = await page
      .locator('.cluster-member-list button')
      .evaluateAll((nodes) => nodes.map((n) => (n as HTMLElement).dataset.id));
    expect(currentIds).not.toContain(secondId);
    await page.keyboard.press('Escape');
    await expect(page.locator('.locker-cluster')).toBeFocused();
    expect(reads).toBe(1);
  });
}

test('tracking edit removes its shared inspection popup immediately', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 480 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await tiles(page);
  const parcel = tracked();
  parcel.locker.location_id = 'Locker de seguimiento';
  await page.route('**/tracking/*', (route) => route.fulfill({ json: parcel }));
  await page.goto('/');
  await showMenu(page);
  await page.locator('#tracking-tab').click();
  await track(page, 1001);
  await page.locator('.tracking-marker').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('.locker-popup')).toContainText(
    'Locker de seguimiento',
  );
  await showMenu(page);
  await page.locator('#tracking-id').fill('');
  await expect(page.locator('.leaflet-popup,.tracking-marker')).toHaveCount(0);
  await expect(page.locator('#tracking-id')).toBeFocused();
});
test('viewport eviction recreates keyboard activation without selecting a role', async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await data(page, [locker(1, 'Reentrada')], false);
  await page.route(photon, (r) =>
    r.fulfill({
      json: places(
        new URL(r.request().url()).searchParams.get('q') === 'Canarias'
          ? place('Canarias', -15.43, 28.12)
          : place('Madrid', -3.7038, 40.4168),
      ),
    }),
  );
  await expect(page.locator('.locker-marker')).toHaveCount(1);
  await showMenu(page);
  await page.locator('#location-query').fill('Canarias');
  await page.locator('#location-results button').click();
  await expect(page.locator('.locker-marker')).toHaveCount(0);
  await showMenu(page);
  await page.locator('#location-query').fill('Madrid');
  await page.locator('#location-results button').click();
  await expect(page.locator('.locker-marker')).toHaveCount(1);
  await page.locator('.locker-marker').focus();
  await page.keyboard.press(' ');
  await expect(page.locator('.locker-popup strong')).toHaveText('Reentrada');
  await expect(page.locator('#pickup-locker')).toHaveAttribute(
    'data-selected-id',
    '',
  );
  await expect(page.locator('#delivery-locker')).toHaveAttribute(
    'data-selected-id',
    '',
  );
});

for (const viewport of [
  { width: 320, height: 568 },
  { width: 375, height: 480 },
  { width: 667, height: 375 },
]) {
  test(`compact mobile menu preserves work and accessible map ${viewport.width}x${viewport.height}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    let reads = 0;
    await tiles(page);
    await page.route('**/lockers', (route) => {
      reads++;
      return route.fulfill({ json: [locker(1)] });
    });
    await page.goto('/');
    const toggle = page.getByRole('button', {
      name: 'Abrir menú',
      exact: true,
    });
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await expect(page.locator('#menu-content')).toBeHidden();
    await expect(page.locator('#available-count')).toHaveText('1');
    await page.screenshot({
      path: `test-results/compact-${viewport.width}-initial.png`,
    });
    await toggle.focus();
    await page.keyboard.press('Enter');
    const footprint = await page.locator('#map-panels').boundingBox();
    expect(footprint!.height).toBeLessThanOrEqual(viewport.height * 0.6 + 1);
    await selectRole(page, 'pickup', 1);
    await page.locator('#parcel-weight').fill('1.001');
    await page.locator('#parcel-weight').press('Escape');
    await expect(page.locator('#menu-toggle')).toBeFocused();
    await expect(page.locator('#menu-content')).toBeHidden();
    // Hidden controls cannot receive keyboard focus.
    await page
      .locator('#parcel-weight')
      .evaluate((node) => (node as HTMLElement).focus());
    await expect(page.locator('#menu-toggle')).toBeFocused();
    await page.keyboard.press('Space');
    await expect(page.locator('#parcel-weight')).toHaveValue('1.001');
    await expect(page.locator('#pickup-locker')).toHaveAttribute(
      'data-selected-id',
      id(1),
    );
    await expect(page.locator('#parcel-weight')).toHaveCSS('font-size', '16px');
    await page.locator('#tracking-tab').click();
    await page.locator('#tracking-id').fill(id(1001));
    await page.locator('#tracking-submit').scrollIntoViewIfNeeded();
    await expect(page.locator('#menu-toggle')).toBeInViewport();
    await page.screenshot({
      path: `test-results/compact-${viewport.width}-expanded.png`,
    });
    await page.locator('#menu-toggle').click();
    await page.locator('#menu-toggle').click();
    await expect(page.locator('#tracking-tab')).toHaveAttribute(
      'aria-selected',
      'true',
    );
    await expect(page.locator('#tracking-id')).toHaveValue(id(1001));
    expect(reads).toBe(1);
    const freeMap = await page.evaluate(() => {
      const menu = document
        .querySelector('#map-panels')!
        .getBoundingClientRect();
      return (
        document
          .elementFromPoint(
            innerWidth / 2,
            (menu.bottom + innerHeight - 30) / 2,
          )
          ?.closest('#map') === document.querySelector('#map')
      );
    });
    expect(freeMap).toBe(true);
    await expect(
      page.getByRole('button', { name: 'Acercar mapa' }),
    ).toBeInViewport();
    await expect(page.locator('.leaflet-control-attribution')).toBeInViewport();
    await page.locator('#menu-toggle').click();
    await page.setViewportSize({ width: 1280, height: 800 });
    await expect(page.locator('#tracking-tab')).toBeFocused();
    await expect(page.locator('#menu-toggle')).toBeHidden();
    await expect(page.locator('#menu-content')).toBeVisible();
    await page.setViewportSize(viewport);
    await expect(page.locator('#menu-toggle')).toBeFocused();
    await expect(page.locator('#menu-content')).toBeHidden();
    await openPanel(page);
    await expect(page.locator('#pickup-clear')).toBeFocused();
    await page.route(photon, (route) =>
      route.fulfill({ json: places(place()) }),
    );
    await page.locator('#location-query').fill('Madrid');
    await page.locator('#location-results button').click();
    expect(await markerHit(page)).toBe(true);
    const markerBox = await page.locator('.search-location').boundingBox();
    const menuBox = await page.locator('#map-panels').boundingBox();
    expect(markerBox!.y).toBeGreaterThan(menuBox!.y + menuBox!.height);
  });
}

test('compact status exposes failure and retry without automatic expansion', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 480 });
  await tiles(page, true);
  let reads = 0;
  await page.route('**/lockers', (route) => {
    reads++;
    return reads === 1
      ? route.fulfill({ status: 503, body: 'unavailable' })
      : route.fulfill({ json: [] });
  });
  await page.goto('/');
  await expect(page.locator('#menu-status')).toContainText('HTTP 503');
  await expect(page.locator('#menu-content')).toBeHidden();
  await showMenu(page);
  await page.locator('#retry').click();
  await page.locator('#menu-toggle').click();
  await expect(page.locator('#menu-status')).toContainText('No hay lockers');
  await expect(page.locator('#menu-status')).toContainText('Fondo del mapa');
  await expect(page.locator('#menu-content')).toBeHidden();
  expect(reads).toBe(2);
});

test('pending mobile tracking survives collapse and its response never reopens menu', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 480 });
  await data(page, [locker(1)]);
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  let reads = 0;
  await page.route('**/tracking/*', async (route) => {
    reads++;
    await pending;
    await route.fulfill({ json: tracked() });
  });
  await page.locator('#tracking-tab').click();
  await page.locator('#tracking-id').fill(id(1001));
  await page.locator('#tracking-submit').click();
  await expect.poll(() => reads).toBe(1);
  await page.locator('#menu-toggle').click();
  release();
  await expect(page.locator('.tracking-marker')).toHaveCount(1);
  await expect(page.locator('#menu-content')).toBeHidden();
  await expect(page.locator('#menu-toggle')).toBeFocused();
  await showMenu(page);
  await expect(page.locator('#tracking-result')).toBeVisible();
  expect(reads).toBe(1);
});

test('mobile results keep polling and reopen without a duplicate submission', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 480 });
  await data(page, [locker(1)]);
  let posts = 0,
    gets = 0;
  let submitted: any;
  await page.route('**/quotations', async (route) => {
    posts++;
    submitted = route.request().postDataJSON();
    await route.fulfill({
      status: 202,
      json: { id: quoteId, status: 'PENDING' },
    });
  });
  await page.route(`**/quotations/${quoteId}`, (route) => {
    gets++;
    return route.fulfill({
      json: quote(submitted, gets === 1 ? 'PENDING' : 'COMPLETED'),
    });
  });
  await fillShipping(page);
  await page.locator('#compare-shipping').click();
  await expect(page.locator('#menu-content')).toBeHidden();
  await expect(page.locator('#results-title')).toBeFocused();
  await expect(page.locator('#quotation-status')).toContainText('finalizada');
  expect(gets).toBe(2);
  await page.screenshot({ path: 'test-results/compact-375-results.png' });
  await page.keyboard.press('Escape');
  await expect(page.locator('#compare-shipping')).toBeFocused();
  await expect(page.locator('#menu-content')).toBeVisible();
  await reopenResults(page);
  await page.locator('#menu-toggle').click();
  await expect(page.locator('#results')).toBeHidden();
  await expect(page.locator('#menu-content')).toBeVisible();
  await reopenResults(page);
  await expect(page.locator('#quotation-offers')).toContainText('12,34');
  expect(posts).toBe(1);
  expect(gets).toBe(2);
});

test('mobile menu responds to touch and Escape dismisses suggestions before menu', async ({
  browser,
}) => {
  const context = await browser.newContext({
    viewport: { width: 375, height: 480 },
    hasTouch: true,
  });
  const page = await context.newPage();
  await tiles(page);
  await page.route('**/lockers', (route) =>
    route.fulfill({ json: [locker(1)] }),
  );
  await page.goto('/');
  await page.locator('#menu-toggle').tap();
  await page.locator('#pickup-locker').fill('Locker');
  await expect(page.locator('#pickup-options button')).toHaveCount(1);
  await page.keyboard.press('Escape');
  await expect(page.locator('#pickup-locker')).toBeFocused();
  await expect(page.locator('#menu-content')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#menu-toggle')).toBeFocused();
  await expect(page.locator('#menu-content')).toBeHidden();
  await page.locator('#menu-toggle').tap();
  await page.locator('#menu-toggle').tap();
  await expect(page.locator('#menu-content')).toBeHidden();
  await context.close();
});

test.describe('mobile inspection alongside quotation results', () => {
  test.use({ hasTouch: true });
  for (const viewport of [
    { width: 375, height: 480 },
    { width: 667, height: 375 },
  ]) {
    test(`keeps whole popup actions and pin clear of live results ${viewport.width}`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await data(page, [locker(1, 'Inspección con resultados')]);
      let posts = 0,
        gets = 0;
      let submitted: any;
      let release!: () => void;
      const pending = new Promise<void>((resolve) => {
        release = resolve;
      });
      await page.route('**/quotations', (route) => {
        posts++;
        submitted = route.request().postDataJSON();
        return route.fulfill({
          status: 202,
          json: { id: quoteId, status: 'PENDING' },
        });
      });
      await page.route(`**/quotations/${quoteId}`, async (route) => {
        gets++;
        if (gets > 1) await pending;
        await route.fulfill({
          json: quote(submitted, gets === 1 ? 'PENDING' : 'COMPLETED'),
        });
      });
      await fillShipping(page);
      await page.locator('#compare-shipping').click();
      await expect.poll(() => gets).toBe(2);
      const marker = page.locator('.locker-marker');
      await marker.focus();
      await page.keyboard.press('Enter');
      await expect(page.locator('#results')).toBeVisible();
      await expect(page.locator('#results .results-scroll')).toBeHidden();
      async function hit(selector: string) {
        return page.locator(selector).evaluate((node) => {
          const box = node.getBoundingClientRect();
          return node.contains(
            document.elementFromPoint(
              box.x + box.width / 2,
              box.y + box.height / 2,
            ),
          );
        });
      }
      async function geometry() {
        const bounds = await page.evaluate(() => {
          const rect = (selector: string) =>
            document.querySelector(selector)!.getBoundingClientRect();
          return {
            popup: rect('.leaflet-popup').toJSON(),
            pin: rect('.locker-marker').toJSON(),
            results: rect('#results').toJSON(),
            menu: rect('#map-panels').toJSON(),
            zoom: rect('.leaflet-control-zoom').toJSON(),
          };
        });
        expect(bounds.popup.y).toBeGreaterThanOrEqual(
          Math.max(bounds.menu.bottom, bounds.zoom.bottom) + 11,
        );
        expect(bounds.pin.bottom).toBeLessThanOrEqual(bounds.results.y - 11);
        expect(await hit('.locker-marker')).toBe(true);
        expect(await hit('#menu-toggle')).toBe(true);
        expect(await hit('.leaflet-control-zoom-in')).toBe(true);
        expect(await hit('#close-results')).toBe(true);
        await expect(page.locator('#results-title')).toBeInViewport();
        await expect(
          page.locator('.leaflet-control-attribution'),
        ).toBeInViewport();
        for (const action of await page
          .locator('.popup-role-actions button')
          .all()) {
          await action.focus();
          await action.evaluate((node) =>
            node.scrollIntoView({ block: 'nearest' }),
          );
          await expect(action).toBeFocused();
          expect(
            await action.evaluate((node) => {
              const box = node.getBoundingClientRect();
              const content = node
                .closest('.locker-popup')!
                .getBoundingClientRect();
              return (
                box.height >= 48 &&
                box.top >= content.top - 1 &&
                box.bottom <= content.bottom + 1 &&
                node.contains(
                  document.elementFromPoint(
                    box.x + box.width / 2,
                    box.y + box.height / 2,
                  ),
                )
              );
            }),
          ).toBe(true);
        }
      }
      await geometry();
      release();
      await expect(page.locator('#quotation-status')).toContainText(
        'finalizada',
      );
      await page.screenshot({
        path: `test-results/compact-results-popup-${viewport.width}.png`,
      });
      await page.setViewportSize(
        viewport.width === 375
          ? { width: 667, height: 375 }
          : { width: 375, height: 480 },
      );
      await geometry();
      await page.locator('.leaflet-popup-close-button').tap();
      await expect(marker).toBeFocused();
      await expect(page.locator('#results .results-scroll')).toBeVisible();
      await expect(page.locator('#quotation-offers')).toContainText('12,34');
      expect(await hit('.locker-marker')).toBe(true);
      const normal = await page.locator('#results').boundingBox();
      expect(normal!.height).toBeCloseTo(
        page.viewportSize()!.height * 0.5 - 12,
      );
      await marker.press('Enter');
      await geometry();
      await page
        .getByRole('button', { name: 'Locker de destino', exact: true })
        .tap();
      await expect(page.locator('#delivery-clear')).toBeFocused();
      await expect(page.locator('#menu-content')).toBeVisible();
      await expect(page.locator('#results')).toBeHidden();
      expect(posts).toBe(1);
      expect(gets).toBe(2);
    });
  }
});
