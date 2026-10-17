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
  if (open)
    await page
      .getByRole('button', { name: 'Ver lockers', exact: true })
      .click();
}
test('real cross-origin FastAPI middleware allows exact origin and denies another', async ({
  page,
  context,
}) => {
  await tiles(page); // The API request is intentionally never intercepted here.
  const response = page.waitForResponse('http://127.0.0.1:8765/lockers');
  await page.goto('/');
  await expect(
    page.getByRole('status').filter({ hasText: 'No hay lockers' }),
  ).toBeVisible();
  expect((await response).headers()['access-control-allow-origin']).toBe(
    'http://127.0.0.1:4321',
  );
  const denied = await context.newPage();
  await tiles(denied);
  await denied.goto('http://localhost:4321/');
  await expect(denied.locator('#status')).toContainText(
    'conectar con el servicio de lockers',
  );
  await expect(
    denied.getByRole('button', { name: 'Reintentar consulta' }),
  ).toBeVisible();
  expect(
    await denied.evaluate(async () => {
      try {
        await fetch('http://127.0.0.1:8765/lockers', { credentials: 'omit' });
        return 'readable';
      } catch {
        return 'blocked';
      }
    }),
  ).toBe('blocked');
});
test('Spain view includes territories, keeps positions and permits shared-coordinate selection', async ({
  page,
}) => {
  const positions = [
    [40.4168, -3.7038],
    [39.5696, 2.6502],
    [28.4636, -16.2518],
    [35.8894, -5.3213],
    [35.2923, -2.9381],
    [40.4168, -3.7038],
  ];
  await data(
    page,
    positions.map(([latitude, longitude], i) =>
      locker(
        i + 1,
        ['Madrid', 'Palma', 'Tenerife', 'Ceuta', 'Melilla', 'Madrid segundo'][
          i
        ],
        { latitude, longitude },
      ),
    ),
  );
  await expect(page.locator('#available-count')).toHaveText('6');
  await expect(page.locator('#positioned-count')).toHaveText('6');
  const markers = page.locator('.locker-marker');
  await expect(markers).toHaveCount(6);
  await page.getByRole('button', { name: 'Ver España', exact: true }).click();
  const mapBox = await page.locator('#map').boundingBox();
  for (let i = 0; i < 6; i++) {
    const box = await markers.nth(i).boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(mapBox!.x - 20);
    expect(box!.x).toBeLessThan(mapBox!.x + mapBox!.width);
    expect(box!.y).toBeGreaterThanOrEqual(mapBox!.y - 40);
    expect(box!.y).toBeLessThan(mapBox!.y + mapBox!.height);
  }
  for (let i = 0; i < 6; i++) {
    await page.locator(`[data-id="${id(i + 1)}"]`).click();
    await expect(page.locator('#locker-detail')).toContainText(id(i + 1));
    await expect(page.locator('.leaflet-popup')).toHaveCount(1);
    await expect(page.locator('.leaflet-popup')).toContainText(id(i + 1));
    await page.getByRole('button', { name: 'Ver España' }).click();
  }
  await page.getByRole('button', { name: 'Cerrar listado de lockers' }).click();
  await page.locator('.locker-marker').nth(1).click();
  await expect(page.locator('#locker-detail')).toContainText(id(2));
});
test('nullable labels, postal text and untrusted markup stay literal in list, detail and popup', async ({
  page,
}) => {
  const address = {
    country_code: 'ES',
    postal_code: '01001',
    province: 'Álava',
    city: 'Vitoria',
    street: '<img src=x onerror="window.pwned=1">',
    street_number: '2',
  };
  await data(page, [
    { ...locker(1, null), address },
    locker(2, null, null),
    locker(3, '<script>window.pwned=1</script>'),
  ]);
  await expect(page.locator('#locker-list')).toContainText('01001');
  await expect(page.locator('#locker-list')).toContainText(id(2));
  await page.locator(`[data-id="${id(3)}"]`).click();
  await expect(page.locator('#locker-detail')).toContainText(
    '<script>window.pwned=1</script>',
  );
  await expect(page.locator('.leaflet-popup')).toContainText(
    '<script>window.pwned=1</script>',
  );
  expect(await page.evaluate(() => 'pwned' in window)).toBe(false);
  await expect(
    page.locator(
      '#locker-list img, #locker-detail script, .leaflet-popup script',
    ),
  ).toHaveCount(0);
});
test('all unmapped lockers remain usable and distinct from an empty response', async ({
  page,
}) => {
  await data(page, [
    locker(1, 'Sin posición', null),
    locker(2, 'Incompleto', { latitude: 40 }),
  ]);
  await expect(page.locator('#available-count')).toHaveText('2');
  await expect(page.locator('#positioned-count')).toHaveText('0');
  await expect(page.locator('#status')).toContainText(
    'Ninguno tiene coordenadas',
  );
  await expect(page.locator('.locker-marker')).toHaveCount(0);
  await page.locator(`[data-id="${id(1)}"]`).click();
  await expect(page.locator('#locker-detail')).toContainText(
    'Sin coordenadas válidas',
  );
});
test('loading, refresh failure, retry and capacity changes replace stale availability with GET only', async ({
  page,
}) => {
  await tiles(page);
  let count = 0;
  const methods: string[] = [];
  await page.route('http://127.0.0.1:8765/lockers', async (route) => {
    methods.push(route.request().method());
    count++;
    if (count === 1) {
      await new Promise((resolve) => setTimeout(resolve, 250));
      await route.fulfill({ json: [locker(1)] });
    } else if (count === 2)
      await route.fulfill({ status: 503, body: 'unavailable' });
    else if (count === 3) await route.fulfill({ json: [locker(1)] });
    else
      await route.fulfill({
        json: [
          { ...locker(1), compartments: [{ enabled: true, occupied: true }] },
        ],
      });
  });
  await page.goto('/');
  await expect(page.locator('#status')).toContainText('Consultando');
  await page.getByRole('button', { name: 'Ver lockers', exact: true }).click();
  await expect(page.locator('#locker-list button')).toHaveCount(1);
  await page.locator('#locker-list button').click();
  await page.getByRole('button', { name: 'Actualizar' }).click();
  await expect(page.locator('#status')).toContainText('HTTP 503');
  await expect(page.locator('#locker-list button')).toHaveCount(0);
  await expect(page.locator('.locker-marker')).toHaveCount(0);
  await expect(page.locator('#locker-detail')).toBeHidden();
  await page.getByRole('button', { name: 'Reintentar consulta' }).click();
  await expect(page.locator('#locker-list button')).toHaveCount(1);
  await page.locator('#locker-list button').click();
  await page.getByRole('button', { name: 'Actualizar' }).click();
  await expect(page.locator('#status')).toContainText(
    'No hay lockers disponibles',
  );
  await expect(page.locator('#locker-detail')).toBeHidden();
  expect(methods).toEqual(['GET', 'GET', 'GET', 'GET']);
});
test('tile failure preserves keyboard details and 375px layout', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 900 });
  await tiles(page, true);
  await page.route('http://127.0.0.1:8765/lockers', (route) =>
    route.fulfill({ json: [locker(1, 'Nombre muy largo '.repeat(10))] }),
  );
  await page.goto('/');
  await expect(page.locator('#tile-warning')).toBeVisible();
  await page.getByRole('button', { name: 'Ver lockers', exact: true }).click();
  const button = page.locator('#locker-list button');
  await button.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#locker-detail')).toContainText(id(1));
  await expect(button).toBeFocused();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await expect(page.getByRole('link', { name: 'OpenStreetMap' })).toBeVisible();
  await page.screenshot({ path: 'test-results/mobile.png', fullPage: true });
});
test('malformed data and network failures remain errors with retry', async ({
  page,
}) => {
  await data(page, { invalid: 'not a collection' });
  await expect(page.locator('#status')).toContainText(
    'datos de lockers no válidos',
  );
  await expect(page.locator('#retry')).toBeVisible();
  await page.unroute('http://127.0.0.1:8765/lockers');
  await page.route('http://127.0.0.1:8765/lockers', (route) => route.abort());
  await page.locator('#retry').click();
  await expect(page.locator('#status')).toContainText(
    'conectar con el servicio de lockers',
  );
  await expect(page.locator('#locker-list button')).toHaveCount(0);
});

