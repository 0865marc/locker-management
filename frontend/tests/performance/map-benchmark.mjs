import { chromium } from '@playwright/test';

// Run against a static build with PUBLIC_API_BASE_URL=http://127.0.0.1:8765.
// The API and tiles are intercepted so this measures local rendering, not network.
// Write JSONL to a file and compare medians from the same machine/browser.
const baseURL = process.argv[2] ?? 'http://127.0.0.1:4328';
const variant = process.argv[3] ?? 'current';
const counts = (process.env.BENCH_COUNTS ?? '250,1000,5000')
  .split(',')
  .map(Number);
const patterns = (process.env.BENCH_PATTERNS ?? 'spread,dense').split(',');
const runs = Number(process.env.BENCH_RUNS ?? 3);
if (
  counts.some((n) => !Number.isSafeInteger(n) || n < 1) ||
  !Number.isSafeInteger(runs) ||
  runs < 1 ||
  patterns.some((p) => !['spread', 'dense'].includes(p))
) {
  throw new Error(
    'Use positive integer BENCH_COUNTS/BENCH_RUNS and spread,dense BENCH_PATTERNS.',
  );
}
const browser = await chromium.launch({
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined,
  headless: true,
});
const tile = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aG1kAAAAASUVORK5CYII=',
  'base64',
);
const uuid = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
try {
  for (const width of [1280, 375])
    for (const pattern of patterns)
      for (const count of counts)
        for (let run = 1; run <= runs; run++) {
          const page = await browser.newPage({
            viewport: { width, height: width === 1280 ? 800 : 480 },
          });
          const cdp = await page.context().newCDPSession(page);
          await cdp.send('Performance.enable');
          const payload = Array.from({ length: count }, (_, i) => ({
            id: uuid(i + 1),
            location_id: i ? `Locker ${i + 1}` : 'Benchmark origen',
            active: true,
            address: {
              country_code: 'ES',
              postal_code: '28001',
              province: 'Madrid',
              city: 'Madrid',
              street: 'Calle demo',
              street_number: '1',
            },
            coordinates:
              i === 0
                ? { latitude: 40.4168, longitude: -3.7038 }
                : pattern === 'spread'
                  ? {
                      latitude: 36 + ((i * 7919) % 7900) / 1000,
                      longitude: -9 + ((i * 3571) % 12000) / 1000,
                    }
                  : {
                      latitude: 40.4168 + ((i * 7919) % 1000) / 1000000,
                      longitude: -3.7038 + ((i * 3571) % 1000) / 1000000,
                    },
            compartments: [{ enabled: true, occupied: false }],
          }));
          await page.route('https://tile.openstreetmap.org/**', (r) =>
            r.fulfill({ contentType: 'image/png', body: tile }),
          );
          await page.route('http://127.0.0.1:8765/lockers', (r) =>
            r.fulfill({ json: payload }),
          );
          await page.addInitScript(() => {
            window.bench = { long: [], apiAt: 0 };
            new PerformanceObserver((list) =>
              window.bench.long.push(
                ...list
                  .getEntries()
                  .map((e) => ({ start: e.startTime, duration: e.duration })),
              ),
            ).observe({ type: 'longtask', buffered: true });
            const original = window.fetch;
            window.fetch = async (...args) => {
              const response = await original(...args);
              if (String(args[0]).endsWith('/lockers'))
                window.bench.apiAt = performance.now();
              return response;
            };
          });
          await page.goto(baseURL);
          await page.waitForFunction(
            (n) =>
              document.querySelector('#available-count')?.textContent ===
                String(n) && document.querySelector('.leaflet-marker-icon'),
            count,
          );
          const load = await page.evaluate(
            () =>
              new Promise((resolve) =>
                requestAnimationFrame(() =>
                  requestAnimationFrame(() =>
                    resolve({
                      readyMs: performance.now() - window.bench.apiAt,
                      dom: document.querySelectorAll('*').length,
                      icons: document.querySelectorAll('.leaflet-marker-icon')
                        .length,
                      initialLongTasks: window.bench.long.length,
                      maxInitialLongMs: Math.max(
                        0,
                        ...window.bench.long.map((e) => e.duration),
                      ),
                    }),
                  ),
                ),
              ),
          );
          // Keep the same real locker directly inspectable in both implementations.
          // Selecting only an origin does not change the camera.
          await page.locator('#pickup-locker').fill('Benchmark origen');
          await page.locator(`#pickup-options [data-id="${uuid(1)}"]`).click();
          await page.waitForFunction(
            (id) =>
              document.querySelector('#pickup-locker')?.dataset.selectedId ===
              id,
            uuid(1),
          );
          await page.waitForTimeout(400);
          const animation = await page.evaluate(async () => {
            const marker = [
              ...document.querySelectorAll('.leaflet-marker-icon'),
            ].find((n) => n.getAttribute('title') === 'Benchmark origen');
            if (!marker) throw new Error('Benchmark origin marker missing');
            const start = performance.now();
            const samples = [];
            let previous = start;
            const done = new Promise((resolve) => {
              function frame(now) {
                samples.push(Math.max(0, now - previous));
                previous = now;
                if (now - start < 650) requestAnimationFrame(frame);
                else resolve();
              }
              requestAnimationFrame(frame);
            });
            marker.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            const handlerMs = performance.now() - start;
            await done;
            if (!document.querySelector('.leaflet-popup'))
              throw new Error('Benchmark popup did not open');
            const sorted = [...samples].sort((a, b) => a - b);
            return {
              handlerMs,
              frameMax: Math.max(...samples),
              frameP95: sorted[Math.ceil(sorted.length * 0.95) - 1],
              framesOver32: samples.filter((n) => n > 32).length,
              frames: samples.length,
            };
          });
          await cdp.send('HeapProfiler.collectGarbage');
          const { metrics } = await cdp.send('Performance.getMetrics');
          const { nodes } = await cdp.send('Memory.getDOMCounters');
          const m = Object.fromEntries(metrics.map((m) => [m.name, m.value]));
          console.log(
            JSON.stringify({
              variant,
              width,
              pattern,
              count,
              run,
              ...load,
              ...animation,
              heapMB: m.JSHeapUsedSize / 1048576,
              retainedDOMNodes: nodes,
            }),
          );
          await page.close();
        }
} finally {
  await browser.close();
}
