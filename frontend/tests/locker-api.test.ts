import { afterEach, describe, expect, it, vi } from 'vitest';
import { lockersUrl, loadLockers } from '../src/lib/locker-api';
afterEach(() => vi.useRealTimers());
describe('public API URL', () => {
  it.each([
    undefined,
    '',
    'nonsense',
    'ftp://example.org',
    'https://u:p@example.org',
    'https://example.org?x=1',
    'https://example.org#x',
  ])('rejects %s without fallback', async (value) => {
    const fetcher = vi.fn();
    await expect(loadLockers(value, 'http:', fetcher)).rejects.toThrow(
      'configurada',
    );
    expect(fetcher).not.toHaveBeenCalled();
  });
  it('blocks mixed content before fetching', async () => {
    const fetcher = vi.fn();
    await expect(
      loadLockers('http://api.example', 'https:', fetcher),
    ).rejects.toThrow('configurada');
    expect(fetcher).not.toHaveBeenCalled();
  });
  it('allows explicitly configured local HTTP and preserves base paths', () => {
    expect(lockersUrl('http://127.0.0.1:8000/', 'http:')).toBe(
      'http://127.0.0.1:8000/lockers',
    );
    expect(lockersUrl('https://api.example/v1/', 'https:')).toBe(
      'https://api.example/v1/lockers',
    );
  });
});
describe('fresh browser reads', () => {
  it('GETs directly, without credentials or custom headers, bypassing cache', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response('[]'));
    await expect(
      loadLockers('https://api.example', 'https:', fetcher),
    ).resolves.toEqual([]);
    expect(fetcher).toHaveBeenCalledWith('https://api.example/lockers', {
      method: 'GET',
      credentials: 'omit',
      cache: 'no-store',
      signal: expect.any(AbortSignal),
    });
  });
  it('reports HTTP failure', async () => {
    await expect(
      loadLockers(
        'https://api.example',
        'https:',
        vi.fn().mockResolvedValue(new Response('', { status: 503 })),
      ),
    ).rejects.toThrow('HTTP 503');
  });
  it('reports network/CORS failure without inventing a status or cause', async () => {
    await expect(
      loadLockers(
        'https://api.example',
        'https:',
        vi.fn().mockRejectedValue(new TypeError('Failed to fetch')),
      ),
    ).rejects.toThrow('conectar con el servicio de lockers');
  });
  it('reports invalid JSON', async () => {
    await expect(
      loadLockers(
        'https://api.example',
        'https:',
        vi.fn().mockResolvedValue(new Response('bad')),
      ),
    ).rejects.toThrow('no se puede leer');
  });
  it('reports malformed data', async () => {
    await expect(
      loadLockers(
        'https://api.example',
        'https:',
        vi.fn().mockResolvedValue(new Response('{}')),
      ),
    ).rejects.toThrow('datos de lockers no válidos');
  });
  it('aborts after five seconds, including response body reading', async () => {
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
      loadLockers('https://api.example', 'https:', fetcher),
    ).rejects.toThrow('cinco segundos');
    await vi.advanceTimersByTimeAsync(5000);
    await result;
  });
});
