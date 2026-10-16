# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: Supply three deterministic example adapters`
- TO: `### Requirement: Supply three example adapters with deterministic tariffs`

## MODIFIED Requirements

### Requirement: Supply three example adapters with deterministic tariffs

Simulators SHALL be sim-economy, sim-standard and sim-express with one corresponding service each. Using kg=ceil(max(weight_grams,ceil(volume_mm3/5000))/1000) and zone=0 for equal two-digit postal prefixes, otherwise 1, successful prices SHALL be 250+40*kg+100*zone, 400+60*kg+150*zone and 650+90*kg+200*zone cents. Their min/max days SHALL both be 3+zone, 2+zone and 1+zone respectively. They SHALL use no external APIs or random pricing. Direct construction SHALL use each provider's stochastic behavior rather than guarantee success or zero delay.

#### Scenario: Direct illustrative comparison
- **WHEN** all three simulators succeed for a 1200 g parcel measuring 200 by 150 by 100 mm within one postal prefix
- **THEN** economy returns 330 cents and 3–3 days, standard 520 cents and 2–2 days, and express 830 cents and 1–1 day

#### Scenario: Numeric extremes remain deterministic
- **WHEN** maximum valid dimensions and weight are compared repeatedly and a provider returns successful offers
- **THEN** its offers retain the same bounded integer amounts without monetary floating-point rounding or storage, independently of random timing and failures

## ADDED Requirements

### Requirement: Construct self-contained simulators with fixed profiles

Each simulator SHALL expose zero-argument construction and its own private immutable delay bounds and no-response/error probabilities. Callers SHALL not supply a profile, random generator or wait function. The same fixed profile SHALL apply in direct use and in the worker, without environment overrides.

#### Scenario: Distinct fixed behavior per provider
- **WHEN** economy, standard and express are constructed without arguments
- **THEN** their delay/no-response/error settings are respectively 0.2–0.8 s/0.10/0.15, 0.1–0.5 s/0.05/0.10 and 0.05–0.2 s/0.02/0.05

#### Scenario: No constructor configuration
- **WHEN** a caller attempts to pass a profile, RNG or wait function to a simulator constructor
- **THEN** construction rejects those arguments rather than replacing the provider's own behavior

### Requirement: Apply cooperative stochastic behavior without changing tariffs

Each call SHALL wait a uniformly selected delay within its fixed range, then return its unchanged tariff, raise a technical error or wait cooperatively until timeout/cancellation. No response and error SHALL be disjoint random outcomes with their fixed probabilities. The existing comparator SHALL normalize error/timeout and preserve its no-retry and cancellation contracts.

#### Scenario: Controlled success, error and timeout
- **WHEN** tests control execution-time randomness/waiting to exercise each outcome
- **THEN** successful pricing is unchanged, error becomes PROVIDER_ERROR and no response becomes PROVIDER_TIMEOUT without retries; cancellation cleans up waiting calls
