import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { loadLockers } from '../lib/locker-api';
import type { AvailableLocker } from '../lib/lockers';
function element<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) throw new Error(`Falta el elemento ${id}`);
  return node as T;
}
const status = element('status');
const list = element('locker-list');
const detail = element('locker-detail');
const refresh = element<HTMLButtonElement>('refresh');
const retry = element<HTMLButtonElement>('retry');
const results = element('results');
const openResults = element<HTMLButtonElement>('open-results');
const closeResults = element<HTMLButtonElement>('close-results');
function setResultsOpen(open: boolean, focus = true): void {
  results.hidden = !open;
  element('explorer').dataset.resultsOpen = String(open);
  openResults.setAttribute('aria-expanded', String(open));
  if (focus) (open ? closeResults : openResults).focus({ preventScroll: true });
}
openResults.addEventListener('click', () => setResultsOpen(results.hidden));
closeResults.addEventListener('click', () => setResultsOpen(false));
results.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    event.preventDefault();
    setResultsOpen(false);
  }
});
element('skip-results').addEventListener('click', (event) => {
  event.preventDefault();
  setResultsOpen(true);
});
const parcelForm = element<HTMLFormElement>('parcel-form');
parcelForm.addEventListener('submit', (event) => event.preventDefault());
for (const input of parcelForm.querySelectorAll('input')) {
  input.addEventListener('input', () => {
    const invalid =
      input.validity.badInput ||
      (input.value !== '' &&
        (!Number.isFinite(input.valueAsNumber) || input.valueAsNumber <= 0));
    input.setCustomValidity(
      invalid ? 'Introduce un número mayor que cero.' : '',
    );
    input.setAttribute('aria-invalid', String(invalid));
    element(`${input.id}-error`).hidden = !invalid;
  });
}
for (const panel of [element('map-panels'), results]) {
  L.DomEvent.disableClickPropagation(panel);
  L.DomEvent.disableScrollPropagation(panel);
  panel.addEventListener('keydown', (event) => event.stopPropagation());
}
const spainBounds: L.LatLngBoundsExpression = [
  [27.5, -18.5],
  [44, 4.5],
];
const map = L.map('map', {
  scrollWheelZoom: false,
  zoomControl: false,
}).fitBounds(spainBounds, {
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
element('spain-view').addEventListener('click', () =>
  map.fitBounds(spainBounds, { padding: [15, 15] }),
);
const markers = new Map<string, L.Marker>();
let lockers: AvailableLocker[] = [];
let selectedId: string | null = null;
let busy = false;
function text(tag: string, content: string, className?: string): HTMLElement {
  const node = document.createElement(tag);
  node.textContent = content;
  if (className) node.className = className;
  return node;
}
function arrow(): SVGSVGElement {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 16 16');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('class', 'result-arrow');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', 'M4 12 12 4M4 4h8v8');
  path.setAttribute('stroke', 'currentColor');
  path.setAttribute('stroke-width', '1.5');
  path.setAttribute('fill', 'none');
  svg.append(path);
  return svg;
}
// Pan to the space between overlays; the stored marker coordinates stay unchanged.
function revealPosition(position: [number, number]): boolean {
  const menu = element('map-panels').getBoundingClientRect();
  const panel = results.getBoundingClientRect();
  const size = map.getSize();
  const left = menu.right + 12;
  let right = panel.left - 12;
  let top = 24;
  let bottom = size.y - 24;
  if (right - left < 40) {
    // On mobile the list is below the menu, leaving a narrow strip on its right.
    right = size.x - 12;
    top = (zoom.getContainer()?.getBoundingClientRect().bottom ?? 80) + 48;
    bottom = panel.top - 12;
  }
  const target = L.point((left + right) / 2, (top + bottom) / 2);
  map.panBy(map.latLngToContainerPoint(position).subtract(target), {
    animate: false,
  });
  return right - left >= 280;
}
function select(id: string, center = true, reveal = true): void {
  const locker = lockers.find((item) => item.id === id);
  if (!locker) return;
  if (reveal) setResultsOpen(true, false);
  selectedId = id;
  for (const button of list.querySelectorAll('button'))
    button.setAttribute('aria-pressed', String(button.dataset.id === id));
  detail.replaceChildren(
    text('p', 'DETALLE DEL LOCKER', 'eyebrow'),
    text('h3', locker.label),
    text('p', locker.address ?? 'Dirección no registrada'),
    text(
      'p',
      `${locker.freeCount} ${locker.freeCount === 1 ? 'celda libre' : 'celdas libres'}`,
      'capacity',
    ),
    text('p', `Identificador: ${locker.id}`, 'uuid'),
  );
  if (!locker.position)
    detail.append(text('p', 'Sin coordenadas válidas', 'unmapped'));
  detail.hidden = false;
  const selectedButton = [...list.querySelectorAll('button')].find(
    (button) => button.dataset.id === id,
  );
  selectedButton?.closest('li')?.append(detail);
  if (!results.hidden)
    detail.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  const marker = markers.get(id);
  if (marker && locker.position) {
    for (const item of markers.values()) item.setZIndexOffset(0);
    marker.setZIndexOffset(1000);
    if (center) map.setView(locker.position, 14, { animate: false });
    const popupFits = reveal && revealPosition(locker.position);
    if (popupFits) marker.openPopup();
    else map.closePopup();
  } else map.closePopup();
}
function clear(): void {
  for (const marker of markers.values()) marker.remove();
  markers.clear();
  list.replaceChildren();
  detail.hidden = true;
  detail.replaceChildren();
}
function render(): void {
  clear();
  element('available-count').textContent = String(lockers.length);
  element('available-label').textContent =
    lockers.length === 1 ? 'disponible' : 'disponibles';
  element('positioned-count').textContent = String(
    lockers.filter((item) => item.position).length,
  );
  lockers.forEach((locker, index) => {
    const li = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.id = locker.id;
    button.className = 'locker-result';
    button.setAttribute('aria-pressed', 'false');
    const number = text(
      'span',
      String(index + 1).padStart(2, '0'),
      'result-number',
    );
    number.setAttribute('aria-hidden', 'true');
    const body = text('span', '', 'result-body');
    body.append(
      text('strong', locker.label),
      text('span', locker.address ?? 'Dirección no registrada', 'address'),
      text(
        'span',
        `${locker.freeCount} ${locker.freeCount === 1 ? 'celda libre' : 'celdas libres'}`,
        'capacity',
      ),
    );
    if (!locker.position)
      body.append(text('span', 'Sin coordenadas válidas', 'unmapped'));
    button.append(number, body, arrow());
    button.addEventListener('click', () => select(locker.id));
    li.append(button);
    list.append(li);
    if (locker.position) {
      const popup = document.createElement('div');
      popup.append(
        text('strong', locker.label),
        text(
          'p',
          `${locker.freeCount} ${locker.freeCount === 1 ? 'celda libre' : 'celdas libres'}`,
        ),
        text('small', locker.id),
      );
      const marker = L.marker(locker.position, {
        title: locker.label,
        alt: `Ver ${locker.label}`,
        icon: L.divIcon({
          className: 'locker-marker',
          html: '<span aria-hidden="true">▦</span>',
          iconSize: [34, 40],
          iconAnchor: [17, 40],
          popupAnchor: [0, -35],
        }),
      })
        .addTo(map)
        .bindPopup(popup, { autoPan: false });
      marker.on('click', () => select(locker.id, false));
      markers.set(locker.id, marker);
    }
  });
  if (!markers.size) map.fitBounds(spainBounds, { padding: [15, 15] });
  if (selectedId && lockers.some((item) => item.id === selectedId))
    select(selectedId, false, false);
  else {
    selectedId = null;
    map.closePopup();
  }
}
async function update(): Promise<void> {
  if (busy) return;
  busy = true;
  refresh.disabled = true;
  retry.hidden = true;
  status.className = 'loading';
  status.textContent = 'Consultando disponibilidad…';
  // Hide the previous observation throughout the new read.
  clear();
  element('available-count').textContent = '—';
  element('positioned-count').textContent = '—';
  element('updated-at').textContent = 'Actualizando…';
  try {
    lockers = await loadLockers(
      import.meta.env.PUBLIC_API_BASE_URL,
      window.location.protocol,
    );
    render();
    status.className = lockers.length ? 'success' : 'empty';
    status.textContent = lockers.length
      ? lockers.some((item) => item.position)
        ? `${lockers.length} ${lockers.length === 1 ? 'locker disponible' : 'lockers disponibles'} en la última lectura.`
        : `${lockers.length} ${lockers.length === 1 ? 'locker disponible' : 'lockers disponibles'}. Ninguno tiene coordenadas válidas para el mapa.`
      : 'No hay lockers disponibles en este momento.';
    element('updated-at').textContent =
      `Última lectura · ${new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}`;
  } catch (error) {
    lockers = [];
    selectedId = null;
    clear();
    status.className = 'error';
    status.textContent =
      error instanceof Error
        ? error.message
        : 'No se ha podido consultar la disponibilidad.';
    retry.hidden = false;
    element('updated-at').textContent = 'Sin lectura vigente';
  } finally {
    busy = false;
    refresh.disabled = false;
  }
}
refresh.addEventListener('click', update);
retry.addEventListener('click', update);
void update();
