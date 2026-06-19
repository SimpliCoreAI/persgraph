# PersGraph Phase-2 Directory Rework — File Mapping & Rollback Plan

## Current State
- `agents/` exists with 5 empty agent directories (`.gitkeep` only)
- `runtime/` exists as empty (`.gitkeep` only)
- `workflows/` exists as empty (`.gitkeep` only)
- All runtime code lives in: `scripts/`, `second_brain/`, and `db/`
- `server.py` is top-level web server
- Entry points: `scripts/command.py` (Telegram), `scripts/queue_worker.py`, cron scripts

## File Categories & Proposed Destinations

### CATEGORY A: Core Orchestrator (→ agents/orchestrator/)
**These files handle top-level task routing and command dispatch.**

| Current Path | Purpose | Move To | Notes |
|---|---|---|---|
| `scripts/command.py` | Main Telegram command router | `agents/orchestrator/command_handler.py` | 1420 lines; imports second_brain.* for dispatch; no other scripts import it |
| `scripts/query.py` | Search/query orchestrator | `agents/orchestrator/query_handler.py` | ~150 lines; imports second_brain.query, llm |
| `server.py` | Flask web server | `agents/orchestrator/server.py` | Top-level; serves dashboard, login, travel tools |

**Rationale:** These are the main user-facing orchestrators. They dispatch to specialized workers. Isolating them makes the route clear.

---

### CATEGORY B: Async Queue & State (→ runtime/)
**These files manage async task distribution and state persistence.**

| Current Path | Purpose | Move To | Notes |
|---|---|---|---|
| `scripts/queue_worker.py` | Processes queued async saves | `runtime/queue_worker.py` | 200 lines; main cron loop; imports second_brain.queue |
| `data/queue.json` | Runtime queue state | `runtime/queue.json` | Data; no logic |

**Rationale:** Queue management is infrastructure. Put it in runtime alongside orchestration primitives.

---

### CATEGORY C: Worker Scripts (→ agents/<agent>/)
**These are specialized, standalone workers that process domain-specific tasks.**

#### Email Handler Worker
| Current Path | Purpose | Move To | Notes |
|---|---|---|---|
| `scripts/email_worker.py` | Ingest + process emails | `agents/email-handler/worker.py` | 400 lines; imports ingesters.email, learning_db |

#### Calendar Prebrief Worker
| Current Path | Purpose | Move To | Notes |
|---|---|---|---|
| `scripts/check_appointments.py` | Hourly appointment check | `agents/calendar-prebrief/check_appointments.py` | 80 lines; imports second_brain.notes; runs on cron |
| `scripts/run_prebrief.py` | Build daily prebrief | `agents/calendar-prebrief/run_prebrief.py` | 150 lines; imports connectors.prebrief_builder |
| `scripts/debrief.py` | Evening debrief digest | `agents/calendar-prebrief/debrief.py` | 200 lines; imports ConnectorAPI |

#### Ingest Worker
| Current Path | Purpose | Move To | Notes |
|---|---|---|---|
| `scripts/ingest.py` | Main ingest orchestrator | `agents/ingest-worker/ingest.py` | 300 lines; routes to specific ingesters |
| `scripts/ingest_cc_rewards.py` | CC rewards ingest | `agents/ingest-worker/ingest_cc_rewards.py` | 200 lines; standalone domain logic |
| `db/ingest.py` | DB ingest helpers | `agents/ingest-worker/db_helpers.py` | Move with ingest |

#### Learning Worker
| Current Path | Purpose | Move To | Notes |
|---|---|---|---|
| `scripts/learning_worker.py` | Pattern extraction cron | `agents/learning-worker/learning_worker.py` | 250 lines; processes learning.db cursor |
| `scripts/learning_cron.py` | Learning batch trigger | `agents/learning-worker/cron_trigger.py` | 50 lines; small orchestrator |

