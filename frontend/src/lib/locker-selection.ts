import type { AvailableLocker } from './lockers';
function fold(value: string) {
  return value
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLocaleLowerCase('es');
}
const indexes = new WeakMap<
  AvailableLocker[],
  { locker: AvailableLocker; text: string }[]
>();
export function matchingLockers(
  lockers: AvailableLocker[],
  query: string,
): AvailableLocker[] {
  const needle = fold(query.trim());
  if (!needle) return [];
  const index = getIndex(lockers);
  const matches: AvailableLocker[] = [];
  for (const entry of index) {
    if (entry.text.includes(needle)) matches.push(entry.locker);
    if (matches.length === 21) break;
  }
  return matches;
}
function getIndex(lockers: AvailableLocker[]) {
  let index = indexes.get(lockers);
  if (!index) {
    index = lockers.map((locker) => ({
      locker,
      text: fold(
        [locker.label, locker.address ?? '', locker.postalCode ?? ''].join(' '),
      ),
    }));
    indexes.set(lockers, index);
  }
  return index;
}
export function prepareLockerSearch(lockers: AvailableLocker[]) {
  getIndex(lockers);
}

export function lockerSuggestionState(
  query: string,
  count: number,
): 'empty' | 'none' | 'refine' | 'matches' {
  if (!query.trim()) return 'empty';
  if (count <= 0) return 'none';
  return count > 20 ? 'refine' : 'matches';
}
