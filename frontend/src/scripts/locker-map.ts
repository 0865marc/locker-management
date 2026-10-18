import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { loadLockers } from '../lib/locker-api';
import { setupAutocomplete } from './autocomplete';
import { setupTracking } from './tracking-panel';
import { setupMapCamera } from './map-camera';
import { setupLockerRoute } from './locker-route';
import { setupLockerMarkers } from './locker-markers';
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
const mobile = matchMedia('(max-width: 760px)');
const menuContent = element('menu-content');
const menuToggle = element('menu-toggle');
let menuExpanded = false;
let lastFocused: EventTarget | null = document.activeElement;
document.addEventListener('focusin', (event) => {
  lastFocused = event.target;
});
function hadFocusWithin(node: HTMLElement) {
  return (
    node.contains(document.activeElement) ||
    (document.activeElement === document.body &&
      lastFocused instanceof Node &&
      node.contains(lastFocused))
  );
}
function renderMenu() {
  const open = !mobile.matches || menuExpanded;
  if (!open && hadFocusWithin(menuContent))
    menuToggle.focus({ preventScroll: true });
  menuContent.hidden = !open;
  menuContent.inert = !open;
  menuToggle.setAttribute('aria-expanded', String(open));
  element('menu-label').textContent = open ? 'Volver al mapa' : 'Abrir menú';
  if (!mobile.matches && hadFocusWithin(menuToggle))
    element(`${activeMode}-tab`).focus({ preventScroll: true });
}
function setMenuOpen(open: boolean, focus = false) {
  camera.cancel();
  if (open && mobile.matches && !results.hidden) setResultsOpen(false, false);
  if (open && mobile.matches) map.closePopup();
  if (!open) {
    pickup.close();
    delivery.close();
    geography.close();
  }
  menuExpanded = open;
  renderMenu();
  if (focus) menuToggle.focus({ preventScroll: true });
}
renderMenu();
mobile.addEventListener('change', () => {
  camera.cancel();
  if (mobile.matches && !results.hidden) menuExpanded = false;
  renderMenu();
});
menuToggle.addEventListener('click', () => setMenuOpen(!menuExpanded, true));
// Check before selector handlers, which also consume Escape on closed lists.
element('map-panels').addEventListener(
  'keydown',
  (event) => {
    if (event.key !== 'Escape' || !mobile.matches || !menuExpanded) return;
    if (menuContent.querySelector('[aria-expanded="true"]')) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    setMenuOpen(false, true);
  },
  true,
);
function updateMenuStatus() {
  element('menu-status').textContent = [
    !status.hidden ? status.textContent : '',
    !element('tile-warning').hidden ? 'Fondo del mapa no disponible.' : '',
    activeMode === 'tracking' ? element('tracking-status').textContent : '',
  ]
    .filter(Boolean)
    .join(' ');
}
new MutationObserver(updateMenuStatus).observe(menuContent, {
  subtree: true,
  childList: true,
  characterData: true,
  attributes: true,
  attributeFilter: ['hidden', 'class'],
});
updateMenuStatus();
function hideResults() {
  if (results.contains(document.activeElement) && mobile.matches) {
    menuExpanded = true;
    renderMenu();
    menuToggle.focus({ preventScroll: true });
  }
  results.hidden = true;
  element('explorer').dataset.resultsOpen = 'false';
}
function setResultsOpen(open: boolean, focus = true) {
  camera.cancel();
  if (open && mobile.matches) setMenuOpen(false);
  results.hidden = !open;
  if (!open && mobile.matches) map.closePopup();
  element('explorer').dataset.resultsOpen = String(open);
  if (!open) {
    shipping.close();
    if (focus && mobile.matches) {
      menuExpanded = true;
      renderMenu();
    }
  }
  if (focus) {
    const target = element(open ? 'results-title' : 'compare-shipping');
    target.focus();
    if (!open) target.scrollIntoView({ block: 'nearest' });
  }
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
  setMenuOpen(true);
  setMode('quote');
  element(
    element<HTMLInputElement>('pickup-locker').readOnly
      ? 'pickup-clear'
      : 'pickup-locker',
  ).focus();
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
const camera = setupMapCamera(map);
document.addEventListener('pointerdown', () => camera.cancel(), true);
map
  .getContainer()
  .addEventListener('wheel', () => camera.cancel(), { passive: true });
map.getContainer().addEventListener('keydown', () => camera.cancel());
element('location-query').addEventListener('input', () => camera.cancel());
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
// Use the full mobile width below the menu or above results.
function visibleMapArea() {
  const menu = element('map-panels').getBoundingClientRect();
  const panel = results.hidden ? null : results.getBoundingClientRect();
  const size = map.getSize();
  const zoomBottom = zoom.getContainer()?.getBoundingClientRect().bottom ?? 80;
  return mobile.matches
    ? {
        left: 12,
        right: size.x - 12,
        top: Math.max(menu.bottom + 12, zoomBottom + 12),
        bottom: panel ? panel.top - 12 : size.y - 28,
      }
    : {
        left: menu.right + 12,
        right: panel ? panel.left - 12 : size.x - 24,
        top: zoomBottom + 12,
        bottom: size.y - 28,
      };
}
function revealPosition(position: [number, number]): boolean {
  const area = visibleMapArea();
  const target = L.point(
    (area.left + area.right) / 2,
    (area.top + area.bottom) / 2,
  );
  map.panBy(map.latLngToContainerPoint(position).subtract(target), {
    animate: false,
  });
  return area.right - area.left >= 280;
}
const roleIds: Partial<Record<LockerRole, string>> = {};
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
const markerView = setupLockerMarkers(map, camera, (marker, locker) =>
  showInspection(marker, locker.label, locker.address, locker),
);
const route = setupLockerRoute(
  map,
  camera,
  element('route-status'),
  visibleMapArea,
);
function selectRole(role: LockerRole, locker: AvailableLocker | null) {
  shipping.setRole(role, locker);
  map.closePopup();
  camera.cancel();
  route.select(role, locker);
  if (locker) roleIds[role] = locker.id;
  else delete roleIds[role];
  markerView.roles(Object.values(roleIds));
}
function text(tag: string, value: string) {
  const node = document.createElement(tag);
  node.textContent = value;
  return node;
}
function chooseRole(role: LockerRole, locker: AvailableLocker) {
  setMenuOpen(true);
  setMode('quote', false);
  map.closePopup();
  (role === 'pickup' ? pickup : delivery).select(locker);
}
let inspected: { marker: L.Marker; popup: L.Popup } | null = null;
let fittingInspection = false;
function sizeInspection() {
  if (!mobile.matches || !inspected) return;
  const popupNode = inspected.popup.getElement();
  const content = popupNode?.querySelector<HTMLElement>('.locker-popup');
  const iconNode = inspected.marker.getElement();
  if (!popupNode || !content || !iconNode) return;
  const popup = popupNode.getBoundingClientRect();
  const icon = iconNode.getBoundingClientRect();
  const painted =
    iconNode.querySelector('span')?.getBoundingClientRect() ?? icon;
  const tip =
    popupNode
      .querySelector('.leaflet-popup-tip-container')
      ?.getBoundingClientRect() ?? popup;
  const top = Math.min(popup.top, icon.top, painted.top);
  const bottom = Math.max(
    popup.bottom,
    tip.bottom,
    icon.bottom,
    painted.bottom,
  );
  const area = visibleMapArea();
  // Measure the real frame, pointer and pin; retain a whole 48px role action.
  const height = Math.max(
    48,
    Math.floor(
      content.getBoundingClientRect().height +
        area.bottom -
        area.top -
        (bottom - top),
    ),
  );
  const value = `${height}px`;
  if (content.style.getPropertyValue('--popup-max-height') !== value) {
    content.style.setProperty('--popup-max-height', value);
    inspected.popup.update();
  }
}
function fitInspection() {
  if (
    camera.moving ||
    fittingInspection ||
    !inspected ||
    !map.hasLayer(inspected.popup)
  )
    return;
  sizeInspection();
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
    top < (mobile.matches ? visibleMapArea().top : padding)
      ? top - (mobile.matches ? visibleMapArea().top : padding)
      : bottom > (mobile.matches ? visibleMapArea().bottom : size.y - padding)
        ? bottom - (mobile.matches ? visibleMapArea().bottom : size.y - padding)
        : 0;
  if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
  fittingInspection = true;
  map.panBy([dx, dy], { animate: false });
  fittingInspection = false;
}
map.on('moveend zoomend', fitInspection);
map.on('resize', () => {
  camera.cancel();
  fitInspection();
});
let sharedPopup: L.Popup | null = null;
let inspectionHandlersCleanup = () => {};
let promoted: { icon: HTMLElement; parent: HTMLElement } | null = null;
map.on('popupclose', (event) => {
  if (inspected?.popup !== event.popup) return;
  const marker = inspected.marker;
  inspectionHandlersCleanup();
  inspectionHandlersCleanup = () => {};
  const closedNode = event.popup.getElement();
  if (closedNode) closedNode.inert = true;
  closedNode?.remove();
  if (promoted && marker.getElement() === promoted.icon)
    promoted.parent.append(promoted.icon);
  promoted = null;
  marker.getElement()?.classList.remove('is-inspected');
  inspected = null;
  element('explorer').dataset.inspectionOpen = 'false';
  markerView.inspect(null);
  camera.cancel();
  if (mobile.matches && !results.hidden) {
    const position = marker.getLatLng();
    revealPosition([position.lat, position.lng]);
  }
});
function showInspection(
  marker: L.Marker,
  label: string,
  address: string | null,
  available: AvailableLocker | null,
) {
  camera.cancel();
  if (mobile.matches) setMenuOpen(false);
  map.closePopup();
  markerView.closeMembers();
  if (available) markerView.inspect(available.id);
  element('explorer').dataset.inspectionOpen = 'true';
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
    for (const [role, label] of [
      ['pickup', 'Locker de origen'],
      ['delivery', 'Locker de destino'],
    ] as const) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = label;
      button.addEventListener('click', () => chooseRole(role, available));
      actions.append(button);
    }
    content.append(caption, actions);
  }
  L.DomEvent.disableClickPropagation(content);
  L.DomEvent.disableScrollPropagation(content);
  const popup = (sharedPopup ??= L.popup({
    pane: 'inspection',
    autoPan: false,
    maxWidth: 260,
    minWidth: 220,
    closeOnEscapeKey: false,
  }));
  popup.options.offset = L.point(
    0,
    marker.getElement()?.classList.contains('tracking-marker') ? -28 : -48,
  );
  inspected = { marker, popup };
  popup.setLatLng(marker.getLatLng()).setContent(content).openOn(map);
  const icon = marker.getElement();
  if (icon?.parentElement && inspection && icon.parentElement !== inspection) {
    promoted = { icon, parent: icon.parentElement };
    inspection.append(icon);
  }
  icon?.classList.add('is-inspected');
  sizeInspection();
  const area = visibleMapArea();
  const size = map.getSize();
  const point = map.latLngToContainerPoint(marker.getLatLng());
  const desired = mobile.matches
    ? L.point((area.left + area.right) / 2, area.bottom - 24)
    : L.point((area.left + area.right) / 2, size.y / 2);
  const popupBox = popup.getElement()!.getBoundingClientRect();
  const iconBox = marker.getElement()!.getBoundingClientRect();
  const painted =
    marker.getElement()?.querySelector('span')?.getBoundingClientRect() ??
    iconBox;
  const tip =
    popup
      .getElement()
      ?.querySelector('.leaflet-popup-tip-container')
      ?.getBoundingClientRect() ?? popupBox;
  const left = Math.min(popupBox.left, iconBox.left, painted.left);
  const right = Math.max(popupBox.right, iconBox.right, painted.right);
  const top = Math.min(popupBox.top, iconBox.top, painted.top);
  const bottom = Math.max(
    popupBox.bottom,
    tip.bottom,
    iconBox.bottom,
    painted.bottom,
  );
  const dx = Math.max(
    12 - left,
    Math.min(desired.x - point.x, size.x - 12 - right),
  );
  const dy = Math.max(
    (mobile.matches ? area.top : 12) - top,
    Math.min(
      desired.y - point.y,
      (mobile.matches ? area.bottom : size.y - 12) - bottom,
    ),
  );
  camera.panBy([-dx, -dy]);
  const popupNode = popup.getElement();
  if (popupNode) popupNode.inert = false;
  const focus = popupNode?.querySelector<HTMLElement>('button, a');
  focus?.focus({ preventScroll: true });

  const close = () => {
    map.closePopup();
    marker.getElement()?.focus({ preventScroll: true });
  };
  const closeButton = popupNode?.querySelector('.leaflet-popup-close-button');
  const onKey = (event: KeyboardEvent) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      close();
    }
  };
  popupNode?.addEventListener('keydown', onKey);
  const onClose = (event: Event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
    close();
  };
  closeButton?.addEventListener('click', onClose, true);
  inspectionHandlersCleanup = () => {
    popupNode?.removeEventListener('keydown', onKey);
    closeButton?.removeEventListener('click', onClose, true);
  };
}
function clear() {
  map.closePopup();
  markerView.load([]);
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
  markerView.load(lockers);
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
    camera.cancel();
    map.closePopup();
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
  if (trackingMarker && inspected?.marker === trackingMarker) map.closePopup();
  trackingMarker?.remove();
  trackingMarker = null;
  markerView.tracking(
    activeMode === 'tracking' && parcel?.locker?.position
      ? parcel.lockerId
      : null,
  );
  if (activeMode !== 'tracking' || !parcel?.locker?.position) return;
  const label =
    parcel.relation === 'current'
      ? 'Locker actual'
      : 'Último locker registrado';
  trackingMarker = L.marker(parcel.locker.position, {
    title: `${label}: ${parcel.locker.label}`,
    autoPanOnFocus: false,
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
  const open = () =>
    showInspection(
      marker,
      `${label}: ${parcel.locker!.label}`,
      parcel.locker!.address,
      available,
    );
  marker.on('click', open);
  marker.getElement()?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      event.stopPropagation();
      open();
    }
  });
  map.setView(parcel.locker.position, 14, { animate: false });
  revealPosition(parcel.locker.position);
});
function setMode(mode: 'quote' | 'tracking', restoreRoute = true) {
  if (mode === activeMode) return;
  camera.cancel();
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
  route.setVisible(mode === 'quote', restoreRoute);
  updateMenuStatus();
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
