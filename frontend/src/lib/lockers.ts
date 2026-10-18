export interface AvailableLocker {
  id: string;
  label: string;
  address: string | null;
  postalCode: string | null;
  position: [number, number] | null;
  freeCount: number;
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function invalid(): never {
  throw new Error(
    'El servicio de lockers ha devuelto datos de lockers no válidos.',
  );
}
function addressText(value: unknown): string | null {
  if (value === null) return null;
  if (!record(value)) return invalid();
  const keys = [
    'street',
    'street_number',
    'city',
    'province',
    'country_code',
  ] as const;
  if (!keys.every((key) => typeof value[key] === 'string')) return invalid();
  const postal =
    typeof value.postal_code === 'string' ? `${value.postal_code} ` : '';
  return `${value.street} ${value.street_number}, ${postal}${value.city}, ${value.province}, ${value.country_code}`;
}
function position(value: unknown): [number, number] | null {
  if (!record(value)) return null;
  const { latitude, longitude } = value;
  return typeof latitude === 'number' &&
    Number.isFinite(latitude) &&
    Math.abs(latitude) <= 90 &&
    typeof longitude === 'number' &&
    Number.isFinite(longitude) &&
    Math.abs(longitude) <= 180
    ? [latitude, longitude]
    : null;
}
export function availableLockers(payload: unknown): AvailableLocker[] {
  if (!Array.isArray(payload)) return invalid();
  const seen = new Set<string>();
  const results: AvailableLocker[] = [];
  for (const [index, value] of payload.entries()) {
    if (
      !record(value) ||
      typeof value.id !== 'string' ||
      !uuid.test(value.id) ||
      typeof value.active !== 'boolean' ||
      !Array.isArray(value.compartments) ||
      !(value.location_id === null || typeof value.location_id === 'string')
    )
      return invalid();
    const id = value.id.toLowerCase();
    if (seen.has(id)) return invalid();
    seen.add(id);
    const address = addressText(value.address);
    let freeCount = 0;
    for (const cell of value.compartments) {
      if (
        !record(cell) ||
        typeof cell.enabled !== 'boolean' ||
        typeof cell.occupied !== 'boolean'
      )
        return invalid();
      if (cell.enabled && !cell.occupied) freeCount++;
    }
    if (value.active && freeCount > 0)
      results.push({
        id,
        label:
          (typeof value.location_id === 'string' && value.location_id.trim()) ||
          address ||
          `Locker ${index + 1}`,
        address,
        postalCode:
          record(value.address) &&
          value.address.country_code === 'ES' &&
          typeof value.address.postal_code === 'string' &&
          /^[0-9]{5}$/.test(value.address.postal_code)
            ? value.address.postal_code
            : null,
        position: position(value.coordinates),
        freeCount,
      });
  }
  const counts = new Map<string, number>();
  for (const locker of results)
    counts.set(locker.label, (counts.get(locker.label) ?? 0) + 1);
  // Reserve original labels so generated suffixes never collide with an alias.
  const reserved = new Set(results.map((locker) => locker.label));
  const used = new Set<string>();
  const occurrence = new Map<string, number>();
  for (const locker of results) {
    const label = locker.label;
    if ((counts.get(label) ?? 0) > 1) {
      let number = (occurrence.get(label) ?? 0) + 1;
      while (
        reserved.has(`${label} · ${number}`) ||
        used.has(`${label} · ${number}`)
      )
        number++;
      occurrence.set(label, number);
      locker.label = `${label} · ${number}`;
    }
    used.add(locker.label);
  }
  return results;
}
