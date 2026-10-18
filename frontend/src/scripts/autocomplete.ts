import { searchPlaces, isPostalCode, type Place } from '../lib/geocoder';
export function setupAutocomplete(
  prefix: string,
  options: { onSelect(place: Place, postal: boolean): void; onEdit?(): void },
) {
  function element<T extends HTMLElement>(id: string): T {
    const node = document.getElementById(id);
    if (!node) throw new Error(`Falta ${id}`);
    return node as T;
  }
  const searchForm = element<HTMLFormElement>(`${prefix}-search`);
  const searchInput = element<HTMLInputElement>(`${prefix}-query`);
  const suggestions = element(`${prefix}-suggestions`);
  const searchStatus = element(`${prefix}-status`);
  const searchResults = element(`${prefix}-results`);
  const searchRetry = element<HTMLButtonElement>(`${prefix}-retry`);
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let searchGeneration = 0;
  let pendingSearch: AbortController | null = null;
  let debounceTimer: number | undefined;
  let hideTimer: number | undefined;
  let animationGeneration = 0;
  let pointerSelecting = false;
  function showSuggestions(open: boolean): void {
    const animation = ++animationGeneration;
    clearTimeout(hideTimer);
    suggestions.inert = !open;
    suggestions.setAttribute('aria-hidden', String(!open));
    searchInput.setAttribute('aria-expanded', String(open));
    if (open) {
      if (suggestions.hidden) {
        suggestions.hidden = false;
        // Measure the collapsed state before starting the CSS transition.
        void suggestions.offsetHeight;
      }
      suggestions.classList.add('is-open');
    } else {
      suggestions.classList.remove('is-open');
      if (reducedMotion.matches || suggestions.hidden)
        suggestions.hidden = true;
      else
        hideTimer = window.setTimeout(() => {
          if (animation === animationGeneration) suggestions.hidden = true;
        }, 160);
    }
  }
  function cancelSearch(): void {
    searchGeneration++;
    clearTimeout(debounceTimer);
    pendingSearch?.abort();
    pendingSearch = null;
    searchForm.removeAttribute('aria-busy');
  }
  function closeSuggestions(restoreFocus = false): void {
    cancelSearch();
    if (restoreFocus) searchInput.focus({ preventScroll: true });
    showSuggestions(false);
  }
  function locate(place: Place, postal: boolean): void {
    searchInput.value = place.label;
    closeSuggestions(true);
    options.onSelect(place, postal);
  }
  async function findSuggestions(
    query: string,
    generation: number,
  ): Promise<void> {
    if (generation !== searchGeneration) return;
    const controller = new AbortController();
    pendingSearch = controller;
    searchForm.setAttribute('aria-busy', 'true');
    searchResults.replaceChildren();
    searchRetry.hidden = true;
    searchStatus.hidden = false;
    searchStatus.className = 'loading';
    searchStatus.textContent = 'Buscando ubicaciones…';
    showSuggestions(true);
    try {
      const places = await searchPlaces(query, controller.signal);
      if (generation !== searchGeneration || controller.signal.aborted) return;
      searchStatus.className = '';
      searchStatus.hidden = places.length > 0;
      if (!places.length)
        searchStatus.textContent =
          'No se han encontrado ubicaciones en España.';
      for (const [index, place] of places.entries()) {
        const li = document.createElement('li');
        li.setAttribute('role', 'presentation');
        const button = document.createElement('button');
        button.type = 'button';
        button.id = `${prefix}-suggestion-${generation}-${index}`;
        button.setAttribute('role', 'option');
        button.setAttribute('aria-selected', 'false');
        button.textContent = place.label;
        button.addEventListener('click', () =>
          locate(place, isPostalCode(query)),
        );
        li.append(button);
        searchResults.append(li);
      }
    } catch (error) {
      if (generation !== searchGeneration || controller.signal.aborted) return;
      searchStatus.className = 'error';
      searchStatus.textContent =
        error instanceof Error
          ? error.message
          : 'No se ha podido completar la búsqueda.';
      searchRetry.hidden = false;
    } finally {
      if (generation === searchGeneration) {
        pendingSearch = null;
        searchForm.removeAttribute('aria-busy');
      }
    }
  }
  searchInput.addEventListener('input', () => {
    options.onEdit?.();
    cancelSearch();
    showSuggestions(false);
    const query = searchInput.value.trim();
    if (query.length < 3) return;
    const generation = searchGeneration;
    debounceTimer = window.setTimeout(
      () => void findSuggestions(query, generation),
      350,
    );
  });
  searchForm.addEventListener('submit', (event) => event.preventDefault());
  searchRetry.addEventListener('click', () => {
    searchInput.focus({ preventScroll: true });
    const query = searchInput.value.trim();
    cancelSearch();
    if (query.length >= 3) void findSuggestions(query, searchGeneration);
  });
  searchForm.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      closeSuggestions(true);
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      if (suggestions.inert) return;
      const buttons = [...searchResults.querySelectorAll('button')];
      if (!buttons.length) return;
      event.preventDefault();
      const current = buttons.indexOf(
        document.activeElement as HTMLButtonElement,
      );
      const next =
        event.key === 'ArrowDown'
          ? (current + 1) % buttons.length
          : current <= 0
            ? buttons.length - 1
            : current - 1;
      buttons[next]?.focus();
    }
  });
  // Keep blur from dismissing a touch/click before the candidate receives it.
  suggestions.addEventListener('pointerdown', () => {
    pointerSelecting = true;
  });
  document.addEventListener('pointerup', () => {
    window.setTimeout(() => {
      pointerSelecting = false;
      if (!searchForm.contains(document.activeElement)) closeSuggestions();
    }, 0);
  });
  document.addEventListener('pointercancel', () => {
    pointerSelecting = false;
  });
  searchForm.addEventListener('focusout', (event) => {
    if (
      pointerSelecting ||
      (event.relatedTarget instanceof Node &&
        searchForm.contains(event.relatedTarget))
    )
      return;
    closeSuggestions();
  });
  document.addEventListener('pointerdown', (event) => {
    if (event.target instanceof Node && !searchForm.contains(event.target))
      closeSuggestions();
  });

  return { close: () => closeSuggestions() };
}
