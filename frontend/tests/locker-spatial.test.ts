import { expect, it } from 'vitest';
import { LockerSpatialIndex } from '../src/lib/locker-spatial';
import type { AvailableLocker } from '../src/lib/lockers';
const records = (count: number): AvailableLocker[] =>
  Array.from({ length: count }, (_, n) => ({
    id: String(n),
    label: `Locker ${n}`,
    address: null,
    postalCode: '01001',
    position: [40.4, -3.7],
    freeCount: 1,
  }));
it('counts each unprotected UUID once and rebuilds only changed membership', () => {
  const index = new LockerSpatialIndex();
  index.load(records(45));
  expect(index.protect(new Set(['0', '1']))).toBe(true);
  expect(index.protect(new Set(['1', '0', 'unknown']))).toBe(false);
  const groups = index.visible([-10, 35, 5, 45], 19);
  expect(groups).toHaveLength(1);
  expect(groups[0]!.properties).toMatchObject({
    cluster: true,
    point_count: 43,
  });
  expect(
    index
      .page((groups[0]!.properties as { cluster_id: number }).cluster_id, 0)
      .some((x) => ['0', '1'].includes(x.id)),
  ).toBe(false);
});
it('pages all coincident members exactly once without changing their positions', () => {
  const input = records(45),
    index = new LockerSpatialIndex();
  index.load(input);
  index.protect(new Set());
  const group = index.visible([-10, 35, 5, 45], 19)[0]!;
  const clusterId = (group.properties as { cluster_id: number }).cluster_id;
  expect(index.expansion(clusterId)).toBe(20);
  const pages = [0, 1, 2].map((page) => index.page(clusterId, page));
  expect(pages.map((x) => x.length)).toEqual([20, 20, 5]);
  expect(new Set(pages.flat().map((x) => x.id)).size).toBe(45);
  expect(
    pages
      .flat()
      .every((x) => x.position![0] === 40.4 && x.position![1] === -3.7),
  ).toBe(true);
});
it('keeps absent coordinates in full collection but not geographic results and replaces stale data', () => {
  const index = new LockerSpatialIndex();
  index.load([
    ...records(1),
    { ...records(1)[0]!, id: 'missing', position: null },
  ]);
  index.protect(new Set());
  expect(index.lockers.size).toBe(2);
  expect(index.visible([-10, 35, 5, 45], 19)).toHaveLength(1);
  expect(index.visible([1, 1, 2, 2], 19)).toHaveLength(0);
  index.load([]);
  index.protect(new Set());
  expect(index.visible([-180, -90, 180, 90], 19)).toHaveLength(0);
});
