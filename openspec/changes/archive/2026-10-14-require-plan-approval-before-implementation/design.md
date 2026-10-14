# Design

## Context

See `proposal.md` for motivation. `AGENTS.md` currently refers to existing authorization and "authorized implementation" without defining the plan review gate. The installed proposal skill already requires stopping after planning. This design resolves that authorization ambiguity without changing the skills.

The coordinator presented the concrete `AGENTS.md` adjustment in conversation, and the user explicitly answered "si" in a later message. These artifacts record that approved adjustment; they do not require the user to approve the same scope again.

## Goals / Non-Goals

**Goals:** Make the authorization rule consistent between the required workflow and routing steps 3 and 4; preserve read-only exploration, authorized planning, and autonomy within approved scope.

**Non-Goals:** Change application behavior, hexagonal boundaries, agent definitions, installed skills, or the existing backend relocation. Only `AGENTS.md` is an implementation target.

## Decisions

- Replace the existing authorization paragraph with an explicit requirement to present scope, affected files, acceptance scenarios, and verification; end the turn; and wait for explicit approval in a later user message. This gate covers implementation changes to code, tests, documentation, dependencies, configuration, and file moves. Read-only investigation and authorized OpenSpec planning can precede it. Leaving the current general reference to authorization would preserve the ambiguity.
- State that ordinary initial add/change/fix requests do not approve an unseen plan. Preserve only an explicit user instruction to skip plan review as a waiver. Planning-only requests never authorize implementation.
- Preserve authorization for routine implementation within approved scope. Material changes to scope or intended behavior require a revised plan and approval. Requiring approval for every implementation detail would add unnecessary pauses.
- Append a reference to the gate in routing step 3 and replace step 4's vague opening with "After the plan-review gate above is satisfied". Keep the remaining agent workflow and verification instructions intact.
- Use `skip_specs: true` because this is workflow documentation with no application capability change. Verify by document review against the scenarios below and strict OpenSpec validation; no application test changes are warranted.

## Acceptance Scenarios

1. **Initial action request:** An add/change/fix request permits authorized planning; the coordinator presents the plan and ends the turn before implementation, including documentation edits or file moves.
2. **Later approval:** Explicit approval of that presented plan in a later user message permits implementation and routine verification within its scope, without another approval request.
3. **Material revision:** A material scope or intended behavior change requires presenting the revised plan and obtaining approval before implementing that change.
4. **Explicit waiver:** "Implement without plan review" explicitly waives the review gate; an ordinary initial action request does not.
5. **Exploration or planning only:** Read-only exploration and authorized planning remain possible; a planning-only request never authorizes implementation.

## Risks / Trade-offs

- A broad exception could swallow the gate → Require an explicit instruction to skip review and deny implied waiver from ordinary action requests.
- Repeated approvals could obstruct approved work → Preserve approval for routine work within the accepted scope, including this already-approved documentation adjustment.
