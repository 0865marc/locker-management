# Proposal

## Why

The coordinator implemented a repository change before presenting its plan for user approval. The installed proposal skill already separates planning from implementation; `AGENTS.md` should make that boundary and the meaning of authorization explicit.

## What Changes

- Require presenting the OpenSpec plan, ending the turn, and receiving explicit approval in a later user message before implementation.
- Clarify that initial requests to add, change, or fix something do not approve an unseen plan; an explicit instruction to skip plan review is the only waiver.
- Preserve approval within the accepted scope, require renewed approval for material scope or behavior changes, and align routing steps 3 and 4 with this rule.

## Capabilities

### New Capabilities

None. This is repository workflow documentation; application behavior is unchanged. The change declares `skip_specs: true`.

### Modified Capabilities

None.

## Impact

Only `AGENTS.md` is an implementation target. OpenSpec planning artifacts record this already-approved adjustment. No application code, dependencies, runtime configuration, installed skills, or architecture changes are included.
