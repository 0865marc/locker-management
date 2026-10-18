import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { loadLockers } from '../lib/locker-api';
import { setupAutocomplete } from './autocomplete';
import { setupTracking } from './tracking-panel';
import { setupLockerRoute } from './locker-route';
import { setupLockerSelector, type LockerRole } from './locker-selector';
import type { AvailableLocker } from '../lib/lockers';
import { setupShipping } from './shipping-panel';
function element<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) throw new Error(`Falta ${id}`);
  return node as T;
}
const status = element('status'),
  retry = element<HTMLButtonElement>('retry'),
  results = element('results');
let activeMode: 'quote' | 'tracking' = 'quote';
let opener: HTMLElement = element('compare-shipping');
function hideResults() {
  results.hidden = true;
  element('explorer').dataset.resultsOpen = 'false';
}
function setResultsOpen(open: boolean, focus = true) {
  if (open && results.hidden && document.activeElement instanceof HTMLElement)
    opener = document.activeElement;
  results.hidden = !open;
  element('explorer').dataset.resultsOpen = String(open);
  if (!open) shipping.close();
  if (focus)
    (open
      ? element('results-title')
      : opener.isConnected
        ? opener
        : element('compare-shipping')
    ).focus({ preventScroll: true });
}
const shipping = setupShipping(
  element,
  () => setResultsOpen(true),
  hideResults,
);
const pickup = setupLockerSelector('pickup', (locker) =>
  selectRole('pickup', locker),
);
const delivery = setupLockerSelector('delivery', (locker) =>
  selectRole('delivery', locker),
);
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
  element('pickup-locker').focus();
});
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
// Render inspection above the HTML overlays without lifting the map itself.
map.createPane('inspection', element('explorer'));

