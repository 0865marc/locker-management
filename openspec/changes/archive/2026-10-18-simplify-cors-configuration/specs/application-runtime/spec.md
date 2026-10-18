# Application Runtime Delta

## MODIFIED Requirements

### Requirement: Allow scoped browser access from explicit origins

CORS SHALL use the existing exact-origin allowlist, without credentials or wildcards. It SHALL permit GET and POST preflights with Content-Type on every path, without route-specific policies. PATCH, DELETE and unsupported headers SHALL remain denied in preflight. Invalid origins SHALL fail configuration; absent/empty configuration SHALL allow none. Endpoint contracts and requests without Origin SHALL remain unchanged; CORS is not authorization.

#### Scenario: Allowed quotation creation and observation
- **WHEN** a listed origin requests preflight for POST /quotations with Content-Type and then submits valid JSON
- **THEN** browser CORS permits the existing POST and subsequent GET /quotations/{id}, without credentials or a proxy
- **AND** GET /lockers remains readable from that same exact origin

#### Scenario: Unlisted origin or unrelated write
- **WHEN** an unlisted origin requests access, or a client requests preflight for PATCH, DELETE or an unsupported header such as Authorization or X-Admin
- **THEN** that preflight is denied and no method or origin wildcard is introduced
- **AND** the policy does not claim to prevent direct HTTP clients from invoking existing endpoints

#### Scenario: No Origin and invalid configuration
- **WHEN** requests omit Origin or the allowlist is configured with an invalid origin
- **THEN** normal endpoint behavior remains unchanged for requests without Origin, while invalid configuration fails clearly before application startup

#### Scenario: Uniform policy beyond quotations
- **WHEN** a listed origin requests GET or POST preflight with Content-Type for /lockers, /deliveries, /returns, /quotations/ or a nonexistent path
- **THEN** the same CORS policy permits that preflight without credentials, regardless of path
- **AND** preflight does not invoke business handlers or create an endpoint; subsequent requests still follow the existing routing and payload validation