#### Travel Scout Worker
| Current Path | Purpose | Move To | Notes |
|---|---|---|---|
| `scripts/explore_location.py` | Explore/search locations | `agents/travel-scout/explore_location.py` | 300 lines; location search logic |
| `scripts/explore_mode.py` | Explore mode main loop | `agents/travel-scout/explore_mode.py` | 400 lines; async state machine |
| `scripts/explore_mode_helpers.py` | Explore utilities | `agents/travel-scout/explore_helpers.py` | 200 lines; helper functions |

#### Weekly Briefing
| Current Path | Purpose | Move To | Notes |
|---|---|---|---|
| `scripts/weekly_briefing.py` | Sunday digest builder | `agents/weekly-briefing/worker.py` | 300 lines; cron every Sunday |

#### Utilities (stay in scripts/ for now)
| Current Path | Purpose | Notes |
|---|---|---|
| `scripts/send_email.py` | Email dispatch | Shared utility; not a standalone worker |
| `scripts/validate_poi_setup.py` | Setup validator | Setup-time only; not runtime |
| `scripts/track_api_cost.py` | API cost logger | Observability; shared by all agents |
| `scripts/query.py` | Query orchestrator | Already in Category A |
| `scripts/migrate_places.py` | Data migration | Setup/maintenance; not runtime |

**Rationale:** Each worker is a focused agent. Moving them together keeps agent responsibilities clear and enables independent scaling/testing.

---

### CATEGORY D: Shared Runtime Libraries (→ runtime/ or stay in place)
**These provide orchestration and validation primitives.**

| Current Path | Purpose | Recommendation | Notes |
|---|---|---|---|
| `runtime/` | (new) Orchestration primitives | Create `runtime/spawn.py`, `runtime/validation.py` | For OpenClaw sub-agent spawn logic, shared between agents |
| `db/queries.py` | DB query helpers | `runtime/db_queries.py` | Move with orchestration stack |
| `db/ingest.py` | DB ingest boilerplate | `agents/ingest-worker/db_helpers.py` | Domain-specific; keep with ingest |

**Rationale:** Keep truly shared primitives in runtime; move domain-specific logic to agents.

---

### CATEGORY E: Shared Libraries (→ stay in place OR add `runtime/lib/`)
**These should NOT move; they are shared by multiple agents.**

| Current Path | Purpose | Recommendation | Notes |
|---|---|---|---|
| `second_brain/` | All modules | Stay in place | Core library; imported by all agents; do not move yet |
| `scripts/__init__.py` | Module marker | Stay | Preserve for now |
| `scripts/AGENTS.md` | Documentation | Move to `docs/orchestrator-conventions.md` | Reference guide for agent developers |

**Rationale:** Moving second_brain would require all import paths to update. Defer to Phase 3.

---

### CATEGORY F: Templates & Workflows (→ workflows/)
**Reusable task patterns and blueprints.**

| Current Path | Purpose | Move To | Notes |
|---|---|---|---|
| `scratchpad/template.md` | Command template | `workflows/command_template.md` | Template for new slash commands |
| `scratchpad/prompts.md` | Prompt library | `workflows/prompt_library.md` | Reusable prompts across agents |

**Rationale:** Put reusable patterns in workflows/ for agent developers to copy.

---

### CATEGORY G: Documentation (→ docs/architecture/)
**Already mostly in place; ensure consistency.**

| Current Path | Purpose | Status | Notes |
|---|---|---|---|
| `docs/architecture/directory-rework.md` | Phase-2 plan | Keep | Already there; update with finalized structure |
| `scripts/AGENTS.md` | Scripting conventions | Move to `docs/architecture/agent-conventions.md` | Clarify for new agent developers |
| `docs/swarmforge-vision.md` | Vision doc | Keep | Already there |

---

## Rollback-Friendly First Batch (Minimal Safe Move)

**Batch 1: Core Orchestrator & Queue (5 files, 2 directories)**