test('a stalled read times out visibly and allows another attempt', async ({
  page,
}) => {
  await tiles(page);
  await page.route('http://127.0.0.1:8765/lockers', () => {});
  await page.goto('/');
  await expect(page.locator('#status')).toContainText('cinco segundos', {
    timeout: 7000,
  });
  await expect(page.locator('#retry')).toBeVisible();
  await expect(page.locator('#refresh')).toBeEnabled();
});

test('keyboard selection reveals unmapped details inside a long scrollable list', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await data(
    page,
    Array.from({ length: 20 }, (_, i) =>
      locker(i + 1, `Locker ${i + 1}`, null),
    ),
  );
  for (const n of [1, 20, 10]) {
    const button = page.locator(`[data-id="${id(n)}"]`);
    await button.focus();
    await page.keyboard.press('Enter');
    await expect(button).toBeFocused();
    const detail = page.locator('#locker-detail');
    await expect(detail).toContainText(id(n));
    const geometry = await detail.evaluate((node) => {
      const detail = node.getBoundingClientRect();
      const panel = document.querySelector('#results')!.getBoundingClientRect();
      return {
        top: detail.top,
        bottom: detail.bottom,
        panelTop: panel.top,
        panelBottom: panel.bottom,
        viewportHeight: window.innerHeight,
      };
    });
    expect(geometry.top).toBeGreaterThanOrEqual(
      Math.max(geometry.panelTop, 0) - 1,
    );
    expect(geometry.bottom).toBeLessThanOrEqual(
      Math.min(geometry.panelBottom, geometry.viewportHeight) + 1,
    );
  }
});

