export interface ShippingInput {
  origin_country_code: 'ES';
  origin_postal_code: string;
  destination_country_code: 'ES';
  destination_postal_code: string;
  weight_grams: number;
  dimensions: { width_mm: number; height_mm: number; depth_mm: number };
}
export type ShippingField =
  | 'parcel-length'
  | 'parcel-width'
  | 'parcel-height'
  | 'parcel-weight'
  | 'origin-postal'
  | 'destination-postal';
export interface ParcelFields {
  length: string;
  width: string;
  height: string;
  weight: string;
  origin: string;
  destination: string;
}
export type Validation =
  | { ok: true; input: ShippingInput }
  | { ok: false; errors: Partial<Record<ShippingField, string>> };
export interface Offer {
  service_code: string;
  price_cents: number;
  currency: 'EUR';
  transit_days_min: number;
  transit_days_max: number;
}
export interface Provider {
  provider_code: string;
  status: 'QUOTED' | 'NOT_COVERED' | 'FAILED';
  offers: Offer[];
  error_code: 'PROVIDER_ERROR' | 'PROVIDER_TIMEOUT' | null;
}
export interface Quotation {
  id: string;
  request: ShippingInput;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  results: Provider[];
  process_error_code: 'PUBLISH_ERROR' | 'PROCESSING_ERROR' | null;
}
export const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const postalPattern = /^[0-9]{5}$/;
// Shift decimal text rather than multiplying binary floating-point values.
export function scaledInteger(
  text: string,
  places: number,
  max: number,
): number | null {
  const match = /^\+?(\d*)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/.exec(text.trim());
  if (!match || !(match[1] || match[2])) return null;
  const digits = `${match[1] ?? ''}${match[2] ?? ''}`.replace(/^0+/, '');
  if (!digits) return null;
  const exponent = Number(match[3] ?? 0);
  if (!Number.isSafeInteger(exponent)) return null;
  const shift = places + exponent - (match[2]?.length ?? 0);
  let integer: string;
  if (shift < 0) {
    const remove = -shift;
    if (remove >= digits.length || /[1-9]/.test(digits.slice(-remove)))
      return null;
    integer = digits.slice(0, -remove);
  } else {
    if (digits.length + shift > String(max).length) return null;
    integer = digits + '0'.repeat(shift);
  }
  const value = Number(integer);
  return Number.isSafeInteger(value) && value >= 1 && value <= max
    ? value
    : null;
}
export function validateShipping(fields: ParcelFields): Validation {
  const errors: Partial<Record<ShippingField, string>> = {};
  const length = scaledInteger(fields.length, 1, 2000);
  const width = scaledInteger(fields.width, 1, 2000);
  const height = scaledInteger(fields.height, 1, 2000);
  const weight = scaledInteger(fields.weight, 3, 30000);
  for (const [id, value] of [
    ['parcel-length', length],
    ['parcel-width', width],
    ['parcel-height', height],
  ] as const) {
    if (value === null)
      errors[id] =
        'Introduce de 0,1 a 200 cm, en décimas de cm (milímetros enteros).';
  }
  if (weight === null)
    errors['parcel-weight'] = 'Introduce de 0,001 a 30 kg, en gramos enteros.';
  if (!postalPattern.test(fields.origin))
    errors['origin-postal'] = 'Introduce cinco dígitos de CP de origen.';
  if (!postalPattern.test(fields.destination))
    errors['destination-postal'] = 'Introduce cinco dígitos de CP de destino.';
  if (
    Object.keys(errors).length ||
    length === null ||
    width === null ||
    height === null ||
    weight === null
  )
    return { ok: false, errors };
  return {
    ok: true,
    input: {
      origin_country_code: 'ES',
      origin_postal_code: fields.origin,
      destination_country_code: 'ES',
      destination_postal_code: fields.destination,
      weight_grams: weight,
      dimensions: { width_mm: width, height_mm: height, depth_mm: length },
    },
  };
}
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function invalid(): never {
  throw new Error('El servicio ha devuelto una cotización no válida.');
}
function integer(
  value: unknown,
  max = Number.MAX_SAFE_INTEGER,
): value is number {
  return (
    typeof value === 'number' &&
    Number.isSafeInteger(value) &&
    value > 0 &&
    value <= max
  );
}
function code(value: unknown): value is string {
  return (
    typeof value === 'string' && value.trim() !== '' && value === value.trim()
  );
}
function date(value: unknown): boolean {
  return typeof value === 'string' && Number.isFinite(Date.parse(value));
}
function inputFromUnknown(value: unknown): ShippingInput {
  if (
    !record(value) ||
    value.origin_country_code !== 'ES' ||
    value.destination_country_code !== 'ES' ||
    typeof value.origin_postal_code !== 'string' ||
    !postalPattern.test(value.origin_postal_code) ||
    typeof value.destination_postal_code !== 'string' ||
    !postalPattern.test(value.destination_postal_code) ||
    !integer(value.weight_grams, 30000) ||
    !record(value.dimensions)
  )
    return invalid();
  const { width_mm, height_mm, depth_mm } = value.dimensions;
  if (
    !integer(width_mm, 2000) ||
    !integer(height_mm, 2000) ||
    !integer(depth_mm, 2000)
  )
    return invalid();
  return {
    origin_country_code: 'ES',
    origin_postal_code: value.origin_postal_code,
    destination_country_code: 'ES',
    destination_postal_code: value.destination_postal_code,
    weight_grams: value.weight_grams,
    dimensions: { width_mm, height_mm, depth_mm },
  };
}
export function sameInput(a: ShippingInput, b: ShippingInput): boolean {
  return (
    a.origin_country_code === b.origin_country_code &&
    a.origin_postal_code === b.origin_postal_code &&
    a.destination_country_code === b.destination_country_code &&
    a.destination_postal_code === b.destination_postal_code &&
    a.weight_grams === b.weight_grams &&
    a.dimensions.width_mm === b.dimensions.width_mm &&
    a.dimensions.height_mm === b.dimensions.height_mm &&
    a.dimensions.depth_mm === b.dimensions.depth_mm
  );
}
export function acceptedQuotation(payload: unknown): string {
  if (
    !record(payload) ||
    typeof payload.id !== 'string' ||
    !uuidPattern.test(payload.id) ||
    payload.status !== 'PENDING'
  )
    return invalid();
  return payload.id.toLowerCase();
}
export function normalizeQuotation(
  payload: unknown,
  id: string,
  expected: ShippingInput,
): Quotation {
  if (
    !record(payload) ||
    typeof payload.id !== 'string' ||
    !uuidPattern.test(payload.id) ||
    payload.id.toLowerCase() !== id.toLowerCase() ||
    typeof payload.status !== 'string' ||
    !['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'].includes(
      payload.status,
    ) ||
    !Array.isArray(payload.results) ||
    !date(payload.created_at)
  )
    return invalid();
  const request = inputFromUnknown(payload.request);
  if (!sameInput(request, expected)) return invalid();
  const status = payload.status as Quotation['status'];
  const terminal = status === 'COMPLETED' || status === 'FAILED';
  if (terminal ? !date(payload.finished_at) : payload.finished_at !== null)
    return invalid();
  const processError = payload.process_error_code;
  if (
    status === 'FAILED'
      ? typeof processError !== 'string' ||
        !['PUBLISH_ERROR', 'PROCESSING_ERROR'].includes(processError)
      : processError !== null
  )
    return invalid();
  if (status !== 'COMPLETED' && payload.results.length) return invalid();
  if (status === 'COMPLETED' && !payload.results.length) return invalid();
  const seen = new Set<string>();
  const results: Provider[] = payload.results.map((value) => {
    if (
      !record(value) ||
      !code(value.provider_code) ||
      seen.has(value.provider_code) ||
      typeof value.status !== 'string' ||
      !['QUOTED', 'NOT_COVERED', 'FAILED'].includes(value.status) ||
      !Array.isArray(value.offers)
    )
      return invalid();
    seen.add(value.provider_code);
    const services = new Set<string>();
    const offers: Offer[] = value.offers.map((offer) => {
      if (
        !record(offer) ||
        !code(offer.service_code) ||
        services.has(offer.service_code) ||
        !integer(offer.price_cents) ||
        offer.currency !== 'EUR' ||
        !integer(offer.transit_days_min) ||
        !integer(offer.transit_days_max) ||
        offer.transit_days_max < offer.transit_days_min
      )
        return invalid();
      services.add(offer.service_code);
      return {
        service_code: offer.service_code,
        price_cents: offer.price_cents,
        currency: 'EUR',
        transit_days_min: offer.transit_days_min,
        transit_days_max: offer.transit_days_max,
      };
    });
    if (
      value.status === 'QUOTED'
        ? !offers.length || value.error_code !== null
        : offers.length !== 0
    )
      return invalid();
    if (
      value.status === 'FAILED'
        ? typeof value.error_code !== 'string' ||
          !['PROVIDER_ERROR', 'PROVIDER_TIMEOUT'].includes(value.error_code)
        : value.error_code !== null
    )
      return invalid();
    return {
      provider_code: value.provider_code,
      status: value.status as Provider['status'],
      offers,
      error_code: value.error_code as Provider['error_code'],
    };
  });
  return {
    id: payload.id.toLowerCase(),
    request,
    status,
    results,
    process_error_code: processError as Quotation['process_error_code'],
  };
}