**Why this batch first:**
1. Isolated from worker logic
2. No dependencies *within* the batch (queue is read by orchestrator, not vice versa)
3. Clear ownership: orchestrator files are never imported by workers
4. After move: only orchestrator files change; shared utilities unchanged

**Batch 1 Files:**

```
Move:
  scripts/command.py                    → agents/orchestrator/command_handler.py
  scripts/query.py                      → agents/orchestrator/query_handler.py
  scripts/queue_worker.py               → runtime/queue_worker.py
  server.py                             → agents/orchestrator/server.py
  data/queue.json                       → runtime/queue.json

Keep (no move):
  second_brain/                         (shared library; too many imports)
  scripts/send_email.py                 (utility; shared by multiple agents)
  scripts/track_api_cost.py             (observability; shared)
  db/                                   (shared; stays for now)
```

**Import Updates After Batch 1:**
1. Create `runtime/__init__.py` 
2. Create `agents/orchestrator/__init__.py`
3. If any files in `scripts/` need to import queue_worker, add path resolution in those files
4. Update cron job payloads in OpenClaw to point to new paths

**Verification After Batch 1:**
```bash
# Still works:
python -m scripts.send_email              # shared utility
python scripts/track_api_cost.py          # observability
python scripts/validate_poi_setup.py      # setup

# Now routed through agents/:
.venv/bin/python agents/orchestrator/command_handler.py "/ask ..." --sender <id>
.venv/bin/python agents/orchestrator/server.py               # web server
.venv/bin/python runtime/queue_worker.py                     # cron job

# Cron updates (if used):
# OLD: python scripts/queue_worker.py
# NEW: python runtime/queue_worker.py
```

**Rollback for Batch 1:**
```bash
# If anything breaks:
git mv agents/orchestrator/command_handler.py scripts/command.py
git mv agents/orchestrator/query_handler.py   scripts/query.py
git mv agents/orchestrator/server.py          server.py
git mv runtime/queue_worker.py                scripts/queue_worker.py
git mv runtime/queue.json                     data/queue.json
# Then: update cron jobs back to scripts/ paths
```

**Effort:** ~30 min (file moves + __init__.py creation + cron adjustment)

---

## Recommended Second Batch (After Validation)

**Batch 2: Email Handler Worker (1 file)**

```
Move:
  scripts/email_worker.py                → agents/email-handler/worker.py
  
Create:
  agents/email-handler/__init__.py
  
No import changes needed outside email_worker.py itself.
Cron/orchestrator call changes:
  OLD: python scripts/email_worker.py
  NEW: python agents/email-handler/worker.py
```

**Why this second:**
- Single file; no internal dependencies within batch
- Called from cron; isolated from command routing
- Can be tested independently after move

---

## Recommended Third Batch (After Batch 2)

**Batch 3: Calendar/Prebrief Workers (3 files)**

```
Move:
  scripts/check_appointments.py         → agents/calendar-prebrief/check_appointments.py
  scripts/run_prebrief.py               → agents/calendar-prebrief/run_prebrief.py
  scripts/debrief.py                    → agents/calendar-prebrief/debrief.py

Create:
  agents/calendar-prebrief/__init__.py

No import changes needed outside files themselves.
Cron updates needed (check_appointments runs on hourly cron).
```

**Why this third:**
- Same pattern as Batch 2
- Grouped by domain (calendar/prebrief)
- All cron-driven; no orchestrator dependency

---

## Final State After All Batches

