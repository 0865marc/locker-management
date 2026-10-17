import {
  createQuotation,
  waitForQuotation,
  QuotationRequestError,
} from '../lib/quotation-api';
import {
  validateShipping,
  scaledInteger,
  type ShippingInput,
  type Quotation,
} from '../lib/quotations';
import type { AvailableLocker } from '../lib/lockers';
export function setupShipping(
  element: <T extends HTMLElement>(id: string) => T,
) {
  const form = element<HTMLFormElement>('shipping-form');
  const compare = element<HTMLButtonElement>('compare-shipping');
  const resume = element<HTMLButtonElement>('quotation-resume');
  const status = element('quotation-status');
  const offers = element('quotation-offers');
  const reference = element('quotation-reference');
  let generation = 0;
  let controller: AbortController | null = null;
  let known: { id: string; input: ShippingInput } | null = null;
  let destination: AvailableLocker | null = null;
  let busy = false;
  let terminal = false;
  const field = (id: string) => element<HTMLInputElement>(id);
  function stop() {
    generation++;
    controller?.abort();
    controller = null;
    busy = false;
    compare.disabled = false;
    resume.hidden = !known || terminal;
  }
  function invalidate() {
    stop();
    known = null;
    terminal = false;
    resume.hidden = true;
    status.textContent = '';
    offers.replaceChildren();
    reference.hidden = true;
    for (const id of [
      'parcel-length',
      'parcel-width',
      'parcel-height',
      'parcel-weight',
      'origin-postal',
      'destination-postal',
    ]) {
      field(id).removeAttribute('aria-invalid');
      element(`${id}-error`).hidden = true;
    }
  }
  for (const id of [
    'parcel-length',
    'parcel-width',
    'parcel-height',
    'parcel-weight',
    'origin-postal',
    'destination-postal',
  ])
    field(id).addEventListener('input', () => {
      invalidate();
      if (!id.startsWith('parcel-')) return;
      const input = field(id);
      const invalid =
        input.validity.badInput ||
        (input.value !== '' &&
          scaledInteger(
            input.value,
            id === 'parcel-weight' ? 3 : 1,
            id === 'parcel-weight' ? 30000 : 2000,
          ) === null);
      input.setAttribute('aria-invalid', String(invalid));
      const error = element(`${id}-error`);
      error.textContent =
        id === 'parcel-weight'
          ? 'Introduce de 0,001 a 30 kg, en gramos enteros.'
          : 'Introduce de 0,1 a 200 cm, en décimas de cm (milímetros enteros).';
      error.hidden = !invalid;
    });
  function showReference() {
    reference.textContent = known ? `Referencia: ${known.id}` : '';
    reference.hidden = true;
  }
  function node(tag: string, content: string) {
    const n = document.createElement(tag);
    n.textContent = content;
    return n;
  }
  function render(quotation: Quotation) {
    terminal = true;
    if (quotation.status === 'FAILED') {
      status.textContent =
        quotation.process_error_code === 'PUBLISH_ERROR'
          ? 'No se ha podido iniciar el proceso de cotización.'
          : 'El proceso de cotización ha fallado.';
      return;
    }
    status.textContent = 'Consulta finalizada. Resultados simulados:';
    for (const provider of quotation.results) {
      const card = node('section', '');
      card.className = 'offer-card';
      const names: Record<string, string> = {
        'sim-economy': 'Económico',
        'sim-standard': 'Estándar',
        'sim-express': 'Exprés',
      };
      card.append(
        node(
          'h3',
          `${names[provider.provider_code] ?? provider.provider_code} · simulado`,
        ),
      );
      if (provider.status === 'NOT_COVERED')
        card.append(node('p', 'Sin cobertura para esta solicitud.'));
      else if (provider.status === 'FAILED')
        card.append(
          node(
            'p',
            provider.error_code === 'PROVIDER_TIMEOUT'
              ? 'El proveedor ha agotado su tiempo de respuesta.'
              : 'El proveedor ha devuelto un error.',
          ),
        );
      else
        for (const offer of provider.offers) {
          card.append(
            node(
              'p',
              `Servicio ${{ economy: 'económico', standard: 'estándar', express: 'exprés' }[offer.service_code as 'economy' | 'standard' | 'express'] ?? offer.service_code}`,
            ),
            node(
              'strong',
              new Intl.NumberFormat('es-ES', {
                style: 'currency',
                currency: 'EUR',
              }).format(offer.price_cents / 100),
            ),
            node(
              'p',
              offer.transit_days_min === offer.transit_days_max
                ? `${offer.transit_days_min} ${offer.transit_days_min === 1 ? 'día' : 'días'}`
                : `${offer.transit_days_min}–${offer.transit_days_max} días`,
            ),
          );
        }
      offers.append(card);
    }
  }
  async function run(input: ShippingInput, continuation: boolean) {
    if (busy) return;
    busy = true;
    compare.disabled = true;
    resume.hidden = true;
    offers.replaceChildren();
    const token = ++generation;
    const abort = new AbortController();
    controller = abort;
    status.textContent = continuation
      ? 'Consultando la misma solicitud…'
      : 'Creando cotización…';
    try {
      if (!continuation) {
        const id = await createQuotation(
          import.meta.env.PUBLIC_API_BASE_URL,
          location.protocol,
          input,
          abort.signal,
        );
        if (token !== generation) return;
        known = { id, input };
        showReference();
      }
      if (!known) return;
      const quotation = await waitForQuotation(
        import.meta.env.PUBLIC_API_BASE_URL,
        location.protocol,
        known.id,
        known.input,
        abort.signal,
        (state) => {
          if (token === generation)
            status.textContent =
              state === 'PENDING'
                ? 'Solicitud recibida. Esperando proveedores…'
                : 'Comparando proveedores…';
        },
      );
      if (token !== generation) return;
      render(quotation);
      resume.hidden = true;
    } catch (error) {
      if (token !== generation || abort.signal.aborted) return;
      if (error instanceof QuotationRequestError && error.reference)
        known = { id: error.reference, input };
      status.textContent =
        error instanceof Error
          ? error.message
          : 'No se ha podido completar la consulta.';
      showReference();
      resume.hidden = !known || terminal;
    } finally {
      if (token === generation) {
        busy = false;
        compare.disabled = false;
        controller = null;
      }
    }
  }
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (busy) return;
    if (!destination) {
      element('destination-locker').focus();
      status.textContent = 'Elige un locker de destino.';
      return;
    }
    const validation = validateShipping({
      length: field('parcel-length').value,
      width: field('parcel-width').value,
      height: field('parcel-height').value,
      weight: field('parcel-weight').value,
      origin: field('origin-postal').value,
      destination: field('destination-postal').value,
    });
    if (!validation.ok) {
      for (const [id, message] of Object.entries(validation.errors)) {
        field(id).setAttribute('aria-invalid', 'true');
        const error = element(`${id}-error`);
        error.textContent = message;
        error.hidden = false;
      }
      const first = Object.keys(validation.errors)[0];
      if (first) field(first).focus();
      return;
    }
    known = null;
    terminal = false;
    reference.hidden = true;
    void run(validation.input, false);
  });
  resume.addEventListener('click', () => {
    if (known) void run(known.input, true);
  });
  window.addEventListener('pagehide', stop);
  return {
    setDestination(locker: AvailableLocker | null) {
      invalidate();
      destination = locker;
      element('destination-address').textContent =
        locker?.address ?? (locker ? 'Dirección no registrada' : '');
      element('destination-position').hidden = !locker || !!locker.position;
      field('destination-postal').value = locker?.postalCode ?? '';
      field('destination-postal').readOnly = !!locker?.postalCode;
      element('destination-postal-note').textContent =
        locker && !locker.postalCode
          ? 'CP del locker no registrado. Introduce su CP de destino.'
          : '';
    },
    close() {
      const wasBusy = busy;
      stop();
      if (!known && wasBusy)
        status.textContent =
          'La creación no se ha podido confirmar. La espera local se ha detenido; podría haberse registrado.';
      if (known && !terminal) {
        status.textContent =
          'Consulta local detenida. El trabajo puede continuar en el servidor.';
        showReference();
      }
    },
  };
}
