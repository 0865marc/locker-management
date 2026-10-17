import { describe, it, expect, vi, afterEach } from 'vitest';
import {
  scaledInteger,
  validateShipping,
  normalizeQuotation,
  acceptedQuotation,
} from '../src/lib/quotations';
import {
  createQuotation,
  readQuotation,
  waitForQuotation,
} from '../src/lib/quotation-api';
const id = '00000000-0000-4000-8000-000000000001';
const fields = {
  length: '25.5',
  width: '15',
  height: '10',
  weight: '1.001',
  origin: '28001',
  destination: '01001',
};
const validated = validateShipping(fields);
if (!validated.ok) throw Error();
const input = validated.input;
const pending = {
  id,
  request: input,
  status: 'PENDING',
  created_at: '2026-10-17T12:00:00Z',
  finished_at: null,
  process_error_code: null,
  results: [],
};
const completed = {
  ...pending,
  status: 'COMPLETED',
  finished_at: '2026-10-17T12:00:01Z',
  results: [
    {
      provider_code: 'sim-economy',
      status: 'QUOTED',
      error_code: null,
      offers: [
        {
          service_code: 'economy',
          price_cents: 1234,
          currency: 'EUR',
          transit_days_min: 2,
          transit_days_max: 4,
        },
      ],
    },
  ],
};
afterEach(() => vi.useRealTimers());
describe('shipping contract', () => {
  it('converts exact decimal text and maps length to depth', () => {
    expect(input).toMatchObject({
      weight_grams: 1001,
      destination_postal_code: '01001',
      dimensions: { depth_mm: 255, width_mm: 150, height_mm: 100 },
    });
  });
  it.each([
    ['0.1', 1, 2000, 1],
    ['200', 1, 2000, 2000],
    ['0.001', 3, 30000, 1],
    ['30', 3, 30000, 30000],
    ['1e-3', 3, 30000, 1],
    ['1.0000', 3, 30000, 1000],
    ['1.001', 3, 30000, 1001],
    ['0.01', 1, 2000, null],
    ['200.1', 1, 2000, null],
    ['30.001', 3, 30000, null],
    ['0', 3, 30000, null],
    ['-1', 3, 30000, null],
    ['Infinity', 3, 30000, null],
    ['1e99999999', 3, 30000, null],
  ] as const)('scales %s precisely', (text, places, max, result) =>
    expect(scaledInteger(text, places, max)).toBe(result),
  );
  it('rejects fractional units and non-ASCII postal codes', () =>
    expect(
      validateShipping({ ...fields, length: '1.01', origin: '１２３４５' }),
    ).toMatchObject({
      ok: false,
      errors: {
        'parcel-length': expect.any(String),
        'origin-postal': expect.any(String),
      },
    }));
  it('normalizes terminal provider offers', () =>
    expect(
      normalizeQuotation(completed, id, input).results[0]?.offers[0]
        ?.price_cents,
    ).toBe(1234));
  it.each([
    { status: ['PENDING'] },
    {
      process_error_code: ['PROCESSING_ERROR'],
      status: 'FAILED',
      finished_at: completed.finished_at,
    },
    { results: [{ ...completed.results[0], status: ['QUOTED'] }] },
    {
      results: [
        {
          provider_code: 'x',
          status: 'FAILED',
          offers: [],
          error_code: ['PROVIDER_TIMEOUT'],
        },
      ],
    },
    { id: 'bad' },
    { request: { ...input, weight_grams: 1 } },
    {
      results: [
        {
          ...completed.results[0],
          offers: [{ ...completed.results[0]!.offers[0], currency: 'USD' }],
        },
      ],
    },
  ])('rejects unknown malformed payload %j', (change) =>
    expect(() =>
      normalizeQuotation({ ...completed, ...change }, id, input),
    ).toThrow(),
  );
  it('rejects untrusted creation IDs', () =>
    expect(() =>
      acceptedQuotation({ id: 'https://bad.test', status: 'PENDING' }),
    ).toThrow());
});
describe('quotation transport', () => {
  it('sends only the exact JSON request without credentials and follows validated ID', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id, status: 'PENDING' }), {
          status: 202,
        }),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify(completed)));
    const signal = new AbortController().signal;
    expect(
      await createQuotation('http://api.test', 'http:', input, signal, fetcher),
    ).toBe(id);
    await readQuotation('http://api.test', 'http:', id, input, signal, fetcher);
    expect(fetcher.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      credentials: 'omit',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    });
    expect(fetcher.mock.calls[1]?.[0]).toBe(`http://api.test/quotations/${id}`);
  });
  it('retains publish-error reference without retry', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ detail: { code: 'PUBLISH_ERROR', id } }),
          { status: 503 },
        ),
      );
    await expect(
      createQuotation(
        'http://api.test',
        'http:',
        input,
        new AbortController().signal,
        fetcher,
      ),
    ).rejects.toMatchObject({ reference: id });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it('polls sequentially at one second and terminates', async () => {
    vi.useFakeTimers();
    const fetcher = vi
      .fn()
      .mockImplementationOnce(async () => new Response(JSON.stringify(pending)))
      .mockImplementationOnce(
        async () => new Response(JSON.stringify(completed)),
      );
    const onPending = vi.fn();
    const promise = waitForQuotation(
      'http://api.test',
      'http:',
      id,
      input,
      new AbortController().signal,
      onPending,
      fetcher,
    );
    await vi.advanceTimersByTimeAsync(999);
    expect(fetcher).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect((await promise).status).toBe('COMPLETED');
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
  it('bounds local waiting at 30 seconds without another creation', async () => {
    vi.useFakeTimers();
    const fetcher = vi
      .fn()
      .mockImplementation(async () => new Response(JSON.stringify(pending)));
    const promise = waitForQuotation(
      'http://api.test',
      'http:',
      id,
      input,
      new AbortController().signal,
      () => {},
      fetcher,
    );
    const assertion = expect(promise).rejects.toThrow('treinta segundos');
    await vi.advanceTimersByTimeAsync(30000);
    await assertion;
    expect(fetcher.mock.calls.every((call) => call[1].method === 'GET')).toBe(
      true,
    );
  });
  it('aborts pending waiting immediately', async () => {
    vi.useFakeTimers();
    const abort = new AbortController();
    const fetcher = vi
      .fn()
      .mockImplementation(async () => new Response(JSON.stringify(pending)));
    const promise = waitForQuotation(
      'http://api.test',
      'http:',
      id,
      input,
      abort.signal,
      () => {},
      fetcher,
    );
    const assertion = expect(promise).rejects.toMatchObject({
      name: 'AbortError',
    });
    await vi.advanceTimersByTimeAsync(1);
    abort.abort();
    await assertion;
  });
  it('times out a POST without retry', async () => {
    vi.useFakeTimers();
    const fetcher = vi
      .fn()
      .mockImplementation(
        (_url, options) =>
          new Promise((_resolve, reject) =>
            options.signal.addEventListener('abort', () =>
              reject(new DOMException('abort', 'AbortError')),
            ),
          ),
      );
    const assertion = expect(
      createQuotation(
        'http://api.test',
        'http:',
        input,
        new AbortController().signal,
        fetcher,
      ),
    ).rejects.toThrow('cinco segundos');
    await vi.advanceTimersByTimeAsync(5000);
    await assertion;
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
it('accepts process failure separately from completed provider failures', () => {
  expect(
    normalizeQuotation(
      {
        ...pending,
        status: 'FAILED',
        finished_at: completed.finished_at,
        process_error_code: 'PROCESSING_ERROR',
      },
      id,
      input,
    ).status,
  ).toBe('FAILED');
  const providerFailure = {
    provider_code: 'sim-express',
    status: 'FAILED',
    offers: [],
    error_code: 'PROVIDER_TIMEOUT',
  };
  expect(
    normalizeQuotation({ ...completed, results: [providerFailure] }, id, input),
  ).toMatchObject({ status: 'COMPLETED', results: [providerFailure] });
});
it('reports HTTP 422 data rejection without silently retrying POST', async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(
      new Response(JSON.stringify({ detail: [] }), { status: 422 }),
    );
  await expect(
    createQuotation(
      'http://api.test',
      'http:',
      input,
      new AbortController().signal,
      fetcher,
    ),
  ).rejects.toThrow('HTTP 422');
  expect(fetcher).toHaveBeenCalledTimes(1);
});
it('includes response body reading in the five-second timeout', async () => {
  vi.useFakeTimers();
  const fetcher = vi
    .fn()
    .mockImplementation(async (_url, options) => ({
      ok: true,
      status: 202,
      json: () =>
        new Promise((_resolve, reject) =>
          options.signal.addEventListener('abort', () =>
            reject(new DOMException('abort', 'AbortError')),
          ),
        ),
    }));
  const assertion = expect(
    createQuotation(
      'http://api.test',
      'http:',
      input,
      new AbortController().signal,
      fetcher,
    ),
  ).rejects.toThrow('cinco segundos');
  await vi.advanceTimersByTimeAsync(5000);
  await assertion;
});
