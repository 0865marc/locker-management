import L from 'leaflet';
import type { AvailableLocker } from '../lib/lockers';
import type { LockerRole } from './locker-selector';

/** An illustration of the selected positions, never a transport route. */
export function setupLockerRoute(
  map: L.Map,
  message: HTMLElement,
  visibleArea: () => {
    left: number;
    top: number;
    right: number;
    bottom: number;
  },
) {
  const roles: Record<LockerRole, AvailableLocker | null> = {
    pickup: null,
    delivery: null,
  };
  const pane = map.createPane('selected-route');
  pane.style.zIndex = '625';
  pane.style.pointerEvents = 'none';
  const layer = L.layerGroup().addTo(map);
  let visible = true;
  let fitting = false;
  function endpoint(position: [number, number], label: string, symbol: string) {
    const marker = L.marker(position, {
      interactive: false,
      keyboard: false,
      pane: 'selected-route',
      icon: L.divIcon({
        className: 'route-endpoint',
        html: '',
        iconSize: [symbol === 'O/D' ? 28 : 20, 20],
        iconAnchor: [symbol === 'O/D' ? 14 : 10, 10],
      }),
    }).addTo(layer);
    const node = marker.getElement();
    if (node) {
      node.textContent = symbol;
      node.setAttribute('role', 'img');
      node.setAttribute('aria-label', label);
    }
  }
  function render(frame: boolean) {
    layer.clearLayers();
    message.hidden = true;
    message.textContent = '';
    if (!visible || !roles.pickup || !roles.delivery) return false;
    const origin = roles.pickup.position,
      destination = roles.delivery.position;
    message.hidden = false;
    if (!origin || !destination) {
      const missing = [!origin && 'origen', !destination && 'destino'].filter(
        Boolean,
      );
      message.textContent = `Sin ubicación para el locker de ${missing.join(' y ')}. No se puede mostrar el trayecto.`;
      return false;
    }
    message.textContent = 'Trayecto orientativo · O origen · D destino';
    L.polyline([origin, destination], {
      className: 'locker-route',
      pane: 'selected-route',
      color: '#145b78',
      weight: 3,
      opacity: 0.85,
      dashArray: '7 7',
      interactive: false,
    }).addTo(layer);
    if (frame) {
      const area = visibleArea(),
        size = map.getSize();
      // Include each badge, keep the real positions and bound coincident zoom.
      fitting = true;
      map.fitBounds(L.latLngBounds([origin, destination]), {
        paddingTopLeft: [area.left + 14, area.top + 14],
        paddingBottomRight: [
          size.x - area.right + 14,
          size.y - area.bottom + 14,
        ],
        maxZoom: 14,
        animate: false,
      });
      fitting = false;
    }
    const coincident =
      origin[0] === destination[0] && origin[1] === destination[1];
    const a = map.latLngToContainerPoint(origin),
      b = map.latLngToContainerPoint(destination);
    // Merge only the decoration when badges overlap, never the stored positions.
    if (a.distanceTo(b) < 22) {
      const description = coincident
        ? 'Origen y destino en el mismo punto'
        : 'Origen y destino agrupados en esta vista';
      endpoint(origin, description, 'O/D');
      message.textContent = `Trayecto orientativo · O/D ${description.toLowerCase()}`;
    } else {
      endpoint(origin, `Origen: ${roles.pickup.label}`, 'O');
      endpoint(destination, `Destino: ${roles.delivery.label}`, 'D');
    }
    return true;
  }
  map.on('zoomend', () => {
    if (!fitting) render(false);
  });
  return {
    select(role: LockerRole, locker: AvailableLocker | null) {
      const changed = roles[role]?.id !== locker?.id;
      roles[role] = locker;
      return render(changed);
    },
    setVisible(next: boolean) {
      visible = next;
      render(next);
    },
  };
}
