# Locker Map Spec Delta

## Purpose

Let people locate available lockers across Spain and compare shipping quotations between selected pickup and delivery lockers through an accessible static frontend backed by existing APIs.

## ADDED Requirements

### Requirement: Fill the viewport with the map

The map SHALL fill the visible viewport without surrounding page margins, header or footer reducing its area. A compact parcel-entry panel SHALL appear over its upper-left area. Other controls and panels SHALL overlay the map without resizing it. At desktop and 375-pixel mobile widths, inputs, map controls and attribution SHALL remain accessible without page-level horizontal overflow or overlapping controls.

#### Scenario: Full-screen initial view and resizing
- **WHEN** the page opens on desktop or a 375-pixel-wide mobile viewport, or the viewport changes size
- **THEN** the map fills that viewport, the parcel panel remains in its upper-left area and the zoom controls and attribution remain accessible

### Requirement: Switch accessibly between quotation and tracking

The menu SHALL retain accessible "Cotizar envío" and "Localizar paquete" tabs, initially selecting quotation. Only active content SHALL be visible and interactive. Switching SHALL preserve local inputs and both locker selections, cancel pending work and ignore late responses. The separate geographic search SHALL remain available above both tabs. Tabs SHALL support keyboard navigation without navigating the map.

#### Scenario: Switch while work is pending
- **WHEN** a visitor switches modes during suggestions, quotation polling or tracking
- **THEN** inactive content becomes hidden and unfocusable, pending work cannot reopen it, and inputs remain without automatic submission
- **AND** browser cancellation is not presented as cancellation of server-side processing

### Requirement: Keep the quotation menu compact

The quotation tab SHALL contain pickup/delivery locker selectors, their postal input, parcel fields, "Comparar envíos" and live counts. The availability-success sentence, "Ver lockers", "Actualizar", timestamp, "Ver España" and informational note SHALL remain absent. Loading, empty, error/retry and tile warnings SHALL appear only when applicable. Tracking SHALL not depend on a successful available-locker load.

#### Scenario: Compact and independent modes
- **WHEN** lockers load or fail and the visitor switches to tracking
- **THEN** counts remain truthful, retired controls stay absent and UUID lookup operates independently of locker availability
- **AND** the main quotation menu contains all input needed to compare without a lateral form

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

### Requirement: Search geography independently of locker selection

A separate search panel above the tabs SHALL find Spanish directions or postal codes after 350 ms without edits and at least three trimmed characters, preserving five-digit postal text. It SHALL offer at most five candidates requiring selection. Choosing one SHALL only fill that search, reveal its map position and close suggestions; it SHALL NOT change tabs, locker selections, postal input, tracking results or quotations.

#### Scenario: Debounced suggestions and geographic choice
- **WHEN** the visitor types an eligible query and selects a returned place
- **THEN** only the latest query is requested with country ES and preserved leading zeroes, and the selected place is revealed without another request
- **AND** typing or receiving candidates alone does not move the map; fewer than three characters sends no request
- **AND** even a result with a postcode cannot supply either locker's postal code

### Requirement: Select actual lockers for both shipment roles

Pickup and delivery selectors SHALL filter loaded available lockers locally by label, recorded address or postcode. Each role SHALL require explicit selection identified by UUID; free text SHALL NOT qualify. Editing a role's text SHALL clear its selection and postal input. Selecting one role SHALL preserve the other and parcel values. Every matching locker, including coincident or unmapped ones, SHALL remain keyboard reachable.

#### Scenario: Local candidates and independent roles
- **WHEN** a visitor searches by label, address or postcode and chooses a locker for each role
- **THEN** the chosen UUIDs identify pickup and delivery without Photon or additional API requests
- **AND** arbitrary geographic addresses can instead be explored through the separate map search, without being accepted as lockers

#### Scenario: Edit or replace a selected role
- **WHEN** the selected label is edited or a different locker is chosen for a role
- **THEN** that role's previous selection or manual postal supplement and obsolete quotations are cleared, while the other role and parcel values remain
- **AND** typing the old label back does not restore its UUID without selection; reopening suggestions or choosing the unchanged UUID does not erase a valid supplement

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

### Requirement: Choose a shipment role from a locker popup

Opening an available locker marker SHALL show a popup with its label, recorded address or absence, and "Seleccionar como locker de entrega"/"Seleccionar como locker de recogida". Opening SHALL NOT change tabs, select a role or open quotation results. Either action SHALL activate quotation, assign only its role and close the popup. The popup SHALL remain keyboard usable at mobile sizes without omitting its actions.

