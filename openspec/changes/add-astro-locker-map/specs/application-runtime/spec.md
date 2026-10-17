# Application Runtime Spec Delta

## ADDED Requirements

### Requirement: Generate synthetic lockers manually through the API

The repository SHALL provide a manually invoked script that creates 250 synthetic lockers by default using the existing POST /lockers API. It SHALL support a positive count through --count, API base URL, reproducible random seed and a dry run without HTTP writes. Generated lockers SHALL be active with enabled free compartments, a synthetic alias, null address and terrestrial coordinates within the bundled Spanish boundary. Startup and builds SHALL NOT run the script automatically.

#### Scenario: Create the requested demonstration collection
- **WHEN** the script runs against an empty dedicated API with default count and successful responses
- **THEN** exactly 250 lockers are created and appear as available in the existing list/map
- **AND** every generated coordinate belongs to the bundled Spanish land geometry, rather than an unrestricted bounding rectangle

#### Scenario: Override the default quantity
- **WHEN** the script runs with --count 12 and all creation requests succeed
- **THEN** exactly 12 new lockers are added regardless of the existing collection size
- **AND** existing lockers are preserved

#### Scenario: Reproduce generation without writing
- **WHEN** two dry runs use the same seed, count and boundary version
- **THEN** they produce the same ordered creation payloads without making API requests
- **AND** reproducibility covers coordinates and input fields, not UUIDs generated later by the server

### Requirement: Report partial demonstration creation without destructive recovery

The generator SHALL validate its options before sending data, issue bounded sequential creation requests and stop on the first failed or uncertain response. It SHALL report confirmed creations and the failure, return a nonzero exit code, and preserve all existing data. It SHALL NOT retry writes blindly, delete lockers or claim a batch rollback. Documentation SHALL identify synthetic data and explain that another execution adds new records.

#### Scenario: Partial or uncertain failure
- **WHEN** a creation request fails or times out after earlier requests succeeded
- **THEN** the script reports the confirmed count and affected item, stops further creation and makes no retry or deletion
- **AND** an uncertain final request is not reported as a confirmed creation

### Requirement: Build and serve a fully static frontend

The repository SHALL provide locked frontend dependencies and documented development, build and static-preview commands. A build SHALL generate only static HTML, CSS and browser assets in `frontend/dist`, without reading locker data. The output SHALL run on a generic static HTTP host without an application server or server-side functions. Existing backend Compose services and persistence SHALL remain independent of the frontend.

#### Scenario: Build while the backend is offline
- **WHEN** dependencies are installed and the frontend is built while the configured API is unavailable
- **THEN** the static build succeeds without requesting lockers or embedding a locker snapshot
- **AND** serving `dist` from a generic static HTTP server delivers the page, whose browser code handles API availability at visit time

#### Scenario: Preserve backend startup
- **WHEN** an operator starts only the existing backend services with Compose or runs its smoke script
- **THEN** migrations, API, broker, worker and named volumes retain their existing behavior without requiring a frontend container

### Requirement: Serve the static frontend through Compose

Default Compose startup SHALL include a frontend serving only the generated static files at `http://127.0.0.1:4321`. Its image SHALL build without the API and run without Node or an API proxy. Compose SHALL pass `PUBLIC_API_BASE_URL` at build time, defaulting to `http://127.0.0.1:8000` when unset. Browser API reads SHALL remain direct. The CI Compose override SHALL publish no frontend host port.

#### Scenario: Start the complete application locally
- **WHEN** an operator runs `docker compose up --build` with default local settings
- **THEN** the static page is available on port 4321 and, once the API is ready, the browser reads lockers directly from port 8000 using the existing CORS policy
- **AND** no separate npm process is required to serve the page

#### Scenario: Build and serve without API availability
- **WHEN** the frontend image is built and started while the API is unavailable
- **THEN** image creation and static page delivery succeed independently, and API failures are handled by the existing browser error state

#### Scenario: Configure another browser-visible API
- **WHEN** the operator supplies a different `PUBLIC_API_BASE_URL` and rebuilds the frontend image
- **THEN** its browser assets use that URL directly, without relying on Docker-internal hostnames or runtime substitution

#### Scenario: Isolate CI ports
- **WHEN** Compose merges the CI override
- **THEN** the frontend has no published host port and the backend-only smoke remains independently runnable

### Requirement: Configure the public API address at build time

The frontend SHALL use `PUBLIC_API_BASE_URL` embedded at build time for direct browser requests to the API. The value SHALL contain no credentials or secrets. Changing it SHALL require rebuilding the static assets. Missing or malformed configuration, and an HTTP API address on an HTTPS page, SHALL produce a visible configuration error without requesting lockers or silently falling back to localhost.

#### Scenario: Hosted HTTPS frontend
- **WHEN** a static HTTPS page is built with an accessible HTTPS API URL and its origin is allowed by that API
- **THEN** the browser reads the configured API's `GET /lockers` directly without a frontend intermediary

#### Scenario: Missing or insecure configuration
- **WHEN** the configured URL is absent, invalid, or uses HTTP while the page uses HTTPS
- **THEN** the UI explains that the connection is not correctly configured, shows no fabricated results and performs no fallback request

#### Scenario: Change API after a build
- **WHEN** an operator changes the build environment's API URL but serves the previous `dist` unchanged
- **THEN** the page still uses its embedded URL until a new build is generated and published

### Requirement: Allow browser reads from explicit origins

The API SHALL configure CORS from `CORS_ALLOWED_ORIGINS`, a comma-separated list of exact HTTP(S) origins, defaulting to none when absent or empty. It SHALL expose responses only to listed origins and grant preflight permission for GET, without credentials or wildcards. Invalid entries SHALL fail configuration clearly. CORS SHALL preserve endpoint behavior and requests without an Origin header; it is not authorization.

#### Scenario: Allowed origin and preflight
- **WHEN** a listed frontend origin sends a locker GET or a valid GET preflight
- **THEN** the API supplies that exact allowed origin and the browser can read the response without credentials

#### Scenario: Unlisted origin or unsupported preflight
- **WHEN** an unlisted origin requests lockers or an origin requests preflight permission for a write method
- **THEN** the API does not grant the requested browser access; an unsupported preflight fails
- **AND** the policy does not imply that CORS prevents direct HTTP clients from calling existing endpoints

#### Scenario: Requests without Origin
- **WHEN** a client calls existing API routes without an Origin header
- **THEN** route statuses and representations remain unchanged

#### Scenario: Invalid configuration
- **WHEN** configuration contains a wildcard or a value that is not an exact HTTP(S) origin
- **THEN** startup reports a configuration error instead of broadening the allowlist

### Requirement: Document static Cloudflare Pages publication

The repository SHALL document preparation for Cloudflare Pages static hosting using root `frontend`, build command `npm run build`, output `dist`, Node build version and locked dependency installation. It SHALL explain the build-time API URL and exact backend CORS origins, including explicitly configured preview origins. The API SHALL be documented as a separately hosted HTTPS prerequisite; no backend hosting or actual publication is implied.

#### Scenario: Prepare publication with project-specific values
- **WHEN** an operator follows the Pages instructions
- **THEN** placeholders identify the public HTTPS API and the exact Pages or custom-domain origin to configure
- **AND** the instructions describe static hosting without frontend server functions and require a rebuild when the API URL changes
