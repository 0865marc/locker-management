import { publicApiUrl } from './locker-api';
import {
  acceptedQuotation,
  normalizeQuotation,
  uuidPattern,
  type ShippingInput,
  type Quotation,
} from './quotations';
export class QuotationRequestError extends Error {
  constructor(
    message: string,
    public readonly reference: string | null = null,
  ) {
    super(message);
  }
}
function abortError(): DOMException {
  return new DOMException('Consulta local detenida', 'AbortError');
}
async function request(
  config: string | undefined,
  protocol: string,
  path: string,
  input: ShippingInput | null,
  signal: AbortSignal,
  fetcher: typeof fetch,
  timeoutMs = 5000,
): Promise<unknown> {
  const url = publicApiUrl(config, protocol, path);
  const controller = new AbortController();
  const cancel = () => controller.abort();
  if (signal.aborted) controller.abort();
  signal.addEventListener('abort', cancel, { once: true });
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  try {
    if (controller.signal.aborted) throw abortError();
    const response = await fetcher(url, {
      method: input ? 'POST' : 'GET',
      credentials: 'omit',
      cache: 'no-store',
      signal: controller.signal,
      ...(input
        ? {
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(input),
          }
        : {}),
    });
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      if (controller.signal.aborted) throw abortError();
      throw new QuotationRequestError(
        input
          ? 'La creación no se ha podido confirmar. No se ha reenviado; podría haberse registrado.'
          : 'No se puede leer la respuesta de esta cotización.',
      );
    }
    if (controller.signal.aborted) throw abortError();
    if (!response.ok) {
      if (
        input &&
        response.status === 503 &&
        typeof payload === 'object' &&
        payload !== null &&
        'detail' in payload
      ) {
        const detail = payload.detail;
        if (
          typeof detail === 'object' &&
          detail !== null &&
          'code' in detail &&
          detail.code === 'PUBLISH_ERROR' &&
          'id' in detail &&
          typeof detail.id === 'string' &&
          uuidPattern.test(detail.id)
        )
          throw new QuotationRequestError(
            'No se ha podido poner en marcha la cotización. Puedes consultar su estado; no se ha reenviado.',
            detail.id.toLowerCase(),
          );
      }
      throw new QuotationRequestError(
        input && response.status === 422
          ? 'El servicio ha rechazado los datos (HTTP 422). Revisa los campos antes de volver a comparar.'
          : `${input ? 'La creación no se ha podido confirmar' : 'No se ha podido consultar la cotización'} (HTTP ${response.status}).${input ? ' No se ha reenviado.' : ''}`,
      );
    }
    if (input && response.status !== 202)
      throw new QuotationRequestError(
        'La creación ha devuelto una respuesta inesperada. No se ha reenviado; podría haberse registrado.',
      );
    return payload;
  } catch (error) {
    if (signal.aborted) throw abortError();
    if (timedOut)
      throw new QuotationRequestError(
        input
          ? 'La creación ha superado los cinco segundos. No se ha reenviado; podría haberse registrado.'
          : 'La lectura ha superado los cinco segundos. Puedes seguir consultando la misma solicitud.',
      );
    if (error instanceof TypeError)
      throw new QuotationRequestError(
        input
          ? 'No se ha podido confirmar la creación por un problema de conexión. No se ha reenviado; podría haberse registrado.'
          : 'No se ha podido conectar para leer esta cotización.',
      );
    throw error;
  } finally {
    clearTimeout(timer);
    signal.removeEventListener('abort', cancel);
  }
}
export async function createQuotation(
  config: string | undefined,
  protocol: string,
  input: ShippingInput,
  signal: AbortSignal,
  fetcher: typeof fetch = fetch,
): Promise<string> {
  const payload = await request(
    config,
    protocol,
    'quotations',
    input,
    signal,
    fetcher,
  );
  try {
    return acceptedQuotation(payload);
  } catch {
    throw new QuotationRequestError(
      'La creación no se ha podido confirmar con una referencia válida. No se ha reenviado; podría haberse registrado.',
    );
  }
}
export async function readQuotation(
  config: string | undefined,
  protocol: string,
  id: string,
  input: ShippingInput,
  signal: AbortSignal,
  fetcher: typeof fetch = fetch,
): Promise<Quotation> {
  if (!uuidPattern.test(id))
    throw new Error('La referencia de la cotización no es válida.');
  return normalizeQuotation(
    await request(config, protocol, `quotations/${id}`, null, signal, fetcher),
    id,
    input,
  );
}
function pause(signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const stop = () => {
      clearTimeout(timer);
      reject(abortError());
    };
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', stop);
      resolve();
    }, 1000);
    if (signal.aborted) stop();
    else signal.addEventListener('abort', stop, { once: true });
  });
}
export async function waitForQuotation(
  config: string | undefined,
  protocol: string,
  id: string,
  input: ShippingInput,
  signal: AbortSignal,
  pending: (state: 'PENDING' | 'PROCESSING') => void,
  fetcher: typeof fetch = fetch,
): Promise<Quotation> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal.addEventListener('abort', cancel, { once: true });
  if (signal.aborted) controller.abort();
  let expired = false;
  const timer = setTimeout(() => {
    expired = true;
    controller.abort();
  }, 30000);
  try {
    while (true) {
      const quotation = await readQuotation(
        config,
        protocol,
        id,
        input,
        controller.signal,
        fetcher,
      );
      if (controller.signal.aborted) throw abortError();
      if (quotation.status === 'COMPLETED' || quotation.status === 'FAILED')
        return quotation;
      pending(quotation.status);
      await pause(controller.signal);
    }
  } catch (error) {
    if (signal.aborted) throw abortError();
    if (expired)
      throw new QuotationRequestError(
        'La espera local ha alcanzado treinta segundos. El trabajo sigue en el servidor; puedes seguir consultando la misma solicitud.',
      );
    throw error;
  } finally {
    clearTimeout(timer);
    signal.removeEventListener('abort', cancel);
  }
}
