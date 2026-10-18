import { describe, expect, it } from 'vitest';
import {
  matchingLockers,
  prepareLockerSearch,
  lockerSuggestionState,
} from '../src/lib/locker-selection';
import type { AvailableLocker } from '../src/lib/lockers';

const lockers: AvailableLocker[] = [
  {
    id: 'uuid-one',
    label: 'Álava Centro',
    address: 'Calle Mayor 2, Vitoria',
    postalCode: '01001',
    position: [42.85, -2.67],
    freeCount: 1,
  },
  {
    id: 'uuid-two',
    label: 'Coincidente',
    address: null,
    postalCode: null,
    position: [42.85, -2.67],
    freeCount: 2,
  },
  {
    id: 'uuid-three',
    label: 'Coincidente',
    address: 'Calle del Mar, Palma',
    postalCode: '07001',
    position: null,
    freeCount: 1,
  },
];

describe('local locker candidates', () => {
  it('matches labels independently of whitespace, case and composed accents', () => {
    expect(matchingLockers(lockers, ' ALAVA ')).toEqual([lockers[0]]);
    expect(matchingLockers(lockers, 'a\u0301lava')).toEqual([lockers[0]]);
  });
  it('matches the recorded address and preserves textual postal zeroes', () => {
    expect(matchingLockers(lockers, 'MAYOR 2')).toEqual([lockers[0]]);
    expect(matchingLockers(lockers, '01001')).toEqual([lockers[0]]);
    expect(matchingLockers(lockers, '07001')).toEqual([lockers[2]]);
    expect(matchingLockers(lockers, '7001')).toEqual([lockers[2]]);
  });
  it('preserves order and each identity for duplicate, coincident and unmapped lockers', () => {
    expect(matchingLockers(lockers, 'coincidente')).toEqual([
      lockers[1],
      lockers[2],
    ]);
    expect(matchingLockers(lockers, '')).toEqual([]);
    expect(matchingLockers(lockers, '   ')).toEqual([]);
  });
  it('does not treat UUIDs or arbitrary geographic text as a selected locker', () => {
    expect(matchingLockers(lockers, 'uuid-one')).toEqual([]);
    expect(matchingLockers(lockers, 'unregistered address')).toEqual([]);
  });
  it('stops at sentinel 21 without mutating the input', () => {
    const many = Array.from({ length: 30 }, (_, index) => ({
      ...lockers[0]!,
      id: String(index),
    }));
    const before = structuredClone(many);
    expect(matchingLockers(many, 'centro')).toHaveLength(21);
    expect(many).toEqual(before);
  });
});

describe('bounded suggestion gate', () => {
  it.each([
    ['', 0, 'empty'],
    [' ', 20, 'empty'],
    ['', 21, 'empty'],
    ['a', 0, 'none'],
    ['a', 1, 'matches'],
    ['a', 20, 'matches'],
    ['a', 21, 'refine'],
    [' a ', 1, 'matches'],
  ])('gates query %j and count %s', (query, count, state) =>
    expect(lockerSuggestionState(String(query), Number(count))).toBe(state),
  );
});

it('prepares normalized fields once per collection, without reading them on each query', () => {
  let reads = 0;
  const items = [
    {
      ...lockers[0]!,
      get label() {
        reads++;
        return 'Álava';
      },
    },
  ];
  expect(matchingLockers(items, '')).toEqual([]);
  expect(reads).toBe(0);
  prepareLockerSearch(items);
  const prepared = reads;
  expect(matchingLockers(items, 'alava')).toHaveLength(1);
  expect(matchingLockers(items, '01001')).toHaveLength(1);
  prepareLockerSearch(items);
  expect(reads).toBe(prepared);
});