async function fullViewport(page: Page, width: number, height: number) {
  const box = await page.locator('#map').boundingBox();
  expect(box).toEqual({ x: 0, y: 0, width, height });
  expect(
    await page.evaluate(() => ({
      width: document.documentElement.scrollWidth,
      height: document.documentElement.scrollHeight,
    })),
  ).toEqual({ width, height });
  await expect(page.locator('header, footer')).toHaveCount(0);
}
function overlaps(
  a: { x: number; y: number; width: number; height: number },
  b: { x: number; y: number; width: number; height: number },
) {
  return (
    a.x < b.x + b.width &&
    a.x + a.width > b.x &&
    a.y < b.y + b.height &&
    a.y + a.height > b.y
  );
}
for (const viewport of [
  { width: 1280, height: 800, name: 'desktop' },
  { width: 375, height: 667, name: 'mobile' },
  { width: 375, height: 480, name: 'mobile-short' },
]) {
  test(`full viewport, compact parcel menu and independent list geometry ${viewport.name}`, async ({
    page,
  }) => {
    await page.setViewportSize({
      width: viewport.width,
      height: viewport.height,
    });
    await data(
      page,
      [
        locker(1, 'Madrid · Atocha'),
        locker(2, 'Palma · Centro', { latitude: 39.57, longitude: 2.65 }),
        locker(3, 'Sin coordenadas', null),
      ],
      false,
    );
    await expect(page.locator('#available-count')).toHaveText('3');
    await expect(page.locator('#results')).toBeHidden();
    await fullViewport(page, viewport.width, viewport.height);
    const parcel = await page.locator('.parcel-panel').boundingBox();
    expect(parcel!.x).toBeLessThan(35);
    expect(parcel!.y).toBeLessThan(35);
    for (const label of [
      'Largo (cm)',
      'Ancho (cm)',
      'Alto (cm)',
      'Peso (kg)',
    ]) {
      const input = page.getByRole('spinbutton', { name: label, exact: true });
      await expect(input).toHaveValue('');
      await expect(input).toBeVisible();
    }
    const zoom = await page.locator('.leaflet-control-zoom').boundingBox();
    expect(overlaps(parcel!, zoom!)).toBe(false);
    await expect(
      page.getByRole('button', { name: 'Acercar mapa' }),
    ).toBeVisible();
    await expect(
      page.getByRole('link', { name: 'OpenStreetMap' }),
    ).toBeVisible();
    await page.screenshot({ path: `test-results/${viewport.name}-closed.png` });
    await page
      .getByRole('button', { name: 'Ver lockers', exact: true })
      .click();
    await expect(page.locator('#close-results')).toBeFocused();
    await expect(page.locator('#open-results')).toHaveAttribute(
      'aria-expanded',
      'true',
    );
    await fullViewport(page, viewport.width, viewport.height);
    const resultBox = await page.locator('#results').boundingBox();
    const leftBox = await page.locator('#map-panels').boundingBox();
    const attribution = await page
      .locator('.leaflet-control-attribution')
      .boundingBox();
    const openZoom = await page.locator('.leaflet-control-zoom').boundingBox();
    expect(overlaps(resultBox!, leftBox!)).toBe(false);
    expect(overlaps(resultBox!, attribution!)).toBe(false);
    expect(overlaps(resultBox!, openZoom!)).toBe(false);
    await page.screenshot({ path: `test-results/${viewport.name}-open.png` });
    await page.locator(`[data-id="${id(1)}"]`).click();
    const selectedMarker = page.locator(
      '.locker-marker[title="Madrid · Atocha"]',
    );
    expect(
      await selectedMarker.evaluate((node) => {
        const rect = node.getBoundingClientRect();
        return (
          document
            .elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2)
            ?.closest('.locker-marker') === node
        );
      }),
    ).toBe(true);
    await expect(page.locator('#locker-detail')).toContainText(id(1));
    await page.screenshot({
      path: `test-results/${viewport.name}-selected.png`,
    });
    await page.keyboard.press('Escape');
    await expect(page.locator('#results')).toBeHidden();
    await expect(page.locator('#open-results')).toBeFocused();
    await page.locator('#skip-results').focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('#results')).toBeVisible();
  });
}

