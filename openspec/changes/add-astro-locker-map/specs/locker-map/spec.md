# Locker Map Spec Delta

## Purpose

Let people locate available lockers across Spain and compare shipping quotations toward a selected locker through an accessible static frontend backed by existing APIs.

## ADDED Requirements

### Requirement: Fill the viewport with the map

The map SHALL fill the visible viewport without surrounding page margins, header or footer reducing its area. A compact parcel-entry panel SHALL appear over its upper-left area. Other controls and panels SHALL overlay the map without resizing it. At desktop and 375-pixel mobile widths, inputs, map controls and attribution SHALL remain accessible without page-level horizontal overflow or overlapping controls.

#### Scenario: Full-screen initial view and resizing
- **WHEN** the page opens on desktop or a 375-pixel-wide mobile viewport, or the viewport changes size
- **THEN** the map fills that viewport, the parcel panel remains in its upper-left area and the zoom controls and attribution remain accessible

### Requirement: Switch accessibly between quotation and tracking

The menu heading SHALL be replaced by "Cotizar envío" and "Localizar paquete" tabs, initially selecting quotation. Only the active tab content SHALL be visible and interactive. Switching SHALL preserve local inputs and selected quotation destination, cancel pending geographic/quotation/tracking work and ignore late responses. Tabs SHALL expose selection and panel relationships and support keyboard navigation without navigating the map.

#### Scenario: Switch while work is pending
- **WHEN** a visitor switches modes during suggestions, quotation polling or a tracking request
- **THEN** inactive content becomes hidden and unfocusable, its pending work cannot reopen it, and returning retains input values without automatic submission
- **AND** browser cancellation is not presented as cancellation of server-side quotation processing

### Requirement: Keep the quotation menu compact

The quotation tab SHALL contain pickup/delivery search, parcel fields and live available/mapped counts. It SHALL retain the removal of the availability-success sentence, "Ver lockers", "Actualizar", last-read time, "Ver España" and informational note. Loading, empty, error/retry and tile warnings SHALL appear only when applicable. Tracking SHALL not depend on a successful available-locker load.

#### Scenario: Compact and independent modes
- **WHEN** lockers load or fail and the visitor switches to tracking
- **THEN** quotation counts remain truthful, retired controls stay absent and UUID lookup can operate independently of locker availability

### Requirement: Enter parcel measurements locally

The quotation tab SHALL contain visibly labelled length, width and height fields in centimetres and weight in kilograms. Fields SHALL start empty, permit empty values and accept positive decimal numbers. Nonpositive values SHALL be invalid. Editing SHALL remain local to the current page without submitting data, persisting values, filtering lockers or requesting quotations. It SHALL NOT move or zoom the map.

#### Scenario: Edit dimensions and weight
- **WHEN** a user enters 25.5, 15, 10 and 2.5 into the four labelled fields and navigates between them by keyboard
- **THEN** the values remain editable, the map view and available lockers stay unchanged, and no request is triggered by those edits
- **AND** clearing a field is allowed, while zero or a negative value is identified as invalid without making a request

#### Scenario: Interact with the overlay
- **WHEN** a user clicks, types or drags within the dimension or weight controls, or scrolls the panel
- **THEN** those interactions operate on the panel without being interpreted as map navigation
- **AND** opening or closing the quotation panel preserves entered parcel values

### Requirement: Search pickup and delivery areas independently

"Dirección de recogida" and "Dirección de entrega" SHALL appear above parcel dimensions. Each SHALL independently search Spanish locations after 350 ms without edits and at least three trimmed characters, retaining five-digit postal text. Each SHALL offer at most five safely rendered candidates requiring selection. Typing or receiving suggestions SHALL NOT move the map, select a locker or request a quotation.

#### Scenario: Independent debounced suggestions
- **WHEN** the visitor types in either field and pauses for 350 ms
- **THEN** only that field's latest eligible query is requested, and the other field's value/state is not replaced
- **AND** fewer than three characters sends no request; country ES, leading zeroes, timeout and stale-response handling are preserved

#### Scenario: Explore delivery lockers
- **WHEN** a delivery suggestion is selected
- **THEN** its label fills that field and the map reveals the area for nearby lockers, closing suggestions without another request
- **AND** the visitor must still choose a locker explicitly; its selection and destination postal code are not changed or inferred from the search

### Requirement: Populate origin postal code from structured pickup data

Selecting a pickup suggestion SHALL fill origin postal code only from a valid structured five-digit Spanish postcode. Missing or invalid postcode SHALL leave origin entry available manually, without parsing a label or coordinates. Editing the selected pickup text SHALL clear its previously derived postcode and invalidate the previous quotation. Selecting another pickup SHALL replace the old postcode or clear it if unavailable.

