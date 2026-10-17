import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { loadLockers } from '../lib/locker-api';
import { searchPlaces, isPostalCode, type Place } from '../lib/geocoder';
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

const searchForm = element<HTMLFormElement>('location-search');
const searchInput = element<HTMLInputElement>('location-query');
const suggestions = element('search-suggestions');
const searchStatus = element('search-status');
const searchResults = element('search-results');
const searchRetry = element<HTMLButtonElement>('search-retry');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
let searchGeneration = 0;
let pendingSearch: AbortController | null = null;
let debounceTimer: number | undefined;
let hideTimer: number | undefined;
let animationGeneration = 0;
let searchMarker: L.Marker | null = null;
let pointerSelecting = false;
function showSuggestions(open: boolean): void {
  const animation = ++animationGeneration;
  clearTimeout(hideTimer);
  suggestions.inert = !open;
  suggestions.setAttribute('aria-hidden', String(!open));
  searchInput.setAttribute('aria-expanded', String(open));
  if (open) {
    if (suggestions.hidden) {
      suggestions.hidden = false;
      // Measure the collapsed state before starting the CSS transition.
      void suggestions.offsetHeight;
    }
    suggestions.classList.add('is-open');
  } else {
    suggestions.classList.remove('is-open');
    if (reducedMotion.matches || suggestions.hidden) suggestions.hidden = true;
    else
      hideTimer = window.setTimeout(() => {
        if (animation === animationGeneration) suggestions.hidden = true;
      }, 160);
  }
}
function cancelSearch(): void {
  searchGeneration++;
  clearTimeout(debounceTimer);
  pendingSearch?.abort();
  pendingSearch = null;
  searchForm.removeAttribute('aria-busy');
}
function closeSuggestions(restoreFocus = false): void {
  cancelSearch();
  if (restoreFocus) searchInput.focus({ preventScroll: true });
  showSuggestions(false);
}
function locate(place: Place, postal: boolean): void {
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
  searchInput.value = place.label;
  closeSuggestions(true);
  map.closePopup();
  map.setView(place.position, postal ? 13 : 16, { animate: false });
  revealPosition(place.position);
}
async function findSuggestions(
  query: string,
  generation: number,
): Promise<void> {
  if (generation !== searchGeneration) return;
  const controller = new AbortController();
  pendingSearch = controller;
  searchForm.setAttribute('aria-busy', 'true');
  searchResults.replaceChildren();
  searchRetry.hidden = true;
  searchStatus.hidden = false;
  searchStatus.className = 'loading';
  searchStatus.textContent = 'Buscando ubicaciones…';
  showSuggestions(true);
  try {
    const places = await searchPlaces(query, controller.signal);
    if (generation !== searchGeneration || controller.signal.aborted) return;
    searchStatus.className = '';
    searchStatus.hidden = places.length > 0;
    if (!places.length)
      searchStatus.textContent = 'No se han encontrado ubicaciones en España.';
    for (const [index, place] of places.entries()) {
      const li = document.createElement('li');
      li.setAttribute('role', 'presentation');
      const button = document.createElement('button');
      button.type = 'button';
      button.id = `suggestion-${generation}-${index}`;
      button.setAttribute('role', 'option');
      button.setAttribute('aria-selected', 'false');
      button.textContent = place.label;
      button.addEventListener('click', () =>
        locate(place, isPostalCode(query)),
      );
      li.append(button);
      searchResults.append(li);
    }
  } catch (error) {
    if (generation !== searchGeneration || controller.signal.aborted) return;
    searchStatus.className = 'error';
    searchStatus.textContent =
      error instanceof Error
        ? error.message
        : 'No se ha podido completar la búsqueda.';
    searchRetry.hidden = false;
  } finally {
    if (generation === searchGeneration) {
      pendingSearch = null;
      searchForm.removeAttribute('aria-busy');
    }
  }
}
searchInput.addEventListener('input', () => {
  cancelSearch();
  showSuggestions(false);
  const query = searchInput.value.trim();
  if (query.length < 3) return;
  const generation = searchGeneration;
  debounceTimer = window.setTimeout(
    () => void findSuggestions(query, generation),
    350,
  );
});
searchForm.addEventListener('submit', (event) => event.preventDefault());
searchRetry.addEventListener('click', () => {
  searchInput.focus({ preventScroll: true });
  const query = searchInput.value.trim();
  cancelSearch();
  if (query.length >= 3) void findSuggestions(query, searchGeneration);
});
searchForm.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    event.preventDefault();
    closeSuggestions(true);
  } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    if (suggestions.inert) return;
    const buttons = [...searchResults.querySelectorAll('button')];
    if (!buttons.length) return;
    event.preventDefault();
    const current = buttons.indexOf(
      document.activeElement as HTMLButtonElement,
    );
    const next =
      event.key === 'ArrowDown'
        ? (current + 1) % buttons.length
        : current <= 0
          ? buttons.length - 1
          : current - 1;
    buttons[next]?.focus();
  }
});
// Keep blur from dismissing a touch/click before the candidate receives it.
suggestions.addEventListener('pointerdown', () => {
  pointerSelecting = true;
});
document.addEventListener('pointerup', () => {
  window.setTimeout(() => {
    pointerSelecting = false;
    if (!searchForm.contains(document.activeElement)) closeSuggestions();
  }, 0);
});
document.addEventListener('pointercancel', () => {
  pointerSelecting = false;
});
searchForm.addEventListener('focusout', (event) => {
  if (
    pointerSelecting ||
    (event.relatedTarget instanceof Node &&
      searchForm.contains(event.relatedTarget))
  )
    return;
  closeSuggestions();
});
document.addEventListener('pointerdown', (event) => {
  if (event.target instanceof Node && !searchForm.contains(event.target))
    closeSuggestions();
});
