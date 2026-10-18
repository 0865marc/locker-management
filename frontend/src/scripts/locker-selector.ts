import {
  matchingLockers,
  lockerSuggestionState,
} from '../lib/locker-selection';
import type { AvailableLocker } from '../lib/lockers';
export type LockerRole = 'pickup' | 'delivery';
export function setupLockerSelector(
  role: LockerRole,
  onChoose: (locker: AvailableLocker | null) => void,
) {
  function element<T extends HTMLElement>(suffix: string): T {
    const n = document.getElementById(`${role}-${suffix}`);
    if (!n) throw Error(`Falta ${role}-${suffix}`);
    return n as T;
  }
  const root = element('selector'),
    input = element<HTMLInputElement>('locker'),
    suggestions = element('suggestions'),
    list = element('options'),
    clear = element<HTMLButtonElement>('clear');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  let lockers: AvailableLocker[] = [];
  let selected: AvailableLocker | null = null;
  let pointerSelecting = false;
  let animation = 0;
  let hideTimer: number | undefined;
  function close(focus = false) {
    const target = selected ? clear : input;
    if (focus) target.focus({ preventScroll: true });
    const generation = ++animation;
    clearTimeout(hideTimer);
    suggestions.inert = true;
    suggestions.setAttribute('aria-hidden', 'true');
    input.setAttribute('aria-expanded', 'false');
    suggestions.classList.remove('is-open');
    if (reducedMotion.matches) suggestions.hidden = true;
    else
      hideTimer = window.setTimeout(() => {
        if (generation === animation) suggestions.hidden = true;
      }, 160);
    if (focus) target.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }
  function choose(locker: AvailableLocker | null) {
    selected = locker;
    input.dataset.selectedId = locker?.id ?? '';
    input.value = locker?.label ?? '';
    input.readOnly = !!locker;
    clear.hidden = !locker;
    element('search-status').textContent = '';
    element('search-status').hidden = true;
    close();
    onChoose(locker);
  }
  function show() {
    if (selected) {
      close();
      return;
    }
    animation++;
    clearTimeout(hideTimer);
    list.replaceChildren();
    const matches = matchingLockers(lockers, input.value);
    const state = lockerSuggestionState(input.value, matches.length);
    const searchStatus = element('search-status');
    searchStatus.textContent =
      state === 'refine'
        ? 'Concreta la búsqueda'
        : state === 'none'
          ? 'Sin coincidencias'
          : '';
    searchStatus.hidden = state === 'empty' || state === 'matches';
    if (state !== 'matches') {
      close();
      return;
    }

    for (const locker of matches) {
      const li = document.createElement('li');
      li.setAttribute('role', 'presentation');
      const button = document.createElement('button');
      button.type = 'button';
      button.setAttribute('role', 'option');
      button.setAttribute('aria-selected', 'false');
      button.dataset.id = locker.id;
      const title = document.createElement('strong');
      title.textContent = locker.label;
      const address = document.createElement('span');
      address.textContent = locker.address ?? 'Dirección no registrada';
      button.append(title, address);
      if (!locker.position) {
        const note = document.createElement('span');
        note.textContent = 'Sin ubicación en el mapa';
        button.append(note);
      }
      button.addEventListener('click', () => {
        choose(locker);
        close(true);
      });
      li.append(button);
      list.append(li);
    }
    suggestions.inert = false;
    suggestions.setAttribute('aria-hidden', 'false');
    input.setAttribute('aria-expanded', 'true');
    if (suggestions.hidden) {
      suggestions.hidden = false;
      void suggestions.offsetHeight;
    }
    suggestions.classList.add('is-open');
  }
  input.addEventListener('focus', () => {
    if (document.activeElement === input) show();
  });
  input.addEventListener('click', () => {
    if (suggestions.inert) show();
  });
  input.addEventListener('input', () => {
    if (selected) {
      input.value = selected.label;
      close();
      return;
    }
    selected = null;
    input.dataset.selectedId = '';
    onChoose(null);
    show();
  });
  root.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      close(true);
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (suggestions.inert) show();
      if (suggestions.inert) return;
      const options = [...list.querySelectorAll('button')];
      const current = options.indexOf(
        document.activeElement as HTMLButtonElement,
      );
      const next =
        event.key === 'ArrowDown'
          ? (current + 1) % options.length
          : current <= 0
            ? options.length - 1
            : current - 1;
      options[next]?.focus();
    } else if (event.key === 'Enter' && event.target === input) {
      event.preventDefault();
      if (suggestions.inert) show();
    }
  });
  clear.addEventListener('click', () => {
    choose(null);
    list.replaceChildren();
    close(true);
  });
  suggestions.addEventListener('pointerdown', () => {
    pointerSelecting = true;
  });
  document.addEventListener('pointerup', () =>
    window.setTimeout(() => {
      pointerSelecting = false;
      if (!root.contains(document.activeElement)) close();
    }, 0),
  );
  document.addEventListener('pointercancel', () => {
    pointerSelecting = false;
  });
  root.addEventListener('focusout', (event) => {
    if (
      pointerSelecting ||
      (event.relatedTarget instanceof Node &&
        root.contains(event.relatedTarget))
    )
      return;
    close();
  });
  document.addEventListener('pointerdown', (event) => {
    if (event.target instanceof Node && !root.contains(event.target)) close();
  });
  return {
    select(locker: AvailableLocker) {
      choose(locker);
      close(true);
    },
    close,
    setLockers(next: AvailableLocker[]) {
      lockers = next;
      if (selected && !lockers.some((locker) => locker.id === selected?.id))
        choose(null);
      close();
    },
  };
}
