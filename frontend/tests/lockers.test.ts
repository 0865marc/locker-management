import { describe, it, expect } from 'vitest';
import { availableLockers } from '../src/lib/lockers';
const base = {
  id: '00000000-0000-4000-8000-000000000001',
  active: true,
  location_id: null,
  address: null,
  coordinates: { latitude: 40.4, longitude: -3.7 },
  compartments: [{ enabled: true, occupied: false }],
};
describe('contract and availability', () => {
  it('counts only enabled free cells of active lockers', () => {
    const compartments = [
      { enabled: true, occupied: false },
      { enabled: true, occupied: false },
      { enabled: false, occupied: false },
      { enabled: true, occupied: true },
    ];
    expect(availableLockers([{ ...base, compartments }])[0]?.freeCount).toBe(2);
    for (const change of [
      { active: false },
      { compartments: [] },
      { compartments: [{ enabled: false, occupied: false }] },
      { compartments: [{ enabled: true, occupied: true }] },
    ])
      expect(availableLockers([{ ...base, ...change }])).toEqual([]);
  });
  it('uses alias, address then UUID, preserving postal text and literal markup', () => {
    const address = {
      country_code: 'ES',
      postal_code: '01001',
      province: 'Álava',
      city: 'Vitoria',
      street: '<b>Calle</b>',
      street_number: '2',
    };
    expect(availableLockers([base])[0]?.label).toBe(base.id);
    expect(availableLockers([{ ...base, address }])[0]?.label).toContain(
      '01001',
    );
    expect(
      availableLockers([
        { ...base, address, location_id: '<script>test</script>' },
      ])[0]?.label,
    ).toBe('<script>test</script>');
  });
  it.each([
    null,
    {},
    { latitude: 40 },
    { latitude: '40', longitude: 2 },
    { latitude: Infinity, longitude: 2 },
    { latitude: NaN, longitude: 2 },
    { latitude: 91, longitude: 0 },
    { latitude: 40, longitude: -181 },
  ])('retains rows with invalid position %j', (coordinates) => {
    expect(availableLockers([{ ...base, coordinates }])).toMatchObject([
      { position: null, freeCount: 1 },
    ]);
  });
  it('keeps genuine coordinates even outside Spain', () => {
    expect(
      availableLockers([
        { ...base, coordinates: { latitude: -40, longitude: 170 } },
      ])[0]?.position,
    ).toEqual([-40, 170]);
  });
  it.each([
    null,
    {},
    [null],
    [{ ...base, id: 'bad' }],
    [{ ...base, active: 'true' }],
    [{ ...base, location_id: 3 }],
    [{ ...base, address: {} }],
    [{ ...base, address: undefined }],
    [{ ...base, compartments: null }],
    [{ ...base, compartments: [{ enabled: 1, occupied: false }] }],
    [base, base],
  ])('rejects essential malformed data %j', (input) => {
    expect(() => availableLockers(input)).toThrow(
      'datos de lockers no válidos',
    );
  });
});
