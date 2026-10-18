# Spec Delta

## MODIFIED Requirements

### Requirement: Fill the viewport with the map

The map SHALL fill the visible viewport without surrounding page margins, header or footer reducing its area. Controls and panels SHALL overlay it without resizing it. Above 760 pixels wide, the parcel-entry panel SHALL remain upper-left. At narrower widths, the menu SHALL start collapsed; its expanded footprint, including its toggle, SHALL occupy at most 60% of the visible height. Map controls and attribution SHALL remain accessible without page-level horizontal overflow or overlapping controls.

#### Scenario: Full-screen initial view and resizing
- **WHEN** the page opens on desktop or a 375-pixel-wide mobile viewport, or the viewport changes size
- **THEN** the map fills that viewport, desktop retains its upper-left panel, mobile starts with a compact menu control, and zoom controls and attribution remain accessible
- **AND** at 320×568, 375×480 and 667×375 the expanded menu scrolls internally within its height limit, leaving a usable map area below it
- **AND** resizing across the mobile boundary preserves values and never leaves keyboard focus in hidden content

#### Scenario: Denser mobile menu remains usable
- **WHEN** a visitor opens the menu at a width up to 760 pixels
- **THEN** moderately smaller non-editable text and reduced padding, gaps and margins make the menu more compact while preserving readable labels, visible focus and usable touch targets
- **AND** editable fields retain a 16-pixel font size to avoid focus-triggered zoom on iOS; desktop typography and spacing remain unchanged

### Requirement: Reserve the lateral panel for quotation results

The initially closed lateral panel SHALL contain only quotation status/reference, offers, simulation notice and close/continuation controls. Comparison from the main menu SHALL open it; marker inspection or role selection SHALL NOT. It SHALL contain no locker selector, postal/parcel input or compare button. Close/Escape SHALL return focus to the main compare control. Mobile layout SHALL preserve access with internal scrolling and SHALL show at most one expanded menu or quotation-results panel at a time.

#### Scenario: Results without a second form
- **WHEN** a valid comparison begins and later completes
- **THEN** the right-hand panel shows progress then provider outcomes, while all shipment input remains in the main menu
- **AND** at 375×480 the results use the mobile panel, the menu is collapsed, and results, popup controls and attribution remain accessible without horizontal page overflow
- **AND** collapsing the menu to display results does not stop the quotation request or its polling

#### Scenario: Return from mobile results
- **WHEN** the visitor closes mobile results with their close control or Escape, or explicitly opens the menu
- **THEN** results close using the existing local-wait cancellation rules, the menu becomes accessible, and unchanged completed results or a known resumable reference remain available through the existing reopen/continue controls
- **AND** Close/Escape reveals the compare control before returning focus; opening the menu never submits or automatically resumes a quotation

#### Scenario: Inspect a marker with mobile results open
- **WHEN** a visitor inspects a marker with pending or completed quotation results open at 375×480 or 667×375
- **THEN** the layout reserves enough space for the popup, its separated pin and at least one whole role-action button within its scrollable content; each role action can be fully revealed and activated by touch or keyboard
- **AND** results may temporarily occupy less height, but their title and close control remain accessible, the pin does not overlap them, and inspection preserves quotation data and ongoing polling
- **AND** closing the popup restores the normal results layout without restarting requests or losing offers

## ADDED Requirements

### Requirement: Collapse the mobile menu without losing work

At widths up to 760 pixels, a labelled Spanish button SHALL expose the menu's expanded state and allow opening it or returning to the map by touch or keyboard. Collapsed content SHALL be unfocusable. Collapsing SHALL preserve mode, entered values, selected lockers, tracking results and quotation state without submitting or leaving either mode. Loading and failure information SHALL remain discoverable without automatically expanding the menu.

#### Scenario: Open, edit and return to the map
- **WHEN** a mobile visitor opens the menu, enters parcel data or a tracking UUID, selects lockers, then collapses and reopens it
- **THEN** the current mode, inputs, selections and existing results remain intact, the collapse control stays reachable while scrolling, and the freed map accepts touch navigation
- **AND** toggling alone creates no locker, geographic, tracking or quotation request, and pending responses cannot reopen the menu or steal focus
- **AND** loading, empty/error/retry and tile-warning states remain accessible from the compact menu control

#### Scenario: Keyboard access and dismissal
- **WHEN** a keyboard visitor opens the menu with Enter or Space and closes it using its control or Escape
- **THEN** hidden fields are excluded from keyboard navigation, focus remains visible, and dismissal returns focus to the compact control
- **AND** Escape first dismisses an active suggestion list; only an otherwise unhandled Escape dismisses the menu
- **AND** the quotation skip link reveals quotation and focuses origin search or its X when selected

#### Scenario: Inspect, select and reveal positions
- **WHEN** a mobile visitor inspects a marker, explicitly chooses a shipment role, selects a geographic result or completes a positioned pair
- **THEN** marker inspection collapses the menu without changing modes or selections, and choosing a role reveals quotation before focusing its X
- **AND** inspected popup actions and their marker, the chosen geographic/tracking position, and deliberately framed route endpoints remain visible outside the active controls
- **AND** map framing uses the space below an expanded menu or above mobile results, with collapsed content consuming no map area; stored coordinates and existing manual-navigation behavior remain unchanged
