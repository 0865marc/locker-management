import type L from 'leaflet';

/** Own only requested camera transitions; the latest interaction wins. */
export function setupMapCamera(map: L.Map) {
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let moving = false;
  let generation = 0;
  map.on('moveend', () => {
    const token = generation;
    // Geometric correction listeners see the transition as active at moveend.
    queueMicrotask(() => {
      if (generation === token) moving = false;
    });
  });
  function cancel() {
    generation++;
    moving = true;
    // Leaflet otherwise rounds a flyTo's fractional zoom before stopping it.
    const snap = map.options.zoomSnap;
    map.options.zoomSnap = 0;
    try {
      map.stop();
    } finally {
      map.options.zoomSnap = snap;
    }
    moving = false;
  }
  function run(action: (animate: boolean) => void) {
    cancel();
    const token = ++generation;
    moving = true;
    action(!reduced.matches);
    if (reduced.matches)
      queueMicrotask(() => {
        if (token === generation) moving = false;
      });
  }
  return {
    cancel,
    get moving() {
      return moving;
    },
    panBy(offset: L.PointExpression) {
      run((animate) => map.panBy(offset, { animate, duration: 0.3 }));
    },
    frame(bounds: L.LatLngBounds, options: L.FitBoundsOptions) {
      run((animate) => {
        if (animate) map.flyToBounds(bounds, { ...options, duration: 0.3 });
        else map.fitBounds(bounds, { ...options, animate: false });
      });
    },
  };
}
export type MapCamera = ReturnType<typeof setupMapCamera>;
