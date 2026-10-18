import Supercluster, {
  type PointFeature,
  type ClusterFeature,
} from 'supercluster';
import type { AvailableLocker } from './lockers';
export type LockerPoint = PointFeature<{ id: string }>;
export type LockerGroup = ClusterFeature<Record<string, never>>;
export class LockerSpatialIndex {
  private index = new Supercluster<{ id: string }>({ radius: 60, maxZoom: 19 });
  private points: LockerPoint[] = [];
  private excluded = '';
  readonly lockers = new Map<string, AvailableLocker>();
  load(lockers: AvailableLocker[]) {
    this.lockers.clear();
    this.points = [];
    for (const locker of lockers) {
      this.lockers.set(locker.id, locker);
      if (locker.position)
        this.points.push({
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: [locker.position[1], locker.position[0]],
          },
          properties: { id: locker.id },
        });
    }
    this.excluded = '\0';
  }
  protect(ids: Set<string>) {
    const key = [...ids]
      .filter((id) => this.lockers.has(id))
      .sort()
      .join(',');
    if (key === this.excluded) return false;
    this.excluded = key;
    this.index = new Supercluster<{ id: string }>({
      radius: 60,
      maxZoom: 19,
    }).load(this.points.filter((point) => !ids.has(point.properties.id)));
    return true;
  }
  visible(bounds: [number, number, number, number], zoom: number) {
    return this.index.getClusters(bounds, Math.floor(zoom));
  }
  expansion(id: number) {
    return this.index.getClusterExpansionZoom(id);
  }
  page(id: number, page: number) {
    return this.index
      .getLeaves(id, 20, page * 20)
      .map((point) => this.lockers.get(point.properties.id)!);
  }
}
