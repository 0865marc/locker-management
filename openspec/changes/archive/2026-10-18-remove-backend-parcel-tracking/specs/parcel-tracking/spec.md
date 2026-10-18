# Parcel Tracking Delta

## ADDED Requirements

### Requirement: Keep backend tracking unavailable

The backend SHALL NOT expose a parcel-tracking endpoint or advertise tracking paths or dedicated response schemas in OpenAPI. GET /tracking/{id} SHALL receive the ordinary 404 for a missing route. Existing delivery, return, locker and quotation contracts, custody data and CORS policy SHALL remain unchanged.

#### Scenario: Requests after withdrawal
- **WHEN** a client reads OpenAPI or requests GET /tracking/{id} with a valid or malformed identifier
- **THEN** OpenAPI contains no tracking path or dedicated tracking schema and either GET returns route-not-found 404
- **AND** the existing endpoints remain available with their previous contracts and CORS behavior

## REMOVED Requirements

### Requirement: Retrieve one parcel by UUID without mutation

**Reason**: The user has withdrawn the backend tracking feature. The application SHALL no longer expose GET /tracking/{id} or advertise it in OpenAPI; requests to the removed route receive the normal 404 for an absent endpoint.
**Migration**: There is no replacement tracking API. Preserve existing delivery, return, locker and quotation endpoints, repository ports and stored data. The retained frontend remains a pending integration and SHALL NOT fall back to downloading parcel collections.

### Requirement: Return only the public tracking projection

**Reason**: The backend tracking response contract and its dedicated projection are removed with the endpoint.
**Migration**: Remove the tracking-only models and HTTP schemas; do not alter the existing delivery/return representations or their business tracking_number fields. Compatible browser fixtures are client tests, not a replacement backend service.

### Requirement: Distinguish current custody from historical assignment

**Reason**: The application no longer provides a tracking projection that derives current or last-known locker relations.
**Migration**: Preserve actual custody states, assignment history and persistence. The retained frontend may still render those labels from compatible test or future integration responses without requiring a backend tracking implementation.

### Requirement: Preserve tracking when locker details are unavailable

**Reason**: Resolving locker metadata for a tracked parcel is removed together with the tracking use case.
**Migration**: Keep existing locker reads and availability behavior unchanged. Do not infer locations or recreate tracking through a fallback endpoint, collection download or test-server service.

## MODIFIED Requirements

### Requirement: Locate explicitly with cancellable browser reads

The tracking view SHALL accept a parcel UUID and submit only on "Localizar paquete" or Enter. Invalid input SHALL show an error before HTTP. A valid attempt SHALL use one credential-free, no-store GET with a five-second timeout and no automatic polling. Editing, a newer attempt or leaving the view SHALL cancel and invalidate previous work. Loading, not-found and failure SHALL remain distinct, with explicit retry.

#### Scenario: Submit and recover
- **WHEN** a visitor submits a valid UUID, receives a not-found/error response and tries again explicitly
- **THEN** each attempt makes one targeted tracking GET, never GET /deliveries, GET /returns or any POST
- **AND** if a compatible test or future integration response is supplied, valid status/locker text remains useful if map tiles fail

#### Scenario: The configured backend has no tracking endpoint
- **WHEN** a visitor submits a valid UUID against the application after backend tracking removal
- **THEN** the backend returns its ordinary route-not-found 404 and the existing frontend shows its not-found state without a result or tracking marker
- **AND** returning to quotation preserves the functioning locker and quotation workflows without a tracking fallback

#### Scenario: A stale response arrives
- **WHEN** a compatible response arrives after a newer UUID, input edit or tab change
- **THEN** it cannot replace current results, move the map or reopen inactive content

### Requirement: Keep the tracking marker independent of quotation availability

A tracking position SHALL use a separate current/last-registered marker without changing counts or quotation inputs. No coordinates SHALL mean no marker. Opening a marker popup SHALL NOT change modes or selections. Only an explicit pickup/delivery action for a currently available locker SHALL activate quotation and select that role. A tracking locker absent from the available collection SHALL remain informative without selection actions. Leaving tracking SHALL hide or remove its marker.

#### Scenario: Historical or unavailable destination is tracked
- **WHEN** a compatible test or future integration response describes an inactive/full locker or a terminal parcel with coordinates
- **THEN** its separate marker reveals the recorded location with the correct current/historical label while availability counts and quotation inputs remain unchanged
- **AND** inspecting a marker does not start a quotation or change tabs; an unavailable tracking locker offers no role-selection action

#### Scenario: Explicitly use an available locker while tracking
- **WHEN** a visitor opens a popup for a currently available locker in tracking mode and chooses pickup or delivery
- **THEN** only that explicit action activates quotation, sets the chosen role from the available record and closes the popup
- **AND** tracking metadata alone never establishes availability, counts remain unchanged and no quotation POST is triggered
