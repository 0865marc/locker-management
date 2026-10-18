import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  geocoderUrl,
  normalizePlaces,
  searchPlaces,
} from '../src/lib/geocoder';
const feature = (
  properties: Record<string, unknown> = {},
  coordinates: unknown = [-3.7, 40.4],
) => ({
  type: 'Feature',
  geometry: { type: 'Point', coordinates },
  properties: { countrycode: 'ES', name: 'Madrid', ...properties },
});
const collection = (...features: unknown[]) => ({
  type: 'FeatureCollection',
  features,
});
afterEach(() => vi.useRealTimers());
describe('Spanish Photon queries', () => {
  it('preserves a postal code with leading zeroes in a structured query', () => {
    const url = new URL(geocoderUrl(' 01001 '));
    expect(url.pathname).toBe('/structured');
    expect(url.searchParams.get('postcode')).toBe('01001');
    expect(url.searchParams.get('q')).toBeNull();
    expect(url.searchParams.get('countrycode')).toBe('ES');
    expect(url.searchParams.get('limit')).toBe('5');
  });
  it('encodes trimmed address text without converting non-ASCII digits into postal codes', () => {
    for (const query of [' Gran Vía & Sol, Madrid ', '０１００１']) {
      const url = new URL(geocoderUrl(query));
      expect(url.pathname).toBe('/api/');
      expect(url.searchParams.get('q')).toBe(query.trim());
      expect(url.searchParams.get('countrycode')).toBe('ES');
    }
  });
  it('does not fetch a blank query', async () => {
    const fetcher = vi.fn();
    await expect(searchPlaces(' ', undefined, fetcher)).rejects.toThrow(
      'Escribe',
    );
    expect(fetcher).not.toHaveBeenCalled();
  });
});
describe('unknown GeoJSON normalization', () => {
  it('preserves text, postal zeroes and coordinate order safely', () => {
    expect(
      normalizePlaces(
        collection(
          feature({
            name: '<img src=x onerror=alert(1)>',
            postcode: '01001',
            city: 'Vitoria',
          }),
        ),
      ),
    ).toEqual([
      {
        label: '<img src=x onerror=alert(1)>, 01001, Vitoria',
        position: [40.4, -3.7],
        postalCode: '01001',
      },
    ]);
  });
  it.each([undefined, null, 1001, '1001', '１２３４５', '01001', ' 01001 '])(
    'accepts only structured five ASCII postal digits %j',
    (postcode) => {
      expect(
        normalizePlaces(
          collection(feature({ name: '01001 label', postcode })),
        )[0]?.postalCode,
      ).toBe(postcode === '01001' ? '01001' : null);
    },
  );
  it('retains at most five valid Spanish WGS84 points in provider order', () => {
    const invalid = [
      feature({ countrycode: 'FR' }),
      feature({}, [181, 40]),
      feature({}, [2, Infinity]),
      feature({}, ['2', 40]),
      feature({}, [2]),
      { ...feature(), geometry: { type: 'Polygon', coordinates: [] } },
    ];
    const valid = Array.from({ length: 8 }, (_, i) =>
      feature({ name: `Lugar ${i}`, countrycode: 'es' }, [i, 40]),
    );
    expect(
      normalizePlaces(collection(...invalid, ...valid)).map(
        (place) => place.label,
      ),
    ).toEqual(['Lugar 0', 'Lugar 1', 'Lugar 2', 'Lugar 3', 'Lugar 4']);
  });
  it('distinguishes a valid collection with no Spanish candidates from malformed data', () => {
    expect(normalizePlaces(collection())).toEqual([]);
    expect(normalizePlaces(collection(feature({ countrycode: 'PT' })))).toEqual(
      [],
    );
  });
  it.each([
    null,
    {},
    [],
    { type: 'FeatureCollection', features: null },
    collection(null),
    collection({ ...feature(), properties: null }),
    collection({ ...feature(), geometry: null }),
  ])('rejects malformed structures %j', (payload) => {
    expect(() => normalizePlaces(payload)).toThrow('respuesta no válida');
  });
});
describe('direct geographic request', () => {
  it('uses GET and omits credentials', async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify(collection(feature()))));
    await expect(
      searchPlaces('Madrid', undefined, fetcher),
    ).resolves.toHaveLength(1);
    expect(fetcher).toHaveBeenCalledWith(
      expect.stringContaining('photon.komoot.io/api/'),
      { method: 'GET', credentials: 'omit', signal: expect.any(AbortSignal) },
    );
  });
  it('reports HTTP failure', async () => {
    await expect(
      searchPlaces(
        'Madrid',
        undefined,
        vi.fn().mockResolvedValue(new Response('', { status: 503 })),
      ),
    ).rejects.toThrow('HTTP 503');
  });
  it('reports unreadable JSON', async () => {
    await expect(
      searchPlaces(
        'Madrid',
        undefined,
        vi.fn().mockResolvedValue(new Response('not json')),
      ),
    ).rejects.toThrow('respuesta no válida');
  });
  it('reports network/CORS failure without assuming the cause', async () => {
    await expect(
      searchPlaces(
        'Madrid',
        undefined,
        vi.fn().mockRejectedValue(new TypeError('Failed to fetch')),
      ),
    ).rejects.toThrow('conectar con el buscador');
  });
  it('does not start a cancelled request', async () => {
    const controller = new AbortController();
    controller.abort();
    const fetcher = vi.fn();
    await expect(
      searchPlaces('Madrid', controller.signal, fetcher),
    ).rejects.toMatchObject({ name: 'AbortError' });
    expect(fetcher).not.toHaveBeenCalled();
  });
  it('propagates external cancellation to the transport', async () => {
    const controller = new AbortController();
    let transport: AbortSignal | null | undefined;
    const fetcher = vi.fn<typeof fetch>().mockImplementation(
      (_url, init) =>
        new Promise((_resolve, reject) => {
          transport = init?.signal;
          transport?.addEventListener('abort', () =>
            reject(new DOMException('Aborted', 'AbortError')),
          );
        }),
    );
    const result = expect(
      searchPlaces('Madrid', controller.signal, fetcher),
    ).rejects.toMatchObject({ name: 'AbortError' });
    controller.abort();
    await result;
    expect(transport?.aborted).toBe(true);
  });
  it('times out after five seconds including body reading', async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn<typeof fetch>().mockImplementation(
      async (_url, init) =>
        new Response(
          new ReadableStream({
            start(controller) {
              init?.signal?.addEventListener('abort', () =>
                controller.error(new DOMException('Aborted', 'AbortError')),
              );
            },
          }),
        ),
    );
    const result = expect(
      searchPlaces('Madrid', undefined, fetcher),
    ).rejects.toThrow('cinco segundos');
    await vi.advanceTimersByTimeAsync(5000);
    await result;
  });
});