const inspection = map.getPane('inspection');
if (inspection) {
  inspection.style.zIndex = '800';
  inspection.classList.add('inspection-pane');
  const syncInspection = () => {
    const pane = map.getPane('mapPane');
    if (pane) L.DomUtil.setPosition(inspection, L.DomUtil.getPosition(pane));
  };
  map.on('move zoom viewreset', syncInspection);
  syncInspection();
}
const route = setupLockerRoute(map, element('route-status'), () => {
  const menu = element('map-panels').getBoundingClientRect();
  const panel = results.hidden ? null : results.getBoundingClientRect();
  const size = map.getSize();
  return {
    left: menu.right + 6,
    right: window.matchMedia('(max-width: 760px)').matches
      ? size.x - 8
      : panel
        ? panel.left - 12
        : size.x - 16,
    top: (zoom.getContainer()?.getBoundingClientRect().bottom ?? 80) + 12,
    bottom:
      panel && window.matchMedia('(max-width: 760px)').matches
        ? panel.top - 12
        : size.y - 28,
  };
});
function selectRole(role: LockerRole, locker: AvailableLocker | null) {
  shipping.setRole(role, locker);
  map.closePopup();
  const pairFramed = route.select(role, locker);
  if (!locker?.position) return;
  for (const marker of markers.values()) marker.setZIndexOffset(0);
  markers.get(locker.id)?.setZIndexOffset(1000);
  if (pairFramed) return;
  map.setView(locker.position, 14, { animate: false });
  revealPosition(locker.position);
}
function text(tag: string, value: string) {
  const node = document.createElement(tag);
  node.textContent = value;
  return node;
}
function chooseRole(role: LockerRole, locker: AvailableLocker) {
  setMode('quote');
  map.closePopup();
  (role === 'pickup' ? pickup : delivery).select(locker);
}
let inspected: { marker: L.Marker; popup: L.Popup } | null = null;
let fittingInspection = false;
function fitInspection() {
  if (fittingInspection || !inspected || !map.hasLayer(inspected.popup)) return;
  const popupNode = inspected.popup.getElement();
  const iconNode = inspected.marker.getElement();
  if (!popupNode || !iconNode) return;
  const popup = popupNode.getBoundingClientRect();
  const icon = iconNode.getBoundingClientRect();
  const painted =
    iconNode.querySelector('span')?.getBoundingClientRect() ?? icon;
  const tip =
    popupNode
      .querySelector('.leaflet-popup-tip-container')
      ?.getBoundingClientRect() ?? popup;
  const size = map.getSize(),
    padding = 12;
  const left = Math.min(popup.left, icon.left, painted.left);
  const right = Math.max(popup.right, icon.right, painted.right);
  const top = Math.min(popup.top, icon.top, painted.top);
  const bottom = Math.max(
    popup.bottom,
    tip.bottom,
    icon.bottom,
    painted.bottom,
  );
  const dx =
    left < padding
      ? left - padding
      : right > size.x - padding
        ? right - size.x + padding
        : 0;
  const dy =
    top < padding
      ? top - padding
      : bottom > size.y - padding
        ? bottom - size.y + padding
        : 0;
  if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
  fittingInspection = true;
  map.panBy([dx, dy], { animate: false });
  fittingInspection = false;
}
map.on('moveend zoomend resize', fitInspection);
map.on('popupclose', (event) => {
  if (inspected?.popup === event.popup) inspected = null;
});
function bindInspection(
  marker: L.Marker,
  label: string,
  address: string | null,
  available: AvailableLocker | null,
) {
  const content = document.createElement('div');
  content.className = 'locker-popup';
  content.append(
    text('strong', label),
    text('p', address ?? 'Dirección no registrada'),
  );
  if (available) {
    const caption = text('p', 'Seleccionar como:');
    caption.className = 'popup-role-label';
    const actions = document.createElement('div');
    actions.className = 'popup-role-actions';
    content.append(caption, actions);
    for (const [role, label] of [
      ['delivery', 'Locker de destino'],
      ['pickup', 'Locker de origen'],
    ] as const) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = label;
      button.addEventListener('click', () => chooseRole(role, available));
      actions.append(button);
    }
  }
  L.DomEvent.disableClickPropagation(content);
  L.DomEvent.disableScrollPropagation(content);
  const popup = L.popup({
    pane: 'inspection',
    autoPan: false,
    maxWidth: 260,
    minWidth: 220,
    closeOnEscapeKey: false,
  }).setContent(content);
  marker.bindPopup(popup);
  const open = () => {
    for (const other of markers.values()) other.setZIndexOffset(0);
    marker.setZIndexOffset(1000);
    inspected = { marker, popup };
    marker.openPopup();
    const size = map.getSize();
    if (matchMedia('(max-width:760px)').matches) {
      const desired = L.point(
        size.x / 2,
        Math.min(size.y - 52, Math.max(250, size.y * 0.78)),
      );
      map.panBy(
        map.latLngToContainerPoint(marker.getLatLng()).subtract(desired),
        { animate: false },
      );
    } else revealPosition([marker.getLatLng().lat, marker.getLatLng().lng]);
    fitInspection();
    const popupNode = popup.getElement();
    const focus = popupNode?.querySelector<HTMLElement>('button, a');
    focus?.focus({ preventScroll: true });
  };
  // Own keyboard/click activation so inspection never implies selecting a role.
  marker.off('click');
  marker.on('click', open);
  marker.getElement()?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      event.stopPropagation();
      open();
    }
  });
  content.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      marker.closePopup();
      marker.getElement()?.focus({ preventScroll: true });
    }
  });
  let promoted: { icon: HTMLElement; parent: HTMLElement } | null = null;
  marker.on('popupclose', () => {
    if (promoted && marker.getElement() === promoted.icon)
      promoted.parent.append(promoted.icon);
    promoted = null;
  });
  marker.on('popupopen', () => {
    // Keep just the inspected icon visible beside its popup above the menu.
    const icon = marker.getElement();
    if (
      icon?.parentElement &&
      inspection &&
      icon.parentElement !== inspection
    ) {
      promoted = { icon, parent: icon.parentElement };
      inspection.append(icon);
    }

    const close = popup
      .getElement()
      ?.querySelector<HTMLElement>('.leaflet-popup-close-button');
    close?.addEventListener('click', () =>
      marker.getElement()?.focus({ preventScroll: true }),
    );
    popup.getElement()?.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        marker.closePopup();
        marker.getElement()?.focus({ preventScroll: true });
      }
    });
  });
}
function clear() {
  map.closePopup();
  for (const marker of markers.values()) marker.remove();
  markers.clear();
  pickup.setLockers([]);
  delivery.setLockers([]);
}
function render() {
  element('available-count').textContent = String(lockers.length);
  element('available-label').textContent =
    lockers.length === 1 ? 'disponible' : 'disponibles';
  element('positioned-count').textContent = String(
    lockers.filter((item) => item.position).length,
  );
  pickup.setLockers(lockers);
  delivery.setLockers(lockers);
  for (const locker of lockers) {
    if (!locker.position) continue;
    const marker = L.marker(locker.position, {
      title: locker.label,
      alt: `Ver ${locker.label}`,
      icon: L.divIcon({
        className: 'locker-marker',
        html: '<span aria-hidden="true">▦</span>',
        iconSize: [34, 40],
        iconAnchor: [17, 40],
        popupAnchor: [0, -62],
      }),
    }).addTo(map);
    markers.set(locker.id, marker);
    bindInspection(marker, locker.label, locker.address, locker);
  }
}
async function update() {
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
retry.addEventListener('click', () => void update());
void update();
let searchMarker: L.Marker | null = null;
const geography = setupAutocomplete('location', {
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
      popupAnchor: [0, -28],
    }),
    zIndexOffset: 2000,
  }).addTo(map);
  const marker = trackingMarker;
  const available = lockers.find((item) => item.id === parcel.lockerId) ?? null;
  bindInspection(
    marker,
    `${label}: ${parcel.locker.label}`,
    parcel.locker.address,
    available,
  );
  map.setView(parcel.locker.position, 14, { animate: false });
  revealPosition(parcel.locker.position);
});
function setMode(mode: 'quote' | 'tracking') {
  if (mode === activeMode) return;
  pickup.close();
  delivery.close();
  geography.close();
  map.closePopup();
  tracking.leave();
  if (activeMode === 'quote') {
    setResultsOpen(false, false);
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
  route.setVisible(mode === 'quote');
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
