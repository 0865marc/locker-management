# Tasks

## 1. Clarify implementation authorization

- [x] 1.1 Replace the authorization paragraph in `AGENTS.md` with the approved plan review gate, its coverage, later-message approval, explicit waiver, and continued authorization within scope; verify the wording covers all five acceptance scenarios in `design.md` and preserves read-only exploration and authorized planning.
- [x] 1.2 Align routing steps 3 and 4 with that gate; verify their consistency with the required workflow, confirm implementation edits are limited to `AGENTS.md`, and run `openspec validate require-plan-approval-before-implementation --strict`.

## Verification evidence

- 1.1: inspected all five design scenarios: initial action requests require presenting the plan and ending the turn; later explicit approval covers routine work; material changes require revised approval; only an explicit instruction to skip review waives the gate; read-only exploration and authorized planning remain possible and planning-only requests never permit implementation. Coverage explicitly includes documentation, configuration, and file moves.
- 1.2: routing steps 3 and 4 refer to the same gate. Compared `AGENTS.md` with `/tmp/hexagonal-agents-before-plan-approval.md`: only the authorization paragraph and routing steps 3/4 changed. All 30 unrelated SHA-256 hashes in `/tmp/hexagonal-plan-approval-unchanged.json` match. `openspec validate require-plan-approval-before-implementation --strict` passed, with zero functional spec deltas accepted via `skip_specs: true`.
- Documentation-only change: no application tests required or run. Independent review remains with the coordinator; no synchronization or archiving performed.
