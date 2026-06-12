# AGENTS.md — Persgraph Repo Guidance

## Role framing
Gru is the principal agentic engineer for Persgraph.
Treat Gru as the architecture lead with strong systems and data-engineering judgment.
Subagents should optimize for clean implementation, verification, and clear handoff notes.

## What subagents should do here
- Fix concrete repo issues end-to-end, not halfway.
- Verify behavior with compile/tests/targeted command runs.
- Prefer small, explicit helpers over clever indirection.
- Keep docs aligned with actual command behavior.
- Capture any unfinished edge cases in a scratchpad only if the task truly cannot be completed in one pass.

## Current priorities
1. Slash commands must work reliably from `scripts/command.py`.
2. SQLite-backed features should prefer direct query paths over fragile heuristics.
3. LLM formatting is desirable for user-visible output, but core retrieval/storage logic must work without it.
4. For Persgraph command work, correctness beats elegance.

## Guardrails
- Do not modify runtime data files unless the task explicitly requires it.
- Do not commit or push unless explicitly asked.
- Preserve user data in SQLite DBs.
- If fixing a list/query bug, inspect the actual DB path and rows rather than guessing.

## Command-specific guidance
- `/bucketlist`: use an explicit classifier/category and direct retrieval path.
- `/digest`: generate from real local data sources first, then LLM-polish output.
- `/wiki-ingest`: Obsidian-first persistence must survive indexing/LLM failures.

## Verification expectation
For any command change, try to show:
- syntax compile passes
- at least one save/add path works
- at least one list/read path works
- final output or named blocker
