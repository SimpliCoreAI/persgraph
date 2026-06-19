# PersGraph Directory Rework — First Pass

Goal: keep the rework targeted while making the repo feel like an orchestration platform.

## What this first pass adds
- `agents/` for focused orchestrator and worker workspaces
- `runtime/` for shared orchestration helpers and validation logic
- `workflows/` for reusable task patterns and templates
- `docs/architecture/` for repo layout notes and routing guardrails

## Proposed intent
This is a light reorg, not a deep refactor.
We are not moving product pages, data stores, or the existing command/runtime code yet.

## Suggested ownership model
- `agents/orchestrator/` — top-level task routing and handoff logic
- `agents/*/` — focused worker workspaces for specific duties
- `runtime/` — shared orchestration primitives
- `workflows/` — repeatable task blueprints
- `docs/architecture/` — keep the repo map current as the structure evolves

## Next step after this pass
Introduce thin adapters or entrypoints that point the existing command flows at the new workspace layout, one feature at a time.
