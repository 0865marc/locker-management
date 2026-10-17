# Locker Map Spec Delta

## Purpose

Let people locate available lockers across Spain and inspect their current free capacity through an accessible, read-only map and list backed by real locker data.

## ADDED Requirements

### Requirement: Fill the viewport with the map

The map SHALL fill the visible viewport without surrounding page margins, header or footer reducing its area. A compact parcel-entry panel SHALL appear over its upper-left area. Other controls and panels SHALL overlay the map without resizing it. At desktop and 375-pixel mobile widths, inputs, map controls and attribution SHALL remain accessible without page-level horizontal overflow or overlapping controls.

#### Scenario: Full-screen initial view and resizing
- **WHEN** the page opens on desktop or a 375-pixel-wide mobile viewport, or the viewport changes size
- **THEN** the map fills that viewport, the parcel panel remains in its upper-left area and the zoom controls and attribution remain accessible

### Requirement: Enter parcel measurements locally

The parcel panel SHALL be titled "Tu paquete" and contain visibly labelled length, width and height fields in centimetres and weight in kilograms. Fields SHALL start empty, permit empty values and accept positive decimal numbers. Nonpositive values SHALL be invalid. Editing SHALL remain local to the current page without submitting data, persisting values, filtering lockers or requesting quotations. It SHALL NOT move or zoom the map.

#### Scenario: Edit dimensions and weight
- **WHEN** a user enters 25.5, 15, 10 and 2.5 into the four labelled fields and navigates between them by keyboard
- **THEN** the values remain editable, the map view and available lockers stay unchanged, and no request is triggered by those edits
- **AND** clearing a field is allowed, while zero or a negative value is identified as invalid without making a request

#### Scenario: Interact with the overlay
- **WHEN** a user clicks, types, drags or scrolls inside the parcel panel
- **THEN** those interactions operate on the panel without being interpreted as map navigation
- **AND** toggling the locker list or manually refreshing availability preserves entered values

### Requirement: Keep locker results in a separate collapsible overlay

The locker list SHALL initially be collapsed and open through a keyboard-accessible "Ver lockers" control outside the parcel form. Its overlay SHALL retain all list and detail functionality with internal scrolling and an accessible close control. Selecting a map marker SHALL reveal that locker's details. Loading, empty, error, retry and refresh controls SHALL remain accessible while the list is closed.

#### Scenario: Inspect lockers without permanently reducing the map
- **WHEN** a user opens the list, selects an unmapped locker or one sharing coordinates, then closes it
- **THEN** the correct individual detail is accessible, closing restores focus to the list-opening control when appropriate, and the map retains its full viewport dimensions

#### Scenario: Recover from failure with the list closed
- **WHEN** the initial locker read fails while the list is collapsed
- **THEN** the page displays the failure and an accessible retry action outside the hidden list
- **AND** the existing read-only recovery flow remains usable without entering parcel data

### Requirement: Read live lockers in the browser

The browser SHALL load lockers directly from the configured API using GET without credentials or custom request headers. Each load SHALL bypass the browser response cache and cancel after five seconds without completion. Response validation, availability filtering and map interaction SHALL execute client-side. Missing or invalid essential data SHALL produce a visible data error, while unusable coordinates alone SHALL retain the locker without a map position.

#### Scenario: Fresh client-side observation
- **WHEN** a visitor opens the static page or requests a manual update
- **THEN** the browser performs a new API read and computes availability from that response rather than build-time data or a stored availability cache

#### Scenario: Timeout and unreadable response
- **WHEN** the API does not complete within five seconds, CORS prevents reading it, or essential fields are malformed
- **THEN** the browser displays an error with retry and no fabricated capacity or proxy HTTP status
- **AND** invalid coordinates in an otherwise usable locker response only prevent positioning that locker

### Requirement: Derive general availability from current locker data

The frontend SHALL read the complete locker list and consider a locker available exactly when active is true and at least one returned compartment is enabled and unoccupied. It SHALL display only available lockers in its results and count their enabled, unoccupied compartments. It SHALL explain in Spanish that this is information from the last successful load, without parcel-size matching or reservation.

#### Scenario: Mixed capacity and operational states
- **WHEN** the response contains an active locker with two enabled free cells, one disabled free cell and one occupied cell, an inactive locker with free cells, a full locker and a locker with no enabled cells
- **THEN** only the first locker is listed as available, with a free-cell count of two
- **AND** the UI makes no parcel-fit or reservation guarantee and performs no write request

