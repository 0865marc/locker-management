# shipping-quotes Specification

## Purpose

Compare normalized shipping offers from interchangeable providers using postal route, weight and dimensions, independently of lockers, HTTP and persistent quote history.

## Requirements

### Requirement: Compare transport data without a locker

The comparator SHALL accept origin/destination country and postal code, weight and dimensions without a locker, persisted parcel, HTTP context or database. Countries SHALL be ES, postal codes five ASCII digits, weight an integer in 1..30000 grams and each dimension an integer in 1..2000 millimetres. Booleans SHALL not count as numbers. Invalid inputs SHALL fail before provider calls; comparison SHALL neither persist data nor alter custody.

#### Scenario: Reuse directly without infrastructure
- **WHEN** a caller supplies valid transport data and simulated providers without services or a locker
- **THEN** it receives normalized results directly without consulting persistence or reserving space

#### Scenario: Input boundaries and postal text
- **WHEN** inputs contain postal code "01001", valid numeric boundaries, or malformed/out-of-range fields
- **THEN** valid values and leading zeroes are preserved, while invalid country/postal/numeric values are rejected before provider calls

### Requirement: Accept an explicit extensible provider collection

Comparison SHALL use an explicitly supplied nonempty provider collection. Provider codes SHALL be nonblank trimmed case-sensitive strings and unique within that collection. Invalid collections SHALL fail before calls. Results SHALL contain one entry per supplied provider, ordered by code, without assuming exactly three. Adding a provider SHALL not require changes to the common comparison rules.

#### Scenario: Fourth provider without central branches
- **WHEN** a fourth contract-compatible adapter is supplied alongside the three simulators
- **THEN** all four are queried and appear once without modifying the common comparator or adding provider-specific conditions

#### Scenario: Invalid collection is rejected
- **WHEN** configuration supplies no providers, duplicate codes or blank/untrimmed codes
- **THEN** it fails clearly before any provider call rather than restoring defaults or silently dropping entries

### Requirement: Normalize offers and distinguish business rejection from failure

Each result SHALL expose provider_code, status QUOTED/NOT_COVERED/FAILED, offers and error_code. QUOTED SHALL have nonempty offers and null error; NOT_COVERED SHALL have empty offers and null error; FAILED SHALL have empty offers and PROVIDER_TIMEOUT or PROVIDER_ERROR. Offers SHALL have unique trimmed nonblank service_code, positive integer price_cents/EUR and positive integer transit_days_min/max with min <= max, in natural days from dispatch.

#### Scenario: Multiple services per provider
- **WHEN** one provider returns economy and express offers
- **THEN** both appear under that provider, ordered by service_code, with normalized price and transit interval

#### Scenario: Business rejection and partial technical failure
- **WHEN** one provider declines coverage, another returns offers and another fails technically or returns malformed data
- **THEN** their results are respectively NOT_COVERED, QUOTED and FAILED/PROVIDER_ERROR, retaining the offers and exposing no external payloads or credentials

#### Scenario: No offers from any provider
- **WHEN** every provider reports no coverage or technical failure
- **THEN** every provider remains identifiable with its own terminal outcome and no aggregate status or historical identifier is needed

### Requirement: Bound independent calls without automatic retries

The comparator SHALL allow at most three concurrent provider calls by default and a two-second timeout per call after admission to a slot. Timeout SHALL produce PROVIDER_TIMEOUT while preserving other results. Calls SHALL not be retried automatically. Waiting for admission SHALL not consume a call timeout. There SHALL be no promise of constant total latency as the number of providers increases.

#### Scenario: More providers than available slots
- **WHEN** more than three providers are supplied and active calls are held at observable barriers
- **THEN** at most three calls run simultaneously and waiting calls begin as slots become free, each invoked at most once

#### Scenario: Slow provider preserves fast offers
- **WHEN** one provider exceeds its call timeout while others finish successfully
- **THEN** its result is FAILED/PROVIDER_TIMEOUT and the successful offers are retained without retry

### Requirement: Keep cancellation owned by the caller

Cancelling comparison SHALL propagate cancellation after cancelling and awaiting active and waiting child calls. Cancellation SHALL not become a provider error or leave detached background work. Adapters SHALL cooperate with cancellation; future transport-specific termination guarantees SHALL remain their responsibility.

#### Scenario: Cancel active and waiting work
- **WHEN** the caller cancels comparison while some calls are active and others wait for a slot
- **THEN** cancellation propagates, children are cleaned up and no provider call remains active or starts afterwards

### Requirement: Supply three deterministic example adapters

Simulators SHALL be sim-economy, sim-standard and sim-express with one corresponding service each. Using kg=ceil(max(weight_grams,ceil(volume_mm3/5000))/1000) and zone=0 for equal two-digit postal prefixes, otherwise 1, prices SHALL be 250+40*kg+100*zone, 400+60*kg+150*zone and 650+90*kg+200*zone cents. Their min/max days SHALL both be 3+zone, 2+zone and 1+zone respectively. They SHALL use no external APIs or random pricing.

#### Scenario: Direct illustrative comparison
- **WHEN** a caller supplies the three simulators and a 1200 g parcel measuring 200 by 150 by 100 mm within one postal prefix
- **THEN** economy returns 330 cents and 3–3 days, standard 520 cents and 2–2 days, and express 830 cents and 1–1 day

#### Scenario: Numeric extremes remain deterministic
- **WHEN** maximum valid dimensions and weight are compared repeatedly
- **THEN** each adapter returns the same bounded integer amounts without monetary floating-point rounding or storage