#### Scenario: Structured code and manual fallback
- **WHEN** the pickup suggestion contains postcode "01001", then another selected suggestion has no usable postcode
- **THEN** origin first becomes "01001", then requires manual postal entry instead of retaining the old derived value
- **AND** selecting or editing pickup does not assign a destination locker or submit a quotation

#### Scenario: Edit a selected pickup
- **WHEN** a visitor edits pickup text after its structured postcode populated the origin field
- **THEN** that derived code and obsolete quotation results are invalidated without another quotation POST

### Requirement: Animate and dismiss geographic suggestions accessibly

Suggestions SHALL open and close with a brief animation below the search field and respect reduced-motion preferences. Their controls SHALL support keyboard selection and visible focus. Escape SHALL close suggestions and return focus to the field; leaving the search controls SHALL close without triggering a search. Closed suggestions SHALL immediately become noninteractive and unfocusable. Superseded requests or animations SHALL NOT reopen a dismissed list or hide a newer one.

#### Scenario: Select or dismiss with keyboard and pointer
- **WHEN** a user selects a suggestion by click or keyboard, presses Escape, or moves focus outside the search controls
- **THEN** suggestions close without another request, selection remains possible before focus leaves, and hidden controls cannot receive focus
- **AND** rapid closing/reopening stays consistent, scroll does not navigate the map, and reduced-motion settings suppress the movement

### Requirement: Isolate geographic-search failures and stale responses

Geographic search SHALL have independent loading, no-results and error states, with a five-second timeout and explicit retry. It SHALL accept only valid Spanish point results and render provider text safely. A superseded or cancelled response SHALL NOT update results or move the map. Search SHALL NOT mutate lockers, infer missing locker coordinates or call locker APIs, and a search failure SHALL leave the existing map and locker data usable.

#### Scenario: No result or unavailable provider
- **WHEN** geographic search returns no valid Spanish result, fails, times out or yields malformed data
- **THEN** its own status communicates no results or failure and permits explicit retry or a new debounced query without replacing locker results or their status

#### Scenario: A later query supersedes an earlier request
- **WHEN** a user edits or replaces a pending query and its earlier response subsequently arrives
- **THEN** the earlier response is ignored, and only the latest eligible query can update suggestions; the map moves only after selection

### Requirement: Select a locker as the shipping destination

In quotation mode, selecting a locker marker SHALL open "Enviar a este locker". The panel SHALL show its destination label/address and a compact selector of available lockers, including coincident or unmapped ones. A keyboard-accessible "Elegir destino y cotizar" link SHALL activate quotation mode and open the selector. Closing or Escape SHALL restore focus to the opening control when possible, without resizing the map.

#### Scenario: Select individually without a technical catalogue
- **WHEN** a visitor in quotation mode selects a marker or uses the destination selector, including lockers sharing a position or lacking coordinates
- **THEN** the chosen locker becomes the destination and its recorded position is revealed when usable
- **AND** the panel contains no technical catalogue, UUID/cell detail sheet or inherited general-list opening action

#### Scenario: Keyboard entry and return
- **WHEN** a keyboard user follows the destination link, selects a locker and closes the panel
- **THEN** the selector and quote controls are usable without map pointer interaction and closing restores focus to the link

### Requirement: Read live lockers in the browser

The browser SHALL load lockers directly from the configured API using GET without credentials or custom request headers. Each load SHALL bypass the browser response cache and cancel after five seconds without completion. Response validation, availability filtering and map interaction SHALL execute client-side. Missing or invalid essential data SHALL produce a visible data error, while unusable coordinates alone SHALL retain the locker without a map position.

#### Scenario: Fresh client-side observation
- **WHEN** a visitor opens the static page or retries a failed locker load
- **THEN** the browser performs a new API read and computes availability from that response rather than build-time data or a stored availability cache

#### Scenario: Timeout and unreadable response
- **WHEN** the API does not complete within five seconds, CORS prevents reading it, or essential fields are malformed
- **THEN** the browser displays an error with retry and no fabricated capacity or proxy HTTP status
- **AND** invalid coordinates in an otherwise usable locker response only prevent positioning that locker

### Requirement: Derive general availability from current locker data

The frontend SHALL consider a locker available exactly when active is true and at least one returned compartment is enabled and unoccupied. Only available lockers SHALL appear in the quotation marker layer/destination selector; tracking uses an independent layer. Counts SHALL reflect the current successful load. Availability and shipping quotations SHALL NOT claim parcel fit, reserve capacity or create a shipment.