```
agents/
  orchestrator/
    __init__.py
    command_handler.py      (was: scripts/command.py)
    query_handler.py        (was: scripts/query.py)
    server.py               (was: server.py)
  email-handler/
    __init__.py
    worker.py               (was: scripts/email_worker.py)
  calendar-prebrief/
    __init__.py
    check_appointments.py
    run_prebrief.py
    debrief.py
  ingest-worker/
    __init__.py
    ingest.py
    ingest_cc_rewards.py
    db_helpers.py
  travel-scout/
    __init__.py
    explore_location.py
    explore_mode.py
    explore_helpers.py
  learning-worker/
    __init__.py
    learning_worker.py
    cron_trigger.py
  weekly-briefing/
    __init__.py
    worker.py

runtime/
  __init__.py
  queue_worker.py         (was: scripts/queue_worker.py)
  queue.json              (was: data/queue.json)
  spawn.py                (new: OpenClaw sub-agent spawn helpers)
  validation.py           (new: input/output validation primitives)

workflows/
  __init__.py
  command_template.md
  prompt_library.md
  (expand as patterns emerge)

scripts/
  __init__.py
  send_email.py           (stays: shared utility)
  track_api_cost.py       (stays: observability)
  validate_poi_setup.py   (stays: setup/maintenance)
  AGENTS.md               (move to docs/ or make a compat shim)

second_brain/
  (unchanged; too many imports to move in Phase 2)

db/
  (unchanged; stay for now; can move if time permits)
```

---

## Testing & Verification Checklist

After **each batch move:**

1. **Import paths**: Run `python -m py_compile agents/**/*.py` to check syntax
2. **Cron jobs**: Verify OpenClaw cron still finds the new paths
3. **Telegram**: Test `/ask` and `/ingest` commands still route correctly
4. **Workers**: Spot-check that `python agents/*/worker.py` still runs
5. **Git**: Verify move preserved history: `git log --follow agents/orchestrator/command_handler.py`

---

## Risk Assessment

| Risk | Mitigation |
|---|---|
| Cron jobs break | Update cron job payloads in OpenClaw after each batch |
| Import paths fail | Create `__init__.py` in each agent dir; test before committing |
| Telegram routing fails | Ensure `scripts/send_email.py` still accessible to orchestrator |
| Rollback is slow | Each batch is independent; rolling back one batch does not affect others |

---

## Summary

- **Batch 1 (Orchestrator & Queue):** 4 files → agents/, runtime/. Smallest safe first move.
- **Batch 2 (Email Worker):** 1 file → agents/email-handler/. Single-file, low risk.
- **Batch 3 (Calendar Workers):** 3 files → agents/calendar-prebrief/. Grouped by domain.
- **Remaining workers:** Can follow same pattern over time.
- **Shared libraries:** second_brain/, db/ stay for Phase 3.
- **Workflows & templates:** Move reusable patterns to workflows/ as they emerge.

**Total effort for Phase 2:** ~2 hours across 3 batches.

---

## Implementation Guide

### Before Batch 1: Prepare
```bash
cd ~/AgenticHub/Persgraph
git checkout -b phase2-directory-rework-batch1
```

### Batch 1 Execution
```bash
# Move orchestrator files
git mv scripts/command.py agents/orchestrator/command_handler.py
git mv scripts/query.py agents/orchestrator/query_handler.py
git mv server.py agents/orchestrator/server.py

# Move queue infrastructure
git mv scripts/queue_worker.py runtime/queue_worker.py
git mv data/queue.json runtime/queue.json

# Create __init__.py files
touch agents/orchestrator/__init__.py
touch runtime/__init__.py

git add -A
git commit -m "Phase 2: Move orchestrator files to agents/ and queue to runtime/

- Move command_handler, query_handler, server to agents/orchestrator/
- Move queue_worker and queue.json to runtime/
- Preserve git history with git mv
- Update cron job payloads separately
"
```

### After Each Batch: Verify
```bash
# Syntax check
python -m py_compile agents/orchestrator/*.py runtime/*.py

# Verify cron still callable
python agents/orchestrator/command_handler.py --help 2>&1 | head -5
python runtime/queue_worker.py --dry-run 2>&1 | head -5

# Review git history
git log --oneline -5
git log --follow agents/orchestrator/command_handler.py | head -10
```

### Rollback (if needed)
```bash
git reset --hard HEAD~1
# Then update cron jobs back to old paths
```
