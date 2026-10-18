import { afterEach, expect, it, vi } from 'vitest';
import type L from 'leaflet';
import { setupMapCamera } from '../src/scripts/map-camera';
afterEach(() => vi.unstubAllGlobals());
function fixture(reduced = false) {
  vi.stubGlobal('matchMedia', () => ({ matches: reduced }));
  let end = () => {};
  const map = {
    options: { zoomSnap: 1 },
    on: vi.fn((_event, listener) => {
      end = listener;
    }),
    stop: vi.fn(() => end()),
    panBy: vi.fn(),
    fitBounds: vi.fn(),
    flyToBounds: vi.fn(),
  };
  return {
    map,
    end: () => end(),
    camera: setupMapCamera(map as unknown as L.Map),
  };
}
it('a stop completion cannot unlock a superseding transition', async () => {
  const { camera, end, map } = fixture();
  camera.panBy([10, 20]);
  camera.panBy([20, 40]);
  await Promise.resolve();
  expect(camera.moving).toBe(true);
  expect(map.options.zoomSnap).toBe(1);
  end();
  await Promise.resolve();
  expect(camera.moving).toBe(false);
});
it('cancellation leaves no delayed active movement', async () => {
  const { camera } = fixture();
  camera.panBy([10, 20]);
  camera.cancel();
  await Promise.resolve();
  expect(camera.moving).toBe(false);
});
it('reduced motion uses immediate bounds and releases the transition', async () => {
  const { camera, map } = fixture(true);
  camera.frame({} as L.LatLngBounds, { maxZoom: 14 });
  expect(map.flyToBounds).not.toHaveBeenCalled();
  expect(map.fitBounds).toHaveBeenCalledWith(
    {},
    { maxZoom: 14, animate: false },
  );
  await Promise.resolve();
  expect(camera.moving).toBe(false);
});
