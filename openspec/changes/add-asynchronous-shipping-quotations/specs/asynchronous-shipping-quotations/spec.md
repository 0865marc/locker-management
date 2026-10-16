# Spec Delta

## Purpose

Queue shipping comparisons for a single worker and preserve requests, provider outcomes and offers for later consultation, without automatic retries or recovery.

## ADDED Requirements

### Requirement: Save and enqueue a quotation once

POST /quotations SHALL validate the existing shipping input, save a new PENDING request and publish its identifier once. It SHALL return 202 with id, PENDING status and Location only after publication confirmation, without calling providers. Invalid input or unknown fields SHALL return 422 without stored work. A failed initial write SHALL return 503 without publication.

#### Scenario: Enqueue valid input
- **WHEN** valid ES transport input is submitted and persistence and publication succeed
- **THEN** the request, including postal leading zeroes, is saved and 202 identifies it before any provider comparison is required to finish

#### Scenario: Invalid input
- **WHEN** countries, postal codes, weight, dimensions or extra fields violate the existing input contract
- **THEN** 422 is returned without storing or publishing a quotation

### Requirement: Report publication failure without provider results

A failed publication SHALL return 503 with the saved quotation identifier and SHALL attempt to mark that still-pending request FAILED with process_error_code PUBLISH_ERROR when persistence is available. It SHALL not retry publication or fabricate provider results. Saving and publication SHALL have no atomicity or automatic repair guarantee.

#### Scenario: Broker rejects or cannot receive publication
- **WHEN** the request is saved but its single publication attempt fails
- **THEN** 503 identifies the saved request, FAILED/PUBLISH_ERROR is recorded if possible, and no provider is reported as failed merely because publication failed

### Requirement: Execute one comparison and retain provider outcomes

A single worker SHALL process quotations sequentially using the current provider configuration. It SHALL mark a pending request PROCESSING, compare once and atomically store all results/offers with COMPLETED. Existing QUOTED/NOT_COVERED/FAILED statuses, error codes, pricing and provider/service ordering SHALL remain unchanged. Provider errors and timeouts SHALL not be retried.

#### Scenario: Successful and failed providers together
- **WHEN** comparison returns offers from one provider, a technical error from another and no coverage from a third
- **THEN** the quotation completes with QUOTED offers, FAILED/PROVIDER_ERROR and NOT_COVERED, preserving each provider and any multiple services

#### Scenario: No response times out without retry
- **WHEN** one provider does not answer within the existing admitted-call timeout
- **THEN** it is called once and recorded as FAILED/PROVIDER_TIMEOUT while other outcomes are retained; even an all-failed result set completes the quotation

### Requirement: Consume without requeue or automatic recovery

The worker SHALL acknowledge each delivery before reading or processing its quotation, and SHALL not begin comparison if acknowledgement fails. It SHALL not requeue, republish or automatically recover consumed work. Invalid messages and requests no longer PENDING SHALL be ignored. A process or database failure can leave PENDING/PROCESSING indefinitely; no exactly-once guarantee SHALL be claimed.

#### Scenario: Acknowledge before execution
- **WHEN** a worker receives a valid message and executes a comparison ending in provider failures
- **THEN** acknowledgement precedes provider calls, the result is stored once and the consumed job is not requeued or replayed

#### Scenario: Unexpected processing failure
- **WHEN** processing raises an unexpected error after consumption
- **THEN** it attempts to record FAILED/PROCESSING_ERROR if persistence allows, without invented provider outcomes or another comparison; no final error record is guaranteed if the process or database is unavailable

### Requirement: Retrieve saved requests and results

GET /quotations/{id} SHALL return id, original request, status, UTC created_at/finished_at, process_error_code and results. PENDING/PROCESSING SHALL have empty results and null finished_at; COMPLETED SHALL expose the complete normalized result set; FAILED SHALL expose its process error. Unknown UUID SHALL return 404, malformed UUID 422 and unavailable persistence 503. Reads SHALL remain coherent with the committed state.

#### Scenario: Read from a new instance
- **WHEN** an API instance reads a pending, completed or failed quotation saved by another instance
- **THEN** it retrieves the same request and committed state, with preserved offers/provider errors or process error, without ranking offers or invoking providers
