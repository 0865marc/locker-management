# Spec Delta

## Purpose

Require revisions targeting main to contain only archived OpenSpec changes, with a reproducible diagnostic and explicit preservation of completed specifications and history.

## ADDED Requirements

### Requirement: Report an independent OpenSpec closure check

GitHub Actions SHALL report a stable `OpenSpec closure` check for pull requests targeting main and pushes to main, regardless of changed paths. It SHALL propagate verification failures and run with bounded execution and read-only repository permissions. The existing five backend checks SHALL retain their names and behavior.

#### Scenario: Verify all changes targeting main
- **WHEN** a pull request to main is opened or updated, or a commit is pushed to main, including a documentation-only change
- **THEN** the closure check runs independently of the five backend checks and reports its own outcome

### Requirement: Reject every active change directory

The closure check SHALL fail when any immediate child directory of `openspec/changes`, other than `archive`, exists. Hidden directories and directory symlinks SHALL count as active changes. The result SHALL not depend on task completion or artifact validity. Failure SHALL list every active change and direct contributors to complete, validate, synchronize and archive changes locally before merging.

#### Scenario: Incomplete or unrecognized work is active
- **WHEN** one or more active directories contain incomplete tasks, only a proposal, or no recognized OpenSpec artifacts
- **THEN** verification fails and identifies every active directory without modifying it

#### Scenario: Completed work still requires archiving
- **WHEN** a change has all tasks checked but its directory remains directly under `openspec/changes`
- **THEN** verification fails and identifies that change as requiring closure

#### Scenario: Hidden work is not omitted
- **WHEN** a hidden directory or a symlink to a directory exists directly under `openspec/changes` with a name other than `archive`
- **THEN** verification fails and includes it in the active-change diagnostic

### Requirement: Accept archived history without treating support files as changes

The closure check SHALL succeed when `openspec/changes` exists and contains no active directories. It SHALL ignore the contents of `archive` and ordinary auxiliary files directly under `openspec/changes`. A missing or unreadable changes directory SHALL produce a clear nonzero error rather than successful closure.

#### Scenario: History and support files are allowed
- **WHEN** the directory contains only archived change directories beneath `archive` and ordinary files such as `.gitkeep` or `README.md`
- **THEN** verification succeeds without reading archived task states

#### Scenario: Empty initialized directory is closed
- **WHEN** `openspec/changes` exists and is empty
- **THEN** verification succeeds even if no archive directory exists yet

#### Scenario: Missing inspection target fails clearly
- **WHEN** `openspec/changes` is absent or cannot be read
- **THEN** verification fails with a diagnostic identifying the inspection problem

### Requirement: Reproduce the policy locally without changing the checkout

The repository SHALL provide a local command implementing the same closure policy used by CI. It SHALL require neither running application services nor installation of OpenSpec, and SHALL not alter tasks, synchronize specifications or move files. Documentation SHALL identify `OpenSpec closure` as a check to require in branch protection when merge blocking is desired.

#### Scenario: Reproduce a failing check locally
- **WHEN** a contributor runs the documented command against the same checkout verified by CI
- **THEN** it returns the same closure outcome, lists the same active changes and leaves all checkout files unchanged

### Requirement: Preserve completed specifications before archiving

Closing a completed change SHALL preserve its verified task evidence, incorporate its delta into the main specifications and retain newer compatible requirements and scenarios before moving its artifacts into dated archive history. The closure check SHALL not automatically perform these operations or treat its own passing result as proof of implementation correctness.

#### Scenario: Close changes with overlapping specification history
- **WHEN** completed changes are synchronized and a main requirement includes newer compatible scenarios than an older delta
- **THEN** synchronization preserves those scenarios and the intended final behavior, validates the resulting specifications, and only then archives the completed changes

#### Scenario: Close the policy change itself
- **WHEN** the closure policy is implemented, verified, independently reviewed, synchronized and archived together with the completed pending changes
- **THEN** the final checkout has no active change directories and the closure check succeeds without an exception for its own change
