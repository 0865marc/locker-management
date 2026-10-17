export interface Place {
  label: string;
  position: [number, number];
}
export function isPostalCode(query: string): boolean {
  return /^[0-9]{5}$/.test(query.trim());
}
export function geocoderUrl(query: string): string {
  const trimmed = query.trim();
  if (!trimmed) throw new Error('Escribe una dirección o un código postal.');
  const postal = isPostalCode(trimmed);
  const url = new URL(
    postal
      ? 'https://photon.komoot.io/structured'
      : 'https://photon.komoot.io/api/',
  );
  url.searchParams.set(postal ? 'postcode' : 'q', trimmed);
  url.searchParams.set('countrycode', 'ES');
  url.searchParams.set('limit', '5');
  return url.href;
}
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function malformed(): never {
  throw new Error('El buscador ha devuelto una respuesta no válida.');
}
export function normalizePlaces(payload: unknown): Place[] {
  if (
    !record(payload) ||
    payload.type !== 'FeatureCollection' ||
    !Array.isArray(payload.features)
  )
    return malformed();
  const places: Place[] = [];
  for (const feature of payload.features) {
    if (
      !record(feature) ||
      feature.type !== 'Feature' ||
      !record(feature.geometry) ||
      !record(feature.properties)
    )
      return malformed();
    const { geometry, properties } = feature;
    if (
      typeof properties.countrycode !== 'string' ||
      properties.countrycode.toUpperCase() !== 'ES' ||
      geometry.type !== 'Point' ||
      !Array.isArray(geometry.coordinates)
    )
      continue;
    const [longitude, latitude] = geometry.coordinates;
    if (
      typeof longitude !== 'number' ||
      !Number.isFinite(longitude) ||
      Math.abs(longitude) > 180 ||
      typeof latitude !== 'number' ||
      !Number.isFinite(latitude) ||
      Math.abs(latitude) > 90
    )
      continue;
    const parts = ['name', 'street', 'housenumber', 'postcode', 'city', 'state']
      .map((key) => properties[key])
      .filter(
        (part): part is string =>
          typeof part === 'string' && part.trim() !== '',
      );
    const label = [...new Set(parts)].join(', ') || 'Ubicación en España';
    places.push({ label, position: [latitude, longitude] });
    if (places.length === 5) break;
  }
  return places;
}
export async function searchPlaces(
  query: string,
  signal?: AbortSignal,
  fetcher: typeof fetch = fetch,
): Promise<Place[]> {
  const url = geocoderUrl(query);
  const controller = new AbortController();
  const cancel = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener('abort', cancel, { once: true });
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
      signal: controller.signal,
    });
    if (!response.ok)
      throw new Error(
        `El buscador no ha podido completar la consulta (HTTP ${response.status}).`,
      );
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      if (controller.signal.aborted)
        throw new DOMException('Cancelado', 'AbortError');
      return malformed();
    }
    return normalizePlaces(payload);
  } catch (error) {
    if (timedOut)
      throw new Error(
        'La búsqueda ha superado los cinco segundos. Vuelve a intentarlo.',
      );
    if (controller.signal.aborted)
      throw new DOMException('Cancelado', 'AbortError');
    if (error instanceof TypeError)
      throw new Error(
        'No se ha podido conectar con el buscador. Vuelve a intentarlo.',
      );
    throw error;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', cancel);
  }
}
