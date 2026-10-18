import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { loadLockers } from '../lib/locker-api';
import { setupAutocomplete } from './autocomplete';
import { setupTracking } from './tracking-panel';
import type { AvailableLocker } from '../lib/lockers';
import { setupShipping } from './shipping-panel';
function element<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) throw new Error(`Falta el elemento ${id}`);
  return node as T;
}
const status = element('status');
const retry = element<HTMLButtonElement>('retry');
const results = element('results');
const selector = element<HTMLSelectElement>('destination-locker');
const shipping = setupShipping(element);
let activeMode: 'quote' | 'tracking' = 'quote';
let opener: HTMLElement = element('skip-results');
function setResultsOpen(open: boolean, focus = true): void {
  results.hidden = !open;
  element('explorer').dataset.resultsOpen = String(open);
  if (!open) shipping.close();
  if (focus)
    (open
      ? selector
      : opener.isConnected
        ? opener
        : element('skip-results')
    ).focus({ preventScroll: true });
}
element('close-results').addEventListener('click', () => setResultsOpen(false));
results.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    event.preventDefault();
    setResultsOpen(false);
  }
});
element('skip-results').addEventListener('click', (event) => {
  event.preventDefault();
  setMode('quote');
  opener = element('skip-results');
  setResultsOpen(true);
});
element('parcel-form').addEventListener('submit', (event) =>
  event.preventDefault(),
);
for (const panel of [element('map-panels'), results]) {
  L.DomEvent.disableClickPropagation(panel);
  L.DomEvent.disableScrollPropagation(panel);
  panel.addEventListener('keydown', (event) => event.stopPropagation());
}
const peninsulaBounds: L.LatLngBoundsExpression = [
  [35.8, -9.4],
  [43.9, 3.4],
];
const map = L.map('map', {
  scrollWheelZoom: true,
  zoomControl: false,
}).fitBounds(peninsulaBounds, {
  padding: [15, 15],
});
const zoom = L.control.zoom({ position: 'topright' }).addTo(map);
zoom
  .getContainer()
  ?.querySelector('.leaflet-control-zoom-in')
  ?.setAttribute('aria-label', 'Acercar mapa');
zoom
  .getContainer()
  ?.querySelector('.leaflet-control-zoom-out')
  ?.setAttribute('aria-label', 'Alejar mapa');
const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);
tiles.on('tileerror', () => {
  element('tile-warning').hidden = false;
  element('tracking-tile-warning').hidden = false;
});
new ResizeObserver(() => map.invalidateSize()).observe(element('map'));
// Pan to the space between overlays; the stored marker coordinates stay unchanged.
function revealPosition(position: [number, number]): boolean {
  const menu = element('map-panels').getBoundingClientRect();
  const panel = results.hidden ? null : results.getBoundingClientRect();
  const size = map.getSize();
  const left = menu.right + 12;
  let right = panel ? panel.left - 12 : size.x - 24;
  let top = 24;
  let bottom = size.y - 24;
  if (window.matchMedia('(max-width: 760px)').matches) {
    // On mobile the list is below the menu, leaving a narrow strip on its right.
    right = size.x - 12;
    top = (zoom.getContainer()?.getBoundingClientRect().bottom ?? 80) + 48;
    bottom = panel ? panel.top - 12 : size.y - 24;
  }
  const target = L.point((left + right) / 2, (top + bottom) / 2);
  map.panBy(map.latLngToContainerPoint(position).subtract(target), {
    animate: false,
  });
  return right - left >= 280;
}
const markers = new Map<string, L.Marker>();
let lockers: AvailableLocker[] = [];
let busy = false;
function select(id: string, center = true): void {
  const locker = lockers.find((item) => item.id === id);
  selector.value = locker?.id ?? '';
  shipping.setDestination(locker ?? null);
  if (!locker) return;
  setResultsOpen(true, false);
  for (const marker of markers.values()) marker.setZIndexOffset(0);
  markers.get(id)?.setZIndexOffset(1000);
  if (locker.position) {
    if (center) map.setView(locker.position, 14, { animate: false });
    revealPosition(locker.position);
  }
}
selector.addEventListener('change', () => select(selector.value));
function clear(): void {
  for (const marker of markers.values()) marker.remove();
  markers.clear();
  selector.replaceChildren(new Option('Elige un locker disponible', ''));
  shipping.setDestination(null);
}
function render(): void {
  clear();
  element('available-count').textContent = String(lockers.length);
  element('available-label').textContent =
    lockers.length === 1 ? 'disponible' : 'disponibles';
  element('positioned-count').textContent = String(
    lockers.filter((item) => item.position).length,
  );
  for (const locker of lockers) {
    selector.add(new Option(locker.label, locker.id));
    if (!locker.position) continue;
    const marker = L.marker(locker.position, {
      title: locker.label,
      alt: `Elegir ${locker.label}`,
      icon: L.divIcon({
        className: 'locker-marker',
        html: '<span aria-hidden="true">▦</span>',
        iconSize: [34, 40],
        iconAnchor: [17, 40],
      }),
    }).addTo(map);
    const openDestination = () => {
      if (activeMode !== 'quote') return;
      opener = marker.getElement() ?? element('skip-results');
      select(locker.id, false);
      selector.focus({ preventScroll: true });
    };
    marker.on('click', openDestination);
    marker.getElement()?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        event.stopPropagation();
        openDestination();
      }
    });
    markers.set(locker.id, marker);
  }
}
async function update(): Promise<void> {
  if (busy) return;
  busy = true;
  retry.hidden = true;
  status.hidden = false;
  status.className = 'loading';
  status.textContent = 'Consultando disponibilidad…';
  clear();
  element('available-count').textContent = '—';
  element('positioned-count').textContent = '—';
  try {
    lockers = await loadLockers(
      import.meta.env.PUBLIC_API_BASE_URL,
      location.protocol,
    );
    render();
    status.hidden = lockers.length > 0;
    status.className = 'empty';
    status.textContent = 'No hay lockers disponibles en este momento.';
  } catch (error) {
    lockers = [];
    clear();
    status.className = 'error';
    status.textContent =
      error instanceof Error
        ? error.message
        : 'No se ha podido consultar la disponibilidad.';
    retry.hidden = false;
  } finally {
    busy = false;
  }
}
retry.addEventListener('click', update);
void update();