test('parcel fields accept local positive decimals without changing map, availability or requests', async ({
  page,
}) => {
  await data(page, [locker(1)], false);
  await expect(page.locator('#available-count')).toHaveText('1');
  let extraRequests = 0;
  page.on('request', (request) => {
    if (!request.url().startsWith('https://tile.openstreetmap.org/'))
      extraRequests++;
  });
  const markerBefore = await page.locator('.locker-marker').boundingBox();
  const mapPaneBefore = await page
    .locator('.leaflet-map-pane')
    .getAttribute('style');
  const inputs = page.locator('#parcel-form input');
  for (const [i, value] of ['25.5', '15', '10', '2.5'].entries()) {
    await inputs.nth(i).fill(value);
    expect(
      await inputs
        .nth(i)
        .evaluate((node: HTMLInputElement) => node.checkValidity()),
    ).toBe(true);
  }
  await inputs.nth(0).focus();
  await page.keyboard.press('Tab');
  await expect(inputs.nth(1)).toBeFocused();
  await page.keyboard.press('Enter');
  await inputs.nth(2).fill('0');
  await expect(inputs.nth(2)).toHaveAttribute('aria-invalid', 'true');
  await expect(page.locator('#parcel-height-error')).toBeVisible();
  await inputs.nth(2).fill('-1.5');
  expect(
    await inputs
      .nth(2)
      .evaluate((node: HTMLInputElement) => node.checkValidity()),
  ).toBe(false);
  await inputs.nth(2).fill('');
  await expect(inputs.nth(2)).toHaveAttribute('aria-invalid', 'false');
  await inputs.nth(2).fill('0.005');
  expect(
    await inputs
      .nth(2)
      .evaluate((node: HTMLInputElement) => node.checkValidity()),
  ).toBe(true);
  await page.locator('.parcel-heading').hover();
  const heading = await page.locator('.parcel-heading').boundingBox();
  await page.mouse.move(heading!.x + 20, heading!.y + 15);
  await page.mouse.down();
  await page.mouse.move(heading!.x + 100, heading!.y + 45);
  await page.mouse.up();
  await page.mouse.wheel(0, 180);
  await expect(page.locator('#available-count')).toHaveText('1');
  expect(await page.locator('.locker-marker').boundingBox()).toEqual(
    markerBefore,
  );
  expect(await page.locator('.leaflet-map-pane').getAttribute('style')).toBe(
    mapPaneBefore,
  );
  expect(extraRequests).toBe(0);
  await page.getByRole('button', { name: 'Ver lockers', exact: true }).click();
  await page.locator('#close-results').click();
  await page.locator('#refresh').click();
  await expect(page.locator('#available-count')).toHaveText('1');
  await expect(inputs.nth(0)).toHaveValue('25.5');
  await expect(inputs.nth(3)).toHaveValue('2.5');
  expect(extraRequests).toBe(1);
  expect(
    await page.evaluate(() => ({
      local: localStorage.length,
      session: sessionStorage.length,
    })),
  ).toEqual({ local: 0, session: 0 });
});