#### Scenario: Inspect then choose explicitly
- **WHEN** a visitor opens an available marker in either mode and then chooses a role
- **THEN** inspection alone preserves mode and selections, while the action switches to quotation if needed, assigns the UUID and focuses that role's selector
- **AND** no quotation request occurs and no technical catalogue or lateral input form opens

#### Scenario: Keyboard entry and popup dismissal
- **WHEN** a keyboard user follows the quotation skip link or closes a marker popup with Escape
- **THEN** the link activates quotation and focuses pickup selection, while popup dismissal restores marker focus when possible
- **AND** choosing lockers remains possible without pointer interaction, including coincident and unmapped lockers

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

The frontend SHALL consider a locker available exactly when active is true and at least one returned compartment is enabled and unoccupied. Both role selectors and the quotation marker layer SHALL use only available lockers; tracking SHALL remain independent. Counts SHALL reflect the current successful load. Selection and quotations SHALL NOT claim parcel fit, reserve capacity or create a shipment.

#### Scenario: Mixed capacity and operational states
- **WHEN** lockers include inactive, full, disabled-only and active free-capacity records
- **THEN** only active lockers with an enabled free cell are offered for either role
- **AND** editing parcel dimensions does not filter that collection or request quotations

#### Scenario: Collection replaced on a new successful load
- **WHEN** a fresh load no longer includes a selected available locker
- **THEN** its affected role and active quotation display are cleared instead of being presented as current

### Requirement: Display real coordinates across Spain

The map SHALL initially frame mainland Spain closely. Mainland, Balearic, Canary Island, Ceuta and Melilla lockers SHALL remain reachable through navigation and either role selector without a "Ver España" control. Valid stored positions SHALL remain unchanged. Wheel input over the map SHALL zoom in/out, while overlay interactions SHALL NOT navigate it. Data loads and empty results SHALL preserve the current view.

#### Scenario: Island and autonomous-city destinations remain reachable
- **WHEN** available destinations have coordinates in Madrid, Palma, Santa Cruz de Tenerife, Ceuta and Melilla and the user selects each
- **THEN** each stored position is revealed in the visible map area with that locker selected for the chosen role

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

Available lockers with missing or invalid coordinates SHALL remain selectable for either role, with an indication that their map position is unavailable. They SHALL NOT receive invented positions or be geocoded. Counts SHALL distinguish all available lockers from mapped ones.

#### Scenario: No available locker can be mapped
- **WHEN** every available locker lacks usable coordinates
- **THEN** the available count and both role selectors remain populated, the mapped count is zero and the map retains its view
- **AND** users can select either role through keyboard entry without a fabricated marker

### Requirement: Identify each available locker safely

Locker identity SHALL remain independent of its label and coordinates. Public labels SHALL use alias, recorded address or a neutral numbered fallback, with duplicate labels distinguishable in the selector. Selections and popups SHALL show the recorded address or its absence without a technical UUID/cell sheet. External text SHALL be rendered literally, never as executable markup.

#### Scenario: Coincident or identically labelled lockers
- **WHEN** two lockers share a position or label
- **THEN** both role selectors permit choosing each distinct locker without changing its stored position

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

The map SHALL retain provider attribution. Tile failures SHALL show a cartography warning without converting successful locker data into a backend error or empty result. Both role selectors, counts and quotation controls SHALL remain usable independently of tiles.

#### Scenario: Tiles fail while data succeeds
- **WHEN** external tiles fail but locker data loads
- **THEN** the warning and attribution remain visible and every available locker is selectable for either role through the menu

### Requirement: Support Spanish mobile and keyboard use

The page SHALL use Spanish content, preserve a usable map and readable panels at desktop and mobile sizes, and expose labelled controls, visible focus and announced loading/error status. Both role selectors, popup actions and quotation controls SHALL be keyboard operable without requiring pointer interaction with the map. Panels SHALL scroll internally without page-level horizontal overflow.

#### Scenario: Small viewport and keyboard operation
- **WHEN** the page is used at 375×480 CSS pixels or with keyboard alone
- **THEN** search, parcel fields, both role selectors, popup actions and quotation controls/results and map attribution remain accessible without covering the selected position or losing focus

### Requirement: Use explicit postal data for each selected locker

