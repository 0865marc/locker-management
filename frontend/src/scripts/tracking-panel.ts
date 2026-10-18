import { loadTracking, trackingLabels, type Tracking } from '../lib/tracking';
import { uuidPattern } from '../lib/quotations';
export function setupTracking(
  element: <T extends HTMLElement>(id: string) => T,
  onLocation: (tracking: Tracking | null) => void,
) {
  const form = element<HTMLFormElement>('tracking-form');
  const input = element<HTMLInputElement>('tracking-id');
  const status = element('tracking-status');
  const result = element('tracking-result');
  const retry = element<HTMLButtonElement>('tracking-retry');
  const error = element('tracking-error');
  let generation = 0;
  let controller: AbortController | null = null;
  function cancel() {
    generation++;
    controller?.abort();
    controller = null;
    form.removeAttribute('aria-busy');
  }
  function clear() {
    result.replaceChildren();
    result.hidden = true;
    onLocation(null);
  }
  function node(tag: string, value: string) {
    const n = document.createElement(tag);
    n.textContent = value;
    return n;
  }
  function invalidate() {
    cancel();
    clear();
    status.textContent = '';
    retry.hidden = true;
    error.hidden = true;
    input.removeAttribute('aria-invalid');
  }
  async function submit() {
    invalidate();
    const id = input.value.trim();
    if (!uuidPattern.test(id)) {
      error.textContent = 'Introduce un UUID válido de entrega o devolución.';
      error.hidden = false;
      input.setAttribute('aria-invalid', 'true');
      input.focus();
      return;
    }
    const token = generation;
    const abort = new AbortController();
    controller = abort;
    form.setAttribute('aria-busy', 'true');
    status.textContent = 'Localizando paquete…';
    try {
      const tracking = await loadTracking(
        import.meta.env.PUBLIC_API_BASE_URL,
        location.protocol,
        id,
        abort.signal,
      );
      if (token !== generation || abort.signal.aborted) return;
      status.textContent = 'Paquete localizado.';
      result.append(
        node('p', tracking.kind === 'delivery' ? 'Entrega' : 'Devolución'),
        node('h2', trackingLabels[tracking.status]),
      );
      if (tracking.relation === 'unassigned')
        result.append(node('p', 'Sin locker asignado.'));
      else {
        result.append(
          node(
            'h3',
            tracking.relation === 'current'
              ? 'Locker actual'
              : 'Último locker registrado',
          ),
        );
        if (tracking.relation === 'last_known')
          result.append(
            node(
              'p',
              'El paquete ya ha salido del locker. Esta es la última asignación registrada.',
            ),
          );
        if (!tracking.locker)
          result.append(node('p', 'Datos del locker no disponibles.'));
        else {
          result.append(
            node('strong', tracking.locker.label),
            node('p', tracking.locker.address ?? 'Dirección no registrada'),
          );
          if (!tracking.locker.position)
            result.append(node('p', 'Ubicación no disponible en el mapa.'));
        }
      }
      result.hidden = false;
      onLocation(tracking);
    } catch (cause) {
      if (token !== generation || abort.signal.aborted) return;
      status.textContent =
        cause instanceof Error
          ? cause.message
          : 'No se ha podido localizar el paquete.';
      retry.hidden = false;
    } finally {
      if (token === generation) {
        controller = null;
        form.removeAttribute('aria-busy');
      }
    }
  }
  input.addEventListener('input', invalidate);
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    void submit();
  });
  retry.addEventListener('click', () => {
    input.focus({ preventScroll: true });
    void submit();
  });
  window.addEventListener('pagehide', cancel);
  return {
    leave() {
      invalidate();
    },
  };
}