test('marker selection opens details; refreshing a closed selected list keeps it closed', async ({
  page,
}) => {
  await data(page, [locker(1, 'Madrid')], false);
  await page.locator('.locker-marker').click();
  await expect(page.locator('#results')).toBeVisible();
  await expect(page.locator('#locker-detail')).toContainText(id(1));
  await page.locator('#close-results').click();
  await page.locator('#refresh').click();
  await expect(page.locator('#available-count')).toHaveText('1');
  await expect(page.locator('#results')).toBeHidden();
  await expect(page.locator('#open-results')).toHaveAttribute(
    'aria-expanded',
    'false',
  );
});

test('short mobile panels scroll internally without moving the map or losing local input', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 480 });
  await data(page, [locker(1)], false);
  await expect(page.locator('#available-count')).toHaveText('1');
  await page.getByRole('spinbutton', { name: 'Largo (cm)' }).fill('25.5');
  const before = await page.locator('.leaflet-map-pane').getAttribute('style');
  const markerBefore = await page.locator('.locker-marker').boundingBox();
  let requests = 0;
  page.on('request', (request) => {
    if (!request.url().startsWith('https://tile.openstreetmap.org/'))
      requests++;
  });
  await page.locator('.parcel-heading').hover();
  await page.mouse.wheel(0, 250);
  await expect
    .poll(() => page.locator('#map-panels').evaluate((node) => node.scrollTop))
    .toBeGreaterThan(0);
  await expect(page.locator('#refresh')).toBeInViewport();
  expect(await page.locator('.leaflet-map-pane').getAttribute('style')).toBe(
    before,
  );
  expect(await page.locator('.locker-marker').boundingBox()).toEqual(
    markerBefore,
  );
  await page.getByRole('spinbutton', { name: 'Largo (cm)' }).focus();
  await page.keyboard.press('Tab');
  await expect(
    page.getByRole('spinbutton', { name: 'Ancho (cm)' }),
  ).toBeFocused();
  await expect(
    page.getByRole('spinbutton', { name: 'Largo (cm)' }),
  ).toHaveValue('25.5');
  expect(requests).toBe(0);
});

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
        .locator('.parcel-panel')
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
    await expect(page.locator('#search-results button')).toHaveCount(1);
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
    await expect(page.locator('#search-results button').first()).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(query).toHaveValue('01001 Vitoria');
    await expect(query).toBeFocused();
    await expect(query).toHaveAttribute('aria-expanded', 'false');
    expect(
      await page
        .locator('#search-suggestions')
        .evaluate((node: HTMLElement) => node.inert),
    ).toBe(true);
    await expect(page.locator('#search-suggestions')).toBeHidden();
    expect(await markerHit(page)).toBe(true);
    await expect(page.locator('#results')).toBeHidden();
    await page.waitForTimeout(400);
    expect(geoReads).toBe(1);
    await page.screenshot({
      path: `test-results/${viewport.name}-menu-selected.png`,
    });
    await page
      .getByRole('button', { name: 'Ver lockers', exact: true })
      .click();
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
    await expect(page.locator('#search-results button')).toHaveCount(5);
    await page.locator('#search-results button').nth(1).click();
    await expect(query).toHaveValue('Plaza Mayor, Madrid');
    await expect(page.locator('#search-suggestions')).toBeHidden();
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
  await expect(page.locator('#search-results button')).toHaveCount(1);
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
  await expect(page.locator('#search-status')).toContainText('HTTP 503');
  await expect(page.locator('#status')).toContainText('1 locker disponible');
  await page.getByRole('button', { name: 'Reintentar búsqueda' }).click();
  await expect(page.locator('#search-status')).toContainText(
    'No se han encontrado',
  );
  await query.fill('Madrid centro');
  await expect(page.locator('#search-status')).toContainText(
    'respuesta no válida',
  );
  await page.getByRole('button', { name: 'Reintentar búsqueda' }).focus();
  await page.keyboard.press('Enter');
  await expect(
    page.getByRole('combobox', { name: 'Dirección o código postal' }),
  ).toBeFocused();
  await expect(page.locator('#search-results button')).toHaveCount(1);
  await page.locator('#search-results button').click();
  await page.unroute(photon);
  await page.route(photon, () => {});
  await query.fill('Tardará');
  await expect(page.locator('#search-status')).toContainText('cinco segundos', {
    timeout: 7000,
  });
  await expect(page.locator('#search-retry')).toBeVisible();
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
    await expect(page.locator('#search-suggestions')).toBeHidden();
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
  await expect(page.locator('#search-results button')).toHaveText(
    'Última ubicación',
  );
  await page.evaluate(() => Reflect.get(window, 'completeOldSearch')());
  await expect(page.locator('#search-results button')).toHaveText(
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
  await expect(page.locator('#search-results button')).toHaveCount(2);
  await query.press('ArrowDown');
  await expect(page.locator('#search-results button').first()).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(query).toBeFocused();
  expect(
    await page
      .locator('#search-suggestions')
      .evaluate((node: HTMLElement) => node.inert),
  ).toBe(true);
  await page
    .locator('#search-results button')
    .first()
    .evaluate((node) => node.focus());
  await expect(query).toBeFocused();
  await query.press('Tab');
  await expect(
    page.getByRole('spinbutton', { name: 'Largo (cm)' }),
  ).toBeFocused();
  await query.fill('Madrid nuevo');
  await expect(page.locator('#search-results button')).toHaveCount(2);
  await expect(query).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('#search-suggestions')).toHaveCSS('opacity', '1');
  await expect(page.locator('#search-suggestions')).not.toHaveAttribute(
    'hidden',
  );
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(page.locator('#search-suggestions')).toHaveCSS(
    'transition-duration',
    '0s',
  );
  await query.press('Escape');
  expect(
    await page
      .locator('#search-suggestions')
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
    await expect(page.locator('#search-results button')).toHaveCount(1);
    await page.locator('#search-results button').tap();
    await expect(query).toHaveValue('Gran Vía, Madrid');
    await expect(query).toBeFocused();
    await expect(page.locator('#search-suggestions')).toBeHidden();
    expect(await markerHit(page)).toBe(true);
    await page.waitForTimeout(400);
    expect(requests).toBe(1);
  } finally {
    await context.close();
  }
});