#### Scenario: Mixed capacity and operational states
- **WHEN** data includes an active locker with enabled free cells, disabled or occupied cells, an inactive locker, a full locker and one without enabled cells
- **THEN** only the active locker with an enabled free cell is offered as a destination
- **AND** editing parcel dimensions does not filter lockers or create a quotation

#### Scenario: Collection replaced on a new successful load
- **WHEN** a fresh locker load no longer includes a previously selected available locker
- **THEN** that selection and its active quotation display are cleared rather than being presented as current

### Requirement: Display real coordinates across Spain

The map SHALL initially frame mainland Spain closely. Mainland, Balearic, Canary Island, Ceuta and Melilla lockers SHALL remain reachable through navigation and destination selection without a "Ver España" control. Valid stored positions SHALL remain unchanged. Wheel input over the map SHALL zoom in/out, while overlay interactions SHALL NOT navigate it. Data loads and empty results SHALL preserve the current view.

#### Scenario: Island and autonomous-city destinations remain reachable
- **WHEN** available destinations have coordinates in Madrid, Palma, Santa Cruz de Tenerife, Ceuta and Melilla and the user selects each
- **THEN** each stored position is revealed in the visible map area with that locker selected as destination

#### Scenario: Initial view and wheel navigation
- **WHEN** the page opens and the user scrolls the wheel over the map in either direction
- **THEN** the initial view focuses on mainland Spain, wheel-up zooms in and wheel-down zooms out
- **AND** scrolling search, parcel or quotation controls does not change map zoom

#### Scenario: Empty loads preserve navigation
- **WHEN** a locker load finishes without positioned lockers after initial framing or geographic search
- **THEN** the current view remains unchanged

#### Scenario: Coordinates are independent of address
- **WHEN** a locker has valid coordinates but no address
- **THEN** it keeps its stored map position without receiving an invented address or postal code

### Requirement: Retain available lockers without usable coordinates

Available lockers with missing or invalid coordinates SHALL remain selectable as destinations, with an indication that their map position is unavailable. They SHALL NOT receive invented positions or be geocoded. Counts SHALL distinguish all available lockers from mapped ones.

#### Scenario: No available locker can be mapped
- **WHEN** every available locker lacks usable coordinates
- **THEN** the available count and destination selector remain populated, the mapped count is zero and the map retains its view
- **AND** users can select a destination through the keyboard entry without a fabricated marker

### Requirement: Identify each available destination safely

Locker identity SHALL remain independent of its label and coordinates. Public labels SHALL use alias, recorded address or a neutral numbered fallback, with duplicate labels distinguishable in the selector. The panel SHALL show the recorded address or its absence without a technical UUID/cell sheet. External text SHALL be rendered literally, never as executable markup.

#### Scenario: Coincident or identically labelled lockers
- **WHEN** two lockers share a position or label
- **THEN** the compact selector permits choosing each distinct destination without changing its stored position

#### Scenario: Missing or untrusted labels
- **WHEN** alias/address is absent or contains markup-like text
- **THEN** a usable fallback or literal label is shown without executing markup or inventing an address

### Requirement: Distinguish loading, empty results and data failure

Locker loading, empty and error states SHALL be communicated in Spanish. Empty SHALL follow only a successful load without available lockers. Network, timeout, HTTP or data failures SHALL offer retry and SHALL NOT present obsolete data as current availability. Success SHALL update counts/map and hide loading/error status without the former repeated success sentence or timestamp.

#### Scenario: Loading, empty and success
- **WHEN** a pending locker load completes
- **THEN** loading disappears and either a no-available-lockers message or populated map/counts is shown

#### Scenario: Failure and recovery
- **WHEN** a locker read fails and the user retries after recovery
- **THEN** an accessible error/retry outside the closed quotation panel leads to a fresh read and usable data without entering parcel measurements

### Requirement: Preserve access when external cartography fails

The map SHALL retain provider attribution. Tile failures SHALL show a cartography warning without converting successful locker data into a backend error or empty result. The destination selector, counts and quotation controls SHALL remain usable independently of tiles.

#### Scenario: Tiles fail while data succeeds
- **WHEN** external tiles fail but locker data loads
- **THEN** the warning and attribution remain visible and every available destination is selectable through the panel

### Requirement: Support Spanish mobile and keyboard use

The page SHALL use Spanish content, preserve a usable map and readable panels at desktop and mobile sizes, and expose labelled controls, visible focus and announced loading/error status. Destination selection and quotation controls SHALL be keyboard operable without requiring pointer interaction with the map. Panels SHALL scroll internally without page-level horizontal overflow.

