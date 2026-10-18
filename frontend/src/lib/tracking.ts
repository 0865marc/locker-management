import { publicApiUrl } from './locker-api';
import { uuidPattern } from './quotations';
export type TrackingStatus =
  | 'AWAITING_PICKUP'
  | 'COLLECTED'
  | 'RETURNED_TO_CARRIER'
  | 'AWAITING_CARRIER'
  | 'HANDED_OVER';
export interface Tracking {
  id: string;
  kind: 'delivery' | 'return';
  status: TrackingStatus;
  relation: 'current' | 'last_known' | 'unassigned';
  lockerId: string | null;
  locker: {
    label: string;
    address: string | null;
    position: [number, number] | null;
  } | null;
}
export const trackingLabels: Record<TrackingStatus, string> = {
  AWAITING_PICKUP: 'Pendiente de recogida',
  COLLECTED: 'Recogido',
  RETURNED_TO_CARRIER: 'Devuelto al transportista',
  AWAITING_CARRIER: 'Pendiente de entrega al transportista',
  HANDED_OVER: 'Entregado al transportista',
};
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function keys(value: Record<string, unknown>, expected: string[]) {
  return (
    Object.keys(value).length === expected.length &&
    expected.every((key) => Object.hasOwn(value, key))
  );
}
function invalid(): never {
  throw new Error('El servicio ha devuelto datos de seguimiento no válidos.');
}
export function normalizeTracking(
  payload: unknown,
  requestedId: string,
): Tracking {
  if (
    !record(payload) ||
    !keys(payload, [
      'id',
      'kind',
      'status',
      'locker_relation',
      'locker_id',
      'locker',
    ]) ||
    typeof payload.id !== 'string' ||
    !uuidPattern.test(payload.id) ||
    payload.id.toLowerCase() !== requestedId.toLowerCase() ||
    (payload.kind !== 'delivery' && payload.kind !== 'return') ||
    typeof payload.status !== 'string'
  )
    return invalid();
  const allowed =
    payload.kind === 'delivery'
      ? ['AWAITING_PICKUP', 'COLLECTED', 'RETURNED_TO_CARRIER']
      : ['AWAITING_CARRIER', 'HANDED_OVER'];
  if (!allowed.includes(payload.status)) return invalid();
  const pending =
    payload.status === 'AWAITING_PICKUP' ||
    payload.status === 'AWAITING_CARRIER';
  if (
    payload.locker_id !== null &&
    (typeof payload.locker_id !== 'string' ||
      !uuidPattern.test(payload.locker_id))
  )
    return invalid();
  const relation =
    payload.locker_id === null
      ? 'unassigned'
      : pending
        ? 'current'
        : 'last_known';
  if (
    payload.locker_relation !== relation ||
    (relation === 'unassigned' && payload.locker !== null)
  )
    return invalid();
  let locker: Tracking['locker'] = null;
  if (payload.locker !== null) {
    const source = payload.locker;
    if (
      !record(source) ||
      !keys(source, ['location_id', 'address', 'coordinates']) ||
      !(source.location_id === null || typeof source.location_id === 'string')
    )
      return invalid();
    let address: string | null = null;
    if (source.address !== null) {
      const value = source.address;
      const fields = [
        'street',
        'street_number',
        'postal_code',
        'city',
        'province',
        'country_code',
      ];
      if (
        !record(value) ||
        !keys(value, fields) ||
        !fields.every((key) => typeof value[key] === 'string')
      )
        return invalid();
      address = `${value.street} ${value.street_number}, ${value.postal_code} ${value.city}, ${value.province}, ${value.country_code}`;
    }
    let position: [number, number] | null = null;
    if (source.coordinates !== null) {
      const value = source.coordinates;
      if (
        !record(value) ||
        !keys(value, ['latitude', 'longitude']) ||
        typeof value.latitude !== 'number' ||
        !Number.isFinite(value.latitude) ||
        Math.abs(value.latitude) > 90 ||
        typeof value.longitude !== 'number' ||
        !Number.isFinite(value.longitude) ||
        Math.abs(value.longitude) > 180
      )
        return invalid();
      position = [value.latitude, value.longitude];
    }
    locker = {
      label:
        typeof source.location_id === 'string' && source.location_id.trim()
          ? source.location_id
          : (address ?? 'Locker registrado'),
      address,
      position,
    };
  }
  return {
    id: payload.id.toLowerCase(),
    kind: payload.kind,
    status: payload.status as TrackingStatus,
    relation,
    lockerId:
      typeof payload.locker_id === 'string'
        ? payload.locker_id.toLowerCase()
        : null,
    locker,
  };
}
export async function loadTracking(
  config: string | undefined,
  protocol: string,
  id: string,
  signal: AbortSignal,
  fetcher: typeof fetch = fetch,
): Promise<Tracking> {
  if (!uuidPattern.test(id))
    throw new Error('Introduce un UUID válido de entrega o devolución.');
  const url = publicApiUrl(config, protocol, `tracking/${id.toLowerCase()}`);
  const controller = new AbortController();
  const cancel = () => controller.abort();
  if (signal.aborted) controller.abort();
  signal.addEventListener('abort', cancel, { once: true });
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, 5000);
  try {
    if (controller.signal.aborted)
      throw new DOMException('Cancelado', 'AbortError');
    const response = await fetcher(url, {
      method: 'GET',
      credentials: 'omit',
      cache: 'no-store',
      signal: controller.signal,
    });
    if (!response.ok) {
      const message =
        response.status === 404
          ? 'No se ha encontrado ese paquete.'
          : response.status === 409
            ? 'Este identificador es ambiguo: coincide con una entrega y una devolución.'
            : response.status === 422
              ? 'El servicio ha rechazado el UUID del paquete.'
              : `No se ha podido localizar el paquete (HTTP ${response.status}).`;
      throw new Error(message);
    }
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      if (controller.signal.aborted)
        throw new DOMException('Cancelado', 'AbortError');
      return invalid();
    }
    if (controller.signal.aborted)
      throw new DOMException('Cancelado', 'AbortError');
    return normalizeTracking(payload, id);
  } catch (error) {
    if (signal.aborted) throw new DOMException('Cancelado', 'AbortError');
    if (timedOut)
      throw new Error(
        'La localización ha superado los cinco segundos. Vuelve a intentarlo.',
      );
    if (error instanceof TypeError)
      throw new Error(
        'No se ha podido conectar con el servicio de seguimiento. Vuelve a intentarlo.',
      );
    throw error;
  } finally {
    clearTimeout(timer);
    signal.removeEventListener('abort', cancel);
  }
}
