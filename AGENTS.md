# Repository instructions

## Required development workflow

Always use OpenSpec and the project SDD agents for work in this repository.
This applies to features, bug fixes, refactoring, tests, documentation,
dependencies, and configuration changes, even when the user does not mention
OpenSpec. Keep the size of the planning artifacts proportional to the change.

For questions and investigations, consult the relevant specifications and use
the exploration workflow without creating a change or editing files unless the
user requests it. Invoke the agents relevant to the requested phase; a question
does not require implementation or a full development cycle.

Before implementation, present the OpenSpec plan to the user, including its
scope, affected files, acceptance scenarios, and verification. End the turn and
wait for explicit approval of that plan in a later user message. This gate
applies to code, tests, documentation, dependencies, configuration, and file
moves. Read-only investigation and authorized OpenSpec planning may precede it.

An initial request to add, change, or fix something does not approve an unseen
plan. Only an explicit user instruction to skip plan review waives this gate.
A planning-only request never authorizes implementation.

Approval remains valid for routine implementation and verification within the
accepted scope; do not request it again for that work. Material changes to scope
or intended behavior require presenting the revised plan and obtaining approval
before implementing those changes. Follow explicit user instructions and any
applicable skill or environment permission requirements without adding unrelated
approval steps.

## Coordinator and agents

The main Codex agent is the coordinator. Delegate phase work to these project
agents, whose definitions are the source of truth for their instructions and
model settings:

| Agent | Definition | Model | Reasoning | Responsibility |
| --- | --- | --- | --- | --- |
| `sdd_planner` | `.codex/agents/sdd_planner.toml` | `gpt-6-astra` | `ultra` | Exploration, requirements, acceptance scenarios, design, tasks, and planning updates. |
| `sdd_builder` | `.codex/agents/sdd_builder.toml` | `gpt-6.1-sol` | `medium` | Implementation, relevant tests, and fixes from review. |
| `sdd_reviewer` | `.codex/agents/sdd_reviewer.toml` | `gpt-6.1-sol` | `high` | Independent review against specifications, architecture, and test evidence. |

- Use the custom agents by name. If the client only supports explicit spawning,
  read the corresponding definition and pass its instructions, model, and
  reasoning effort to the spawned agent. Do not silently substitute a model or
  claim delegation that did not happen.
- Give each agent the change name and path, relevant artifacts, exact task,
  allowed files, dependencies, and expected evidence or deliverables.
- Only the coordinator orchestrates the full workflow. Delegated agents perform
  their assigned phase and return results; they must not recursively start the
  same workflow or spawn more agents unless the coordinator explicitly asks.
- Parallelize independent investigations or tasks with separate file ownership.
  Wait for prerequisites before starting dependent work. Assign a single writer
  to shared planning artifacts and task tracking files.
- The coordinator integrates results, resolves conflicts, manages OpenSpec
  status and closure, and communicates with the user. If a required tool or model
  is unavailable, report the limitation and continue independent work that is
  possible without silently bypassing this workflow.

## OpenSpec phase routing

Read `openspec/config.yaml` and the relevant installed skill under
`.agents/skills/` before executing a phase. Use the CLI's current status and
instructions rather than assuming artifact names, paths, or readiness.

1. Inspect the project with `openspec list --json` and inspect existing
   specifications with `openspec list --specs`. Select an existing change when
   it matches the request. Confirm the initialized root before writing OpenSpec
   artifacts; do not initialize another root as a side effect.
2. Delegate investigation to `sdd_planner` with `openspec-explore` when
   requirements need clarification. Exploration does not implement code.
3. Delegate new change planning to `sdd_planner` with `openspec-propose`, or
   revise an existing change with `openspec-update-change`. Define observable
   behavior and acceptance scenarios before implementation; keep technical
   decisions in the design and executable work in tasks. Respect planning-only
   scope and the installed skills' phase boundaries. Present the plan and end
   the turn at the plan-review gate above before proceeding to implementation.
4. After the plan-review gate above is satisfied, delegate to `sdd_builder` with
   `openspec-apply-change`. Read the selected change's status and apply
   instructions, resolve missing prerequisites, and implement only assigned
   tasks. Mark tasks complete only after verification.
5. If implementation reveals a requirements or design mismatch, send the
   affected planning artifacts back to `sdd_planner` using
   `openspec-update-change`, then resume implementation against the coherent
   artifacts. Do not silently change the intended behavior to fit the code.
6. After implementation, use `sdd_reviewer` for an independent review against
   acceptance scenarios, error handling, regressions, architectural boundaries,
   and relevant tests. Send actionable findings to `sdd_builder` and recheck the
   affected work before declaring completion. The reviewer does not edit files.
7. Use `openspec-sync-specs` when synchronization is requested and
   `openspec-archive-change` when closure is authorized. The coordinator owns
   these operations. Finish and verify synchronization before moving the change
   into the archive; never race synchronization with archiving.

If `openspec` is not on `PATH`, check the existing Node/nvm installation and use
its CLI before assuming OpenSpec needs to be installed again.

## Architecture and verification

- Keep `domain/` independent of FastAPI and persistence frameworks.
- Keep `application/` focused on use cases and domain ports; adapters implement
  HTTP and database concerns. Use `main.py` as the composition root.
- Define migrations through Alembic and follow the repository README for their
  preparation and verification.
- Validate the selected change with
  `openspec validate <change-name> --strict`. Document validation is separate
  from proving that the implementation satisfies its requirements.
- Run tests appropriate to the change. The documented local suite is
  `uv run --extra dev python -m unittest discover -s tests -v`.
  Follow `README.md` for PostgreSQL integration prerequisites and
  `TEST_DATABASE_URL`; report skipped or unavailable checks accurately.
- In the final report, identify the change, completed work, review findings,
  verification results, and any remaining work. Distinguish implementation
  completion from synchronization and archiving.
