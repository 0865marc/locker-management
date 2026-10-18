# Parcel Tracking Spec Delta

## Purpose

Let a visitor locate a known delivery or return by its UUID and distinguish its current custody location from a historical locker assignment, without accessing personal details or complete parcel lists.

## ADDED Requirements

### Requirement: Retrieve one parcel by UUID without mutation

GET /tracking/{id} SHALL search deliveries and returns by the supplied UUID and return 200 for exactly one match, 404 for none, 422 for an invalid UUID and 409 if both flows match. It SHALL NOT enumerate collections, write data, alter custody or consult quotations. Infrastructure failure SHALL remain an error rather than becoming a false not-found result. Existing endpoints and custody transitions SHALL remain unchanged.

#### Scenario: A known delivery or return
- **WHEN** a valid UUID identifies exactly one saved delivery or return
- **THEN** the response describes that record through targeted reads only, without collection reads, writes or provider calls

#### Scenario: Unknown, invalid or ambiguous UUID
- **WHEN** the UUID is unknown, malformed, or exists in both flows
- **THEN** the endpoint returns respectively 404, 422 or 409, without choosing a flow arbitrarily or exposing other records
- **AND** a quotation UUID alone does not identify a tracked parcel

### Requirement: Return only the public tracking projection

A successful response SHALL contain exactly id, kind, status, locker_relation, locker_id and locker. id SHALL be the requested UUID; kind SHALL be delivery or return. locker_id SHALL be a UUID or null. locker SHALL be null or contain only location_id, address and coordinates. The response SHALL omit recipient/sender names, phones, carrier tracking numbers, compartment data and unrelated records.

#### Scenario: Minimal typed payload
- **WHEN** an assigned delivery is found with locker metadata
- **THEN** kind is "delivery", status is one of AWAITING_PICKUP/COLLECTED/RETURNED_TO_CARRIER, locker_id identifies its assignment and locker contains its nullable alias, address and coordinates
- **AND** a return instead uses kind "return" with status AWAITING_CARRIER or HANDED_OVER
- **AND** location_id is text or null; address is null or the existing street/street_number/postal_code/city/province/country_code text object; coordinates is null or finite latitude/longitude in WGS84 bounds

#### Scenario: Personal fields exist in storage
- **WHEN** the stored parcel includes personal names, phone or carrier tracking data
- **THEN** none of those fields appears in the tracking JSON or public result

### Requirement: Distinguish current custody from historical assignment

locker_relation SHALL be "unassigned" with null locker_id and locker when no assignment exists. Assigned AWAITING_PICKUP deliveries and AWAITING_CARRIER returns SHALL use "current". Assigned COLLECTED, RETURNED_TO_CARRIER and HANDED_OVER records SHALL use "last_known". The retained assignment SHALL NOT imply that a departed parcel remains in the locker, and elapsed pickup deadlines SHALL NOT invent new states.

#### Scenario: Current and departed parcels
- **WHEN** an assigned pending parcel is located, then leaves custody and is located again
- **THEN** its relation changes from current to last_known while retaining the recorded locker identifier and its actual terminal state
- **AND** the public UI labels these as current locker and last registered locker respectively

#### Scenario: Unassigned or overdue reception
- **WHEN** reception has no locker assignment, or a pending delivery has passed its pickup deadline
- **THEN** no assignment is invented and the saved custody state is preserved

### Requirement: Preserve tracking when locker details are unavailable

Tracking SHALL resolve the assigned locker regardless of active state or free capacity. Missing locker metadata SHALL yield locker null while retaining locker_id, custody status and the current/last_known relation. Missing address or coordinates SHALL remain null and SHALL NOT be inferred or geocoded. Locker metadata SHALL describe the stored locker record, without claiming a historical address snapshot.

#### Scenario: Full or inactive locker
- **WHEN** the parcel belongs to a full or inactive locker
- **THEN** tracking still returns that locker independently of the available-destination filter

#### Scenario: Missing locker or coordinates
- **WHEN** the parcel has an assignment but the locker read returns no metadata or no coordinates
- **THEN** the result retains status and assignment, explains the missing location details and does not draw a fabricated marker

### Requirement: Locate explicitly with cancellable browser reads

The tracking view SHALL accept a parcel UUID and submit only on "Localizar paquete" or Enter. Invalid input SHALL show an error before HTTP. A valid attempt SHALL use one credential-free, no-store GET with a five-second timeout and no automatic polling. Editing, a newer attempt or leaving the view SHALL cancel and invalidate previous work. Loading, not-found and failure SHALL remain distinct, with explicit retry.

#### Scenario: Submit and recover
- **WHEN** a visitor submits a valid UUID, receives a not-found/error response and tries again explicitly
- **THEN** each attempt makes one targeted tracking GET, never GET /deliveries, GET /returns or any POST
- **AND** valid status/locker text remains useful if map tiles fail

#### Scenario: A stale response arrives
- **WHEN** a response arrives after a newer UUID, input edit or tab change
- **THEN** it cannot replace current results, move the map or reopen inactive content

### Requirement: Keep the tracking marker independent of quotation availability

A tracking position SHALL use a separate current/last-registered marker without changing counts or quotation inputs. No coordinates SHALL mean no marker. Opening a marker popup SHALL NOT change modes or selections. Only an explicit pickup/delivery action for a currently available locker SHALL activate quotation and select that role. A tracking locker absent from the available collection SHALL remain informative without selection actions. Leaving tracking SHALL hide or remove its marker.

#### Scenario: Historical or unavailable destination is tracked
- **WHEN** tracking finds an inactive/full locker or a terminal parcel with coordinates
- **THEN** its separate marker reveals the recorded location with the correct current/historical label while availability counts and quotation inputs remain unchanged
- **AND** inspecting a marker does not start a quotation or change tabs; an unavailable tracking locker offers no role-selection action

#### Scenario: Explicitly use an available locker while tracking
- **WHEN** a visitor opens a popup for a currently available locker in tracking mode and chooses pickup or delivery
- **THEN** only that explicit action activates quotation, sets the chosen role from the available record and closes the popup
- **AND** tracking metadata alone never establishes availability, counts remain unchanged and no quotation POST is triggered