Pickup SHALL supply origin and delivery SHALL supply destination. Each valid structured Spanish locker postcode SHALL remain read-only; otherwise the visitor SHALL enter a supplement explicitly for that role and UUID with a missing-code indication. Both countries SHALL be ES and postcodes five-digit ASCII strings. Labels, coordinates and geographic search SHALL NOT supply inferred codes; manual input SHALL NOT modify locker data.

#### Scenario: Recorded codes and leading zeroes
- **WHEN** selected pickup and delivery lockers contain "01001" and "28001"
- **THEN** comparison uses those exact origin/destination strings with countries ES and read-only registered codes

#### Scenario: Missing codes and role replacement
- **WHEN** either selected locker lacks a valid postcode or is replaced by another such locker
- **THEN** that role requires explicit supplemental postal input before comparison without carrying a previous locker's manual code
- **AND** the other role and parcel measurements remain; no address is invented or saved

### Requirement: Submit only explicitly validated shipping input

"Comparar envíos" SHALL be in the main menu and enabled only with both selected locker UUIDs, valid postal/parcel input and no request or waiting in progress. Submit SHALL revalidate. Dimensions SHALL convert exactly from cm to integer mm in 1..2000 and weight from kg to integer grams in 1..30000. Invalid input SHALL identify the field without HTTP. Editing, selection and search SHALL NOT submit; duplicate clicks SHALL NOT duplicate requests.

#### Scenario: Exact conversion and payload
- **WHEN** the visitor compares two selected lockers with valid codes, 25.5/15/10 cm and 2.5 kg
- **THEN** one POST contains depth_mm 255, width_mm 150, height_mm 100, weight_grams 2500, countries ES and postal strings
- **AND** neither locker UUID nor address is added to the existing API payload

#### Scenario: Incomplete or invalid input
- **WHEN** a role is only free text, a required value is missing, fractions are unrepresentable or limits are exceeded
- **THEN** comparison stays disabled and attempted submission makes no POST, with relevant field feedback
- **AND** a failed, timed-out or unreadable later POST is reported without automatic resubmission

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

Closing results, switching tabs or leaving SHALL stop local waiting and reject late responses. Changing either locker UUID, postal or parcel input SHALL also invalidate results and the resumable reference, even when the postal payload is unchanged. Known quotations SHALL resume only explicitly for their unchanged snapshot. Browser cancellation SHALL NOT claim to cancel worker processing. Geographic search alone SHALL NOT invalidate a quotation.

#### Scenario: Changed identity with unchanged postal payload
- **WHEN** a different locker with the same postcode replaces either role while a POST or GET is pending
- **THEN** the earlier reference/results are invalidated and a late response cannot reopen or replace current content

#### Scenario: Close and return without changing input
- **WHEN** the visitor closes results or leaves quotation mode with a known nonterminal reference, then returns
- **THEN** a read-only continuation remains accessible for that unchanged snapshot without automatically polling or issuing another POST
- **AND** changing input removes that continuation

### Requirement: Reserve the lateral panel for quotation results

The initially closed lateral panel SHALL contain only quotation status/reference, offers, simulation notice and close/continuation controls. Comparison from the main menu SHALL open it; marker inspection or role selection SHALL NOT. It SHALL contain no locker selector, postal/parcel input or compare button. Close/Escape SHALL return focus to the main compare control. Mobile layout SHALL preserve access with internal scrolling.

#### Scenario: Results without a second form
- **WHEN** a valid comparison begins and later completes
- **THEN** the right-hand panel shows progress then provider outcomes, while all shipment input remains in the main menu
- **AND** at 375×480 the results, menu, popup controls and attribution remain accessible without horizontal page overflow

### Requirement: Present provider offers honestly

The panel SHALL show every returned provider/service, EUR price and transit-day range from the quotation, without calculating tariffs or inventing brands. QUOTED, NOT_COVERED and provider FAILED SHALL remain distinguishable, including partial success. Current simulated providers and demonstration prices SHALL be visibly identified. Quotes SHALL NOT imply real-provider coverage, cell fit, reservation, payment or shipment creation.

#### Scenario: Partial and total provider failures
- **WHEN** a completed quotation includes offers, no coverage or provider error/timeout outcomes
- **THEN** each provider remains visible with its own outcome and any successful services retain their prices and transit-day ranges
- **AND** an all-failed provider set is shown faithfully as a completed comparison rather than a fabricated process failure