#### Scenario: Small viewport and keyboard operation
- **WHEN** the page is used at 375×480 CSS pixels or with keyboard alone
- **THEN** search, parcel fields, destination selection, quotation controls/results and map attribution remain accessible without covering the selected position or losing focus

### Requirement: Use explicit postal data for a shipment toward the locker

The selected locker SHALL be the destination. Origin postal code SHALL be required. A valid structured destination postal code SHALL be used as recorded; if missing or invalid, the visitor SHALL enter it explicitly with a missing-code indication. Both countries SHALL be ES and postal codes SHALL remain five-digit ASCII strings. Search labels or coordinates SHALL NOT supply inferred postal codes, and manual entry SHALL NOT modify locker data.

#### Scenario: Recorded destination postal code
- **WHEN** a selected locker has structured postal code "01001" and the visitor enters origin "28001"
- **THEN** comparison uses ES origin "28001" and ES destination "01001", preserving leading zeroes and keeping the recorded destination code read-only

#### Scenario: Missing code and changed destination
- **WHEN** a locker has no valid postal code, or the visitor changes from one such locker to another
- **THEN** destination code must be entered for that locker before submission, without carrying a previous locker's manual code
- **AND** origin and parcel measurements are preserved while obsolete quotation results are cleared

### Requirement: Submit only explicitly validated shipping input

"Comparar envíos" SHALL reuse the existing parcel fields and create one quotation only after valid destination, postal and parcel input. Dimensions SHALL convert exactly from cm to integer mm in 1..2000, and weight from kg to integer grams in 1..30000. Invalid or unrepresentable fractions SHALL show field errors without submission. Editing, selecting a locker or searching SHALL NOT submit automatically; duplicate clicks during submission SHALL NOT create duplicate requests.

#### Scenario: Exact conversion and payload
- **WHEN** the visitor compares length 25.5 cm, width 15 cm, height 10 cm and weight 2.5 kg with valid postal input
- **THEN** one POST contains depth_mm 255, width_mm 150, height_mm 100 and weight_grams 2500, both ES countries and postal strings, with no locker_id or other extra fields

#### Scenario: Invalid input and uncertain submission
- **WHEN** required fields are empty, dimensions cannot represent integer mm, weight cannot represent integer grams, or limits are exceeded
- **THEN** the relevant field is identified and no POST is made
- **AND** a later POST failure, timeout or unreadable response is reported without automatic resubmission or invented provider failures

### Requirement: Observe asynchronous quotations with bounded waiting

After accepted creation, the browser SHALL read that quotation sequentially about once per second, with five-second HTTP timeouts and a thirty-second local waiting limit. PENDING/PROCESSING SHALL show waiting; COMPLETED/FAILED SHALL stop polling. A read failure or waiting limit SHALL permit manually continuing the same identifier without a new POST. Process failure SHALL be distinguished from provider outcomes.

#### Scenario: Pending work completes or fails
- **WHEN** an accepted quotation progresses through pending/processing to a terminal state
- **THEN** reads do not overlap and stop at the terminal state, showing its offers/provider outcomes or process error

#### Scenario: Long wait or interrupted read
- **WHEN** the local waiting limit is reached or a GET fails while the request identifier is known
- **THEN** the UI stops waiting and offers to continue reading the same quotation rather than creating another one
- **AND** it does not claim the server-side work was cancelled

### Requirement: Invalidate obsolete quotation interaction

Closing the panel, switching tabs, changing destination/postal/parcel input or leaving the page SHALL stop local polling and invalidate pending responses. Obsolete results SHALL NOT be shown for new input. Cancellation SHALL affect browser waiting only, without claiming to cancel persisted worker work or an actual shipment. Continuing a known quotation SHALL be allowed only for its unchanged input snapshot.

#### Scenario: Edit or close during creation or polling
- **WHEN** an older POST/GET completes after the visitor edits input, changes destination or closes the panel
- **THEN** it cannot reopen the panel or replace current state/results, and it is never repeated automatically

### Requirement: Present provider offers honestly

The panel SHALL show every returned provider/service, EUR price and transit-day range from the quotation, without calculating tariffs or inventing brands. QUOTED, NOT_COVERED and provider FAILED SHALL remain distinguishable, including partial success. Current simulated providers and demonstration prices SHALL be visibly identified. Quotes SHALL NOT imply real-provider coverage, cell fit, reservation, payment or shipment creation.

#### Scenario: Partial and total provider failures
- **WHEN** a completed quotation includes offers, no coverage or provider error/timeout outcomes
- **THEN** each provider remains visible with its own outcome and any successful services retain their prices and transit-day ranges
- **AND** an all-failed provider set is shown faithfully as a completed comparison rather than a fabricated process failure
