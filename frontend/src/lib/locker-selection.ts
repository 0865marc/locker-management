import type { AvailableLocker } from './lockers';
function fold(value: string) {
  return value
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLocaleLowerCase('es');
}
export function matchingLockers(
  lockers: AvailableLocker[],
  query: string,
): AvailableLocker[] {
  const needle = fold(query.trim());
  return lockers.filter((locker) =>
    fold(
      [locker.label, locker.address ?? '', locker.postalCode ?? ''].join(' '),
    ).includes(needle),
  );
}