test('wheel zoom works in both directions, Spain is wider and empty refresh preserves navigation', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  let reads = 0;
  await tiles(page);
  await page.route('http://127.0.0.1:8765/lockers', (route) => {
    reads++;
    return route.fulfill({
      json:
        reads === 1
          ? [
              locker(1),
              locker(2, 'Valencia', { latitude: 39.47, longitude: -0.38 }),
            ]
          : [],
    });
  });
  await page.goto('/');
  await expect(page.locator('.locker-marker')).toHaveCount(2);
  const distance = async () => {
    const boxes = await page.locator('.locker-marker').evaluateAll((nodes) =>
      nodes.map((node) => {
        const box = node.getBoundingClientRect();
        return { x: box.x, y: box.y };
      }),
    );
    return Math.hypot(boxes[1]!.x - boxes[0]!.x, boxes[1]!.y - boxes[0]!.y);
  };
  const initial = await distance();
  await page.getByRole('button', { name: 'Ver España', exact: true }).click();
  await expect.poll(distance).toBeLessThan(initial);
  await expect(page.locator('.leaflet-map-pane')).not.toHaveClass(
    /leaflet-zoom-anim/,
  );
  const wide = await distance();
  await page.mouse.move(850, 600);
  await page.mouse.wheel(0, -300);
  await expect.poll(distance).toBeGreaterThan(wide);
  await expect(page.locator('.leaflet-map-pane')).not.toHaveClass(
    /leaflet-zoom-anim/,
  );
  const close = await distance();
  await page.mouse.wheel(0, 300);
  await expect.poll(distance).toBeLessThan(close);
  await expect(page.locator('.leaflet-map-pane')).not.toHaveClass(
    /leaflet-zoom-anim/,
  );
  await page.mouse.move(800, 550);
  await page.mouse.down();
  await page.mouse.move(860, 580, { steps: 5 });
  await page.mouse.up();
  await expect(page.locator('.leaflet-map-pane')).not.toHaveClass(
    /leaflet-pan-anim/,
  );
  const before = await page.locator('.leaflet-map-pane').getAttribute('style');
  await page.locator('#refresh').click();
  await expect(page.locator('#available-count')).toHaveText('0');
  expect(await page.locator('.leaflet-map-pane').getAttribute('style')).toBe(
    before,
  );
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
  await expect(page.locator('#search-results button')).toHaveCount(2);
  await page.locator('#search-results button').nth(1).click();
  await expect(query).toHaveValue('Centro');
  await expect(page.locator('#search-suggestions')).toBeHidden();
  expect(await markerHit(page)).toBe(true);
});