let searchMarker: L.Marker | null = null;
const delivery = setupAutocomplete('delivery', {
  onSelect(place, postal) {
    searchMarker?.remove();
    searchMarker = L.marker(place.position, {
      title: `Ubicación buscada: ${place.label}`,
      icon: L.divIcon({
        className: 'search-location',
        html: '<span aria-hidden="true"></span>',
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      }),
    }).addTo(map);
    map.setView(place.position, postal ? 13 : 16, { animate: false });
    revealPosition(place.position);
  },
});
const origin = element<HTMLInputElement>('origin-postal');
let derivedOrigin = false;
origin.addEventListener('input', () => {
  derivedOrigin = false;
});
const pickup = setupAutocomplete('pickup', {
  onSelect(place) {
    origin.value = place.postalCode ?? '';
    derivedOrigin = place.postalCode !== null;
    shipping.invalidate();
  },
  onEdit() {
    if (derivedOrigin) {
      origin.value = '';
      derivedOrigin = false;
    }
    shipping.invalidate();
  },
});
let trackingMarker: L.Marker | null = null;
const tracking = setupTracking(element, (parcel) => {
  trackingMarker?.remove();
  trackingMarker = null;
  if (activeMode !== 'tracking' || !parcel?.locker?.position) return;
  const label =
    parcel.relation === 'current'
      ? 'Locker actual'
      : 'Último locker registrado';
  trackingMarker = L.marker(parcel.locker.position, {
    title: `${label}: ${parcel.locker.label}`,
    icon: L.divIcon({
      className: 'tracking-marker',
      html: '<span aria-hidden="true">●</span>',
      iconSize: [30, 30],
      iconAnchor: [15, 15],
    }),
    zIndexOffset: 2000,
  }).addTo(map);
  map.setView(parcel.locker.position, 14, { animate: false });
  revealPosition(parcel.locker.position);
});
function setMode(mode: 'quote' | 'tracking') {
  if (mode === activeMode) return;
  pickup.close();
  delivery.close();
  tracking.leave();
  if (activeMode === 'quote') {
    setResultsOpen(false, false);
    searchMarker?.remove();
    searchMarker = null;
  }
  activeMode = mode;
  for (const item of ['quote', 'tracking'] as const) {
    const selected = item === mode;
    const tab = element(`${item}-tab`);
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
    const view = element(`${item}-view`);
    view.hidden = !selected;
    view.inert = !selected;
  }
}
const tabs = [
  element<HTMLButtonElement>('quote-tab'),
  element<HTMLButtonElement>('tracking-tab'),
];
tabs.forEach((tab, index) => {
  tab.addEventListener('click', () =>
    setMode(index === 0 ? 'quote' : 'tracking'),
  );
  tab.addEventListener('keydown', (event) => {
    let next: number;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight')
      next = 1 - index;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = 1;
    else return;
    event.preventDefault();
    tabs[next]?.focus({ preventScroll: true });
    setMode(next === 0 ? 'quote' : 'tracking');
  });
});