#### Scenario: Capacity changes between loads
- **WHEN** an initially available locker has no enabled free cells in the next successful manual update
- **THEN** that locker disappears from both available results and map, and any selection of it is cleared

### Requirement: Display real coordinates across Spain

The map SHALL initially frame mainland Spain, the Balearic Islands, the Canary Islands, Ceuta and Melilla, including when results are empty. Available lockers with valid finite WGS84 coordinates SHALL be represented at their stored positions without inferring or altering geography. The user SHALL be able to pan, zoom and return to the Spain view.

#### Scenario: Island and autonomous-city lockers remain reachable
- **WHEN** available lockers have coordinates in Madrid, Palma, Santa Cruz de Tenerife, Ceuta and Melilla
- **THEN** all five positions are included in the Spain view and remain individually selectable from the results

#### Scenario: Coordinates are independent of address
- **WHEN** an available locker has valid coordinates but a null address
- **THEN** it has a map position using those coordinates and does not receive an invented address
- **AND** valid stored positions are not silently discarded based on an address or mainland-only boundary

### Requirement: Retain available lockers without usable coordinates

Available lockers with null, incomplete, nonnumeric, nonfinite or out-of-range coordinates SHALL remain in the results with a Spanish indication that their map position is unavailable. They SHALL NOT produce a marker, be geocoded from their address or be placed at an invented fallback location. Result counts SHALL distinguish all available lockers from those positioned on the map.

#### Scenario: Available lockers cannot be mapped
- **WHEN** all available lockers lack usable coordinates
- **THEN** the list and available count remain populated, the map stays on Spain without markers, and the UI explains that these lockers have no usable map coordinates
- **AND** this state is distinct from having no available lockers

### Requirement: Identify and inspect each available locker

The list and map SHALL allow inspecting each available locker by its UUID, using its alias, address or UUID as its display label in that order. Details SHALL show the recorded address when present and the free-cell count, with explicit missing-address text when absent. Selecting a positioned locker from the list SHALL reveal its map location. Values from the API SHALL be rendered as text, never executable markup.

#### Scenario: Multiple lockers share one position
- **WHEN** two available lockers have the same coordinates or alias
- **THEN** each remains a separate identifiable list result and can be selected to inspect its own UUID and free-cell count
- **AND** overlapping map markers do not prevent accessing either locker through the list

#### Scenario: Nullable labels and untrusted text
- **WHEN** one locker lacks an alias, another lacks both alias and address, and another has markup-like text in its alias or address
- **THEN** the first uses its recorded address, the second uses its UUID, and all supplied text is displayed literally without executing markup

### Requirement: Distinguish loading, empty results and data failure

The frontend SHALL show Spanish loading, success, empty and error states. Empty results SHALL appear only after a successful load with no available lockers. Network failures, timeouts, non-success responses and malformed data SHALL show an error with retry. Manual refresh and retry SHALL perform a new read and replace the displayed results after success; failed refreshes SHALL NOT present old results as current availability.

#### Scenario: Initial load and empty response
- **WHEN** the data request is pending and then succeeds with an empty list or only unavailable lockers
- **THEN** a loading indicator is replaced by a no-available-lockers message, without sample lockers or an error state

#### Scenario: Failure and recovery
- **WHEN** a request fails, times out or returns malformed data and the user retries after the service recovers
- **THEN** a distinguishable error state offers retry and the subsequent success displays the returned available lockers without a page reload

#### Scenario: Refresh fails after prior success
- **WHEN** a manual refresh fails after lockers were displayed
- **THEN** the UI clears current availability results and markers, reports the failure and offers retry

### Requirement: Preserve access when external cartography fails

The map SHALL display attribution for its cartography provider. Tile-loading failures SHALL produce a Spanish cartography warning without converting successful locker data into a backend error or empty result. The list, details and result counts SHALL remain usable independently of tile availability.

#### Scenario: Tiles unavailable while locker data succeeds
- **WHEN** external map tiles fail but the locker request succeeds
- **THEN** the UI reports the map-background problem, retains provider attribution and allows inspecting every available locker in the list

### Requirement: Support Spanish mobile and keyboard use

The page SHALL use Spanish content and document language, retain a visible usable map and readable results at mobile and desktop widths, and expose labelled controls, visible keyboard focus and announced loading/error status. Every locker's details SHALL be accessible through keyboard-operable list controls without requiring pointer interaction with the map.

#### Scenario: Narrow viewport and keyboard navigation
- **WHEN** the page is viewed at 375 CSS pixels wide or operated using only the keyboard
- **THEN** map, list and details remain accessible without page-level horizontal overflow, and selecting a list result reveals its details with visible focus
