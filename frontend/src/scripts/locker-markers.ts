import L from 'leaflet';
import { LockerSpatialIndex, type LockerGroup } from '../lib/locker-spatial';
import type { AvailableLocker } from '../lib/lockers';
import type { MapCamera } from './map-camera';
export const lockerIcon = () =>
  L.divIcon({
    className: 'locker-marker',
    iconSize: [34, 40],
    iconAnchor: [17, 40],
    popupAnchor: [0, -48],
    html: '<svg viewBox="0 0 34 40" aria-hidden="true"><path d="M17 39C14 35 2 25 2 17a15 15 0 0 1 30 0c0 8-12 18-15 22Z" fill="currentColor" stroke="white" stroke-width="2"/><g fill="none" stroke="white" stroke-width="1.5"><rect x="10" y="8" width="14" height="17" rx="1.5"/><path d="M17 8v17M10 16.5h14M14 12v1M20 12v1M14 20v1M20 20v1"/></g></svg>',
  });
export function setupLockerMarkers(
  map: L.Map,
  camera: MapCamera,
  inspect: (marker: L.Marker, locker: AvailableLocker) => void,
) {
  const spatial = new LockerSpatialIndex();
  const markers = new Map<string, L.Marker>();
  const groups = new Map<number, L.Marker>();
  let roles = new Set<string>(),
    inspected: string | null = null,
    focused: string | null = null,
    tracking: string | null = null;
  let scheduled: number | undefined,
    members: L.Popup | null = null,
    reusableMembers: L.Popup | null = null,
    memberTrigger: L.Marker | null = null;
  let memberKeyCleanup = () => {};
  const fallback = () =>
    map
      .getContainer()
      .querySelector<HTMLElement>('.leaflet-control-zoom-in')
      ?.focus({ preventScroll: true });
  function protect() {
    const ids = new Set(roles);
    for (const id of [inspected, focused, tracking]) if (id) ids.add(id);
    if (spatial.protect(ids)) {
      closeMembers();
      for (const marker of groups.values()) {
        if (marker.getElement()?.contains(document.activeElement)) fallback();
        marker.remove();
      }
      groups.clear();
    }
    return ids;
  }
  function closeMembers(restoreFocus = true, remove = true) {
    if (!members) return;
    const closed = members;
    members = null;
    const oldNode = closed.getElement();
    const hadFocus = oldNode?.contains(document.activeElement);
    const trigger = memberTrigger;
    memberTrigger = null;
    camera.cancel();
    memberKeyCleanup();
    memberKeyCleanup = () => {};
    if (oldNode) oldNode.inert = true;
    // Clear ownership before removal: native popupclose must not recurse.
    if (remove) closed.remove();
    oldNode?.remove();
    trigger?.getElement()?.classList.remove('is-inspected');
    if (restoreFocus && hadFocus) {
      if (trigger?.getElement()?.isConnected)
        trigger.getElement()!.focus({ preventScroll: true });
      else fallback();
    }
  }
  map.on('popupclose', (event) => {
    if (members === event.popup) closeMembers(false, false);
  });
  function openLocker(id: string) {
    const locker = spatial.lockers.get(id);
    if (!locker?.position) return;
    map.closePopup();
    inspected = id;
    reconcile();
    const marker = markers.get(id);
    if (marker) inspect(marker, locker);
  }
  function showMembers(group: LockerGroup, trigger: L.Marker, page = 0) {
    closeMembers();
    memberTrigger = trigger;
    trigger.getElement()?.classList.add('is-inspected');
    const root = document.createElement('div');
    root.className = 'cluster-members';
    const title = document.createElement('strong');
    title.textContent = `${group.properties.point_count} lockers en este grupo`;
    const list = document.createElement('div');
    list.className = 'cluster-member-list';
    for (const locker of spatial.page(group.properties.cluster_id, page)) {
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.id = locker.id;
      const name = document.createElement('strong');
      name.textContent = locker.label;
      const address = document.createElement('span');
      address.textContent = locker.address ?? 'Dirección no registrada';
      button.append(name, address);
      button.addEventListener('click', () => {
        closeMembers();
        openLocker(locker.id);
      });
      list.append(button);
    }
    const pages = Math.ceil(group.properties.point_count / 20),
      controls = document.createElement('div');
    controls.className = 'cluster-pagination';
    const status = document.createElement('span');
    status.textContent = `Página ${page + 1} de ${pages}`;
    status.setAttribute('role', 'status');
    for (const [label, next, disabled] of [
      ['Anterior', page - 1, page === 0],
      ['Siguiente', page + 1, page + 1 >= pages],
    ] as const) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = label;
      button.disabled = disabled;
      button.addEventListener('click', () => showMembers(group, trigger, next));
      controls.append(button);
    }
    root.append(title, list, status, controls);
    L.DomEvent.disableClickPropagation(root);
    L.DomEvent.disableScrollPropagation(root);
    members = (reusableMembers ??= L.popup({
      pane: 'inspection',
      maxWidth: 260,
      minWidth: 220,
      maxHeight: 300,
      autoPan: false,
      closeOnEscapeKey: false,
    }))
      .setLatLng(trigger.getLatLng())
      .setContent(root)
      .openOn(map);
    const popupNode = members.getElement()!;
    popupNode.inert = false;
    const onKey = (event: KeyboardEvent) => {
      event.stopPropagation();
      if (event.key === 'Escape') {
        event.preventDefault();
        closeMembers();
      }
    };
    popupNode.addEventListener('keydown', onKey);
    const closeButton = popupNode.querySelector('.leaflet-popup-close-button');
    const onClose = (event: Event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      closeMembers();
    };
    closeButton?.addEventListener('click', onClose, true);
    memberKeyCleanup = () => {
      popupNode.removeEventListener('keydown', onKey);
      closeButton?.removeEventListener('click', onClose, true);
    };
    const box = members.getElement()!.getBoundingClientRect(),
      size = map.getSize();
    const dx = Math.max(12 - box.left, Math.min(0, size.x - 12 - box.right));
    const dy = Math.max(12 - box.top, Math.min(0, size.y - 12 - box.bottom));
    camera.panBy([-dx, -dy]);
    list
      .querySelector<HTMLButtonElement>('button')
      ?.focus({ preventScroll: true });
  }
  function cluster(group: LockerGroup) {
    const marker = L.marker(
      [group.geometry.coordinates[1]!, group.geometry.coordinates[0]!],
      {
        title: `${group.properties.point_count} lockers agrupados`,
        autoPanOnFocus: false,
        icon: L.divIcon({
          className: 'locker-cluster',
          html: String(group.properties.point_count),
          iconSize: [40, 40],
          iconAnchor: [20, 20],
        }),
      },
    );
    const open = () => {
      camera.cancel();
      const expansion = spatial.expansion(group.properties.cluster_id);
      if (map.getZoom() < 19) {
        camera.frame(L.latLngBounds([marker.getLatLng(), marker.getLatLng()]), {
          maxZoom: Math.min(19, Math.max(map.getZoom() + 1, expansion)),
        });
      } else showMembers(group, marker);
    };
    marker.on('click', open);
    marker.on('add', () => {
      const node = marker.getElement()!;
      node.setAttribute('role', 'button');
      node.setAttribute(
        'aria-label',
        `${group.properties.point_count} lockers agrupados`,
      );
      node.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          event.stopPropagation();
          open();
        }
      });
    });
    return marker;
  }
  function single(locker: AvailableLocker) {
    const marker = L.marker(locker.position!, {
      title: locker.label,
      alt: `Ver ${locker.label}`,
      autoPanOnFocus: false,
      icon: lockerIcon(),
    });
    const open = () => openLocker(locker.id);
    marker.on('click', open);
    marker.on('add', () => {
      const node = marker.getElement()!;
      node.dataset.id = locker.id;
      node.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          event.stopPropagation();
          open();
        }
      });
      node.addEventListener('focus', () => {
        if (focused !== locker.id) {
          focused = locker.id;
          schedule();
        }
      });
      node.addEventListener('blur', () => {
        if (focused === locker.id) {
          focused = null;
          schedule();
        }
      });
    });
    return marker;
  }
  function reconcile() {
    const protectedIds = protect(),
      bounds = map.getBounds().pad(0.15);
    const desired = new Set<string>(),
      desiredGroups = new Set<number>();
    for (const feature of spatial.visible(
      [
        bounds.getWest(),
        bounds.getSouth(),
        bounds.getEast(),
        bounds.getNorth(),
      ],
      map.getZoom(),
    )) {
      if ('cluster' in feature.properties) {
        const group = feature as LockerGroup;
        const id = group.properties.cluster_id;
        desiredGroups.add(id);
        if (!groups.has(id)) {
          const marker = cluster(group);
          groups.set(id, marker);
          marker.addTo(map);
        }
      } else desired.add(feature.properties.id);
    }
    for (const id of protectedIds)
      if (id !== tracking && spatial.lockers.get(id)?.position) desired.add(id);
    for (const id of desired) {
      let marker = markers.get(id);
      if (!marker) {
        marker = single(spatial.lockers.get(id)!);
        markers.set(id, marker);
        marker.addTo(map);
      }
      marker.getElement()?.classList.toggle('is-role', roles.has(id));
      marker.getElement()?.classList.toggle('is-inspected', inspected === id);
    }
    for (const [id, marker] of markers)
      if (!desired.has(id)) {
        marker.remove();
        markers.delete(id);
      }
    for (const [id, marker] of groups)
      if (!desiredGroups.has(id)) {
        if (marker === memberTrigger) closeMembers();
        if (marker.getElement()?.contains(document.activeElement)) fallback();
        marker.remove();
        groups.delete(id);
      }
  }
  function schedule() {
    if (scheduled !== undefined) return;
    scheduled = requestAnimationFrame(() => {
      scheduled = undefined;
      reconcile();
    });
  }
  map.on('moveend zoomend resize', schedule);
  return {
    load(lockers: AvailableLocker[]) {
      closeMembers();
      for (const marker of markers.values()) marker.remove();
      for (const marker of groups.values()) marker.remove();
      markers.clear();
      groups.clear();
      inspected = null;
      focused = null;
      spatial.load(lockers);
      reconcile();
    },
    roles(ids: string[]) {
      const next = new Set(ids);
      if (next.size === roles.size && [...next].every((id) => roles.has(id)))
        return;
      roles = next;
      reconcile();
    },
    inspect(id: string | null) {
      if (inspected === id) return;
      inspected = id;
      schedule();
    },
    tracking(id: string | null) {
      if (tracking === id) return;
      tracking = id;
      reconcile();
    },
    get(id: string) {
      return markers.get(id);
    },
    closeMembers,
  };
}
