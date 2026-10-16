# Spec Delta

## MODIFIED Requirements

### Requirement: Supply three deterministic example adapters

Simulators SHALL be sim-economy, sim-standard and sim-express with one corresponding service each. Using kg=ceil(max(weight_grams,ceil(volume_mm3/5000))/1000) and zone=0 for equal two-digit postal prefixes, otherwise 1, prices SHALL be 250+40*kg+100*zone, 400+60*kg+150*zone and 650+90*kg+200*zone cents. Their min/max days SHALL both be 3+zone, 2+zone and 1+zone respectively. They SHALL use no external APIs or random pricing. Without an explicit simulation profile they SHALL retain zero added delay and zero error/no-response probabilities.

#### Scenario: Direct illustrative comparison
- **WHEN** a caller supplies the three simulators without behavior overrides and a 1200 g parcel measuring 200 by 150 by 100 mm within one postal prefix
- **THEN** economy returns 330 cents and 3–3 days, standard 520 cents and 2–2 days, and express 830 cents and 1–1 day

#### Scenario: Numeric extremes remain deterministic
- **WHEN** maximum valid dimensions and weight are compared repeatedly with zero error/no-response probabilities
- **THEN** each successful adapter response returns the same bounded integer amounts without monetary floating-point rounding or storage

## ADDED Requirements

### Requirement: Simulate configurable delay and failure

Simulators SHALL support finite delay bounds 0 <= min <= max and disjoint error/no-response probabilities in [0,1] with sum <= 1; booleans SHALL be rejected. Each call SHALL wait a uniformly selected delay, then return its unchanged tariff, raise a technical error or wait cooperatively until timeout/cancellation. Invalid configuration SHALL fail before calls. Randomness and waiting SHALL be controllable for tests.

#### Scenario: Invalid simulation settings
- **WHEN** delays are negative/reversed, values are nonfinite or boolean, or probabilities exceed their individual or combined limits
- **THEN** configuration fails before provider calls

#### Scenario: Deterministic success, error and timeout checks
- **WHEN** controlled randomness/waiting force success, technical error and no response within comparisons
- **THEN** successful pricing is unchanged, error becomes PROVIDER_ERROR and no response becomes PROVIDER_TIMEOUT without retries; cancellation cleans up waiting calls
