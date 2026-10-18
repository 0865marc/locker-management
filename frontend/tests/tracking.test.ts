import { afterEach, describe, it, expect, vi } from 'vitest';
import {
  normalizeTracking,
  loadTracking,
  trackingLabels,
} from '../src/lib/tracking';
const id = '00000000-0000-4000-8000-000000001001';
const lockerId = '00000000-0000-4000-8000-000000000002';
const payload = {
  id,
  kind: 'delivery',
  status: 'AWAITING_PICKUP',
  locker_relation: 'current',
  locker_id: lockerId,
  locker: {
    location_id: '<img src=x>',
    address: null,
    coordinates: { latitude: 40.4, longitude: -3.7 },
  },
};
afterEach(() => vi.useRealTimers());
describe('minimal tracking projection', () => {
  it.each([
    ['delivery', 'AWAITING_PICKUP', 'current'],
    ['delivery', 'COLLECTED', 'last_known'],
    ['delivery', 'RETURNED_TO_CARRIER', 'last_known'],
    ['return', 'AWAITING_CARRIER', 'current'],
    ['return', 'HANDED_OVER', 'last_known'],
  ])(
    'normalizes %s %s without inventing custody',
    (kind, status, locker_relation) => {
      expect(
        normalizeTracking({ ...payload, kind, status, locker_relation }, id),
      ).toMatchObject({
        kind,
        status,
        relation: locker_relation,
        locker: { label: '<img src=x>', position: [40.4, -3.7] },
      });
      expect(
        trackingLabels[status as keyof typeof trackingLabels],
      ).toBeTruthy();
    },
  );
  it('preserves absent assignment and missing locker metadata distinctly', () => {
    expect(
      normalizeTracking(
        {
          ...payload,
          locker_relation: 'unassigned',
          locker_id: null,
          locker: null,
        },
        id,
      ),
    ).toMatchObject({ relation: 'unassigned', lockerId: null, locker: null });
    expect(normalizeTracking({ ...payload, locker: null }, id)).toMatchObject({
      relation: 'current',
      lockerId,
      locker: null,
    });
    expect(
      normalizeTracking(
        { ...payload, locker: { ...payload.locker, coordinates: null } },
        id,
      ).locker?.position,
    ).toBeNull();
  });
  it.each([
    { id: 'bad' },
    { id: lockerId },
    { kind: ['delivery'] },
    { status: ['AWAITING_PICKUP'] },
    { kind: 'return' },
    { locker_relation: 'last_known' },
    { locker_id: null },
    { recipient_name: 'private' },
    { locker: { ...payload.locker, compartments: [] } },
    {
      locker: {
        ...payload.locker,
        coordinates: { latitude: 91, longitude: 0 },
      },
    },
    { locker: { ...payload.locker, address: { postal_code: '01001' } } },
  ])('rejects malformed or inconsistent unknown %j', (change) =>
    expect(() => normalizeTracking({ ...payload, ...change }, id)).toThrow(
      'no válidos',
    ),
  );
});
describe('targeted browser reads', () => {
  it('validates UUID before HTTP', async () => {
    const fetcher = vi.fn();
    await expect(
      loadTracking(
        'http://api.test',
        'http:',
        'bad',
        new AbortController().signal,
        fetcher,
      ),
    ).rejects.toThrow('UUID válido');
    expect(fetcher).not.toHaveBeenCalled();
  });
  it('reads one UUID directly without credentials or caching', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(payload)));
    await loadTracking(
      'http://api.test',
      'http:',
      id,
      new AbortController().signal,
      fetcher,
    );
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(
      `http://api.test/tracking/${id}`,
      {
        method: 'GET',
        credentials: 'omit',
        cache: 'no-store',
        signal: expect.any(AbortSignal),
      },
    );
  });
  it.each([
    [404, 'No se ha encontrado'],
    [409, 'ambiguo'],
    [422, 'rechazado'],
    [500, 'HTTP 500'],
  ])('distinguishes HTTP %s', async (status, message) => {
    await expect(
      loadTracking(
        'http://api.test',
        'http:',
        id,
        new AbortController().signal,
        vi.fn().mockResolvedValue(new Response('', { status: Number(status) })),
      ),
    ).rejects.toThrow(String(message));
  });
  it('cancels external waiting and makes no request when already aborted', async () => {
    const abort = new AbortController();
    abort.abort();
    const fetcher = vi.fn();
    await expect(
      loadTracking('http://api.test', 'http:', id, abort.signal, fetcher),
    ).rejects.toMatchObject({ name: 'AbortError' });
    expect(fetcher).not.toHaveBeenCalled();
  });
  it('includes body reading in the five-second timeout', async () => {
    vi.useFakeTimers();
    const fetcher = vi
      .fn()
      .mockImplementation(async (_url, options) => ({
        ok: true,
        json: () =>
          new Promise((_resolve, reject) =>
            options.signal.addEventListener('abort', () =>
              reject(new DOMException('Cancelado', 'AbortError')),
            ),
          ),
      }));
    const assertion = expect(
      loadTracking(
        'http://api.test',
        'http:',
        id,
        new AbortController().signal,
        fetcher,
      ),
    ).rejects.toThrow('cinco segundos');
    await vi.advanceTimersByTimeAsync(5000);
    await assertion;
  });
  it('keeps malformed body and network failure distinct from not found', async () => {
    await expect(
      loadTracking(
        'http://api.test',
        'http:',
        id,
        new AbortController().signal,
        vi.fn().mockResolvedValue(new Response('invalid')),
      ),
    ).rejects.toThrow('datos de seguimiento');
    await expect(
      loadTracking(
        'http://api.test',
        'http:',
        id,
        new AbortController().signal,
        vi.fn().mockRejectedValue(new TypeError('fetch')),
      ),
    ).rejects.toThrow('conectar');
  });
});
