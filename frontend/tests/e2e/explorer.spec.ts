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
async function data(page: Page, payload: unknown) {
  await tiles(page);
  await page.route('http://127.0.0.1:8765/lockers', (route) =>
    route.fulfill({ json: payload }),
  );
  await page.goto('/');
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
test('desktop visual inspection', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await data(page, [
    locker(1, 'Madrid · Atocha'),
    locker(2, 'Palma · Centro', { latitude: 39.57, longitude: 2.65 }),
    locker(3, 'Tenerife · La Laguna', { latitude: 28.46, longitude: -16.25 }),
  ]);
  await expect(page.locator('#available-count')).toHaveText('3');
  await page.screenshot({ path: 'test-results/desktop.png', fullPage: true });
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
