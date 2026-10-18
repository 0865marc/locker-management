import { chromium } from '@playwright/test';

// Supplemental CPU/retention diagnostic for the clustered implementation.
// Reduced motion isolates UI/index work; map-benchmark.mjs measures animation.
const baseURL = process.argv[2] ?? 'http://127.0.0.1:4328';
const count = Number(process.env.BENCH_COUNT ?? 5000);
const runs = Number(process.env.BENCH_RUNS ?? 3);
if (
  !Number.isSafeInteger(count) ||
  count < 25 ||
  !Number.isSafeInteger(runs) ||
  runs < 1
)
  throw new Error(
    'BENCH_COUNT must be at least 25; BENCH_RUNS must be positive.',
  );
const browser = await chromium.launch({
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined,
  headless: true,
});
const tile = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aG1kAAAAASUVORK5CYII=',
  'base64',
);
const uuid = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const median = (samples) =>
  [...samples].sort((a, b) => a - b)[Math.floor(samples.length / 2)];
async function timedClick(locator) {
  return locator.evaluate(async (node) => {
    const start = performance.now();
    node.click();
    const handlerMs = performance.now() - start;
    await new Promise((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(resolve)),
    );
    return { handlerMs, settledMs: performance.now() - start };
  });
}
async function memory(page, cdp) {
  await cdp.send('HeapProfiler.collectGarbage');
  const { nodes, jsEventListeners } = await cdp.send('Memory.getDOMCounters');
  const { metrics } = await cdp.send('Performance.getMetrics');
  return {
    nodes,
    listeners: jsEventListeners,
    heapMB: metrics.find((m) => m.name === 'JSHeapUsedSize').value / 1048576,
    connectedNodes: await page.locator('*').count(),
  };
}
try {
  for (const width of [1280, 375])
    for (const pattern of ['spread', 'coincident'])
      for (let run = 1; run <= runs; run++) {
        const page = await browser.newPage({
          viewport: { width, height: width === 1280 ? 800 : 480 },
          reducedMotion: 'reduce',
        });
        const errors = [];
        page.on('pageerror', (error) => errors.push(error.message));
        let apiRequests = 0;
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
            i === 0 || pattern === 'coincident'
              ? { latitude: 40.4168, longitude: -3.7038 }
              : {
                  latitude: 36 + ((i * 7919) % 7900) / 1000,
                  longitude: -9 + ((i * 3571) % 12000) / 1000,
                },
          compartments: [{ enabled: true, occupied: false }],
        }));
        await page.route('https://tile.openstreetmap.org/**', (r) =>
          r.fulfill({ contentType: 'image/png', body: tile }),
        );
        await page.route('http://127.0.0.1:8765/lockers', (r) => {
          apiRequests++;
          return r.fulfill({ json: payload });
        });
        await page.goto(baseURL);
        await page.waitForFunction(
          (n) =>
            document.querySelector('#available-count')?.textContent ===
              String(n) && document.querySelector('.locker-cluster'),
          count,
        );
        const groupClick = await timedClick(
          page.locator('.locker-cluster').first(),
        );
        await page.waitForTimeout(100);
        let membersOpen = null,
          pagination = null,
          memberInspection = null,
          unselectedInspection = null;
        if (
          pattern === 'spread' &&
          (await page.locator('.locker-marker').count())
        ) {
          unselectedInspection = await timedClick(
            page.locator('.locker-marker').first(),
          );
          await page.keyboard.press('Escape');
        }
        if (pattern === 'coincident') {
          membersOpen = await timedClick(
            page.locator('.locker-cluster').first(),
          );
          await page.locator('.cluster-member-list button').first().waitFor();
          if (
            (await page.locator('.cluster-member-list button').count()) !== 20
          )
            throw new Error('Expected a bounded page of 20 members');
          pagination = await timedClick(
            page
              .locator('.cluster-pagination button')
              .filter({ hasText: 'Siguiente' }),
          );
          const member = page.locator('.cluster-member-list button').last();
          const id = await member.getAttribute('data-id');
          memberInspection = await timedClick(member);
          await page.locator('.locker-popup').waitFor();
          await page
            .getByRole('button', { name: 'Locker de origen', exact: true })
            .click();
          if (
            (await page
              .locator('#pickup-locker')
              .getAttribute('data-selected-id')) !== id
          )
            throw new Error('Selected member identity changed');
          await page.locator('#pickup-clear').click();
        }
        // Same cycles and settled state at each checkpoint: selection, inspection,
        // dismissal, removal. Navigation above is measured separately from these.
        const selection = [],
          inspection = [],
          checkpoints = [];
        const cdp = await page.context().newCDPSession(page);
        await cdp.send('Performance.enable');
        for (let cycle = 1; cycle <= 30; cycle++) {
          // Use input events without native text insertion: Chromium's undo
          // stack retains one text node per fill/clear even on a bare <input>,
          // which would obscure application resource retention in this loop.
          await page.locator('#pickup-locker').evaluate((input) => {
            input.focus({ preventScroll: true });
            input.value = 'Benchmark origen';
            input.dispatchEvent(new Event('input', { bubbles: true }));
          });
          selection.push(
            await timedClick(
              page.locator(`#pickup-options [data-id="${uuid(1)}"]`),
            ),
          );
          inspection.push(
            await timedClick(
              page.locator('.locker-marker[title="Benchmark origen"]'),
            ),
          );
          await page.keyboard.press('Escape');
          await timedClick(page.locator('#pickup-clear'));
          if ([5, 15, 30].includes(cycle))
            checkpoints.push({ cycle, ...(await memory(page, cdp)) });
        }
        if (errors.length) throw new Error(errors.join('\n'));
        if (apiRequests !== 1)
          throw new Error(`Unexpected API reloads: ${apiRequests}`);
        console.log(
          JSON.stringify({
            width,
            pattern,
            count,
            run,
            groupClick,
            membersOpen,
            pagination,
            memberInspection,
            unselectedInspection,
            selectionHandlerMedianMs: median(selection.map((x) => x.handlerMs)),
            selectionHandlerMaxMs: Math.max(
              ...selection.map((x) => x.handlerMs),
            ),
            inspectionHandlerMedianMs: median(
              inspection.map((x) => x.handlerMs),
            ),
            inspectionHandlerMaxMs: Math.max(
              ...inspection.map((x) => x.handlerMs),
            ),
            checkpoints,
            apiRequests,
            pageErrors: errors.length,
          }),
        );
        await page.close();
      }
} finally {
  await browser.close();
}
