# PersGraph MVP Routing Layer

## Overview

The PersGraph MVP routing layer provides:
1. **Command-to-worker routing** — maps commands to specialized worker types
2. **Tool/scope boundaries** — enforces capability isolation per worker
3. **Backward compatibility** — existing entrypoints remain unchanged
4. **Extensibility** — new workers can be added without modifying the orchestrator

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ User Input (Telegram, CLI, etc.)                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ orchestrator.run_with_routing(raw_input, sender_id)         │
│  - Resolves user context                                    │
│  - Invokes router.route_command()                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ router.route_command(raw_input, user_context)               │
│  - Parses command + args                                    │
│  - Looks up WorkerType in registry                          │
│  - Returns RoutedTask (worker, payload, metadata)           │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼ (MVP: delegation)       ▼ (Future: worker spawn)
┌──────────────────────┐   ┌────────────────────────────────┐
│ Existing command     │   │ Worker process                 │
│ handlers in          │   │  - InboxTriageWorker           │
│ command_handler.py   │   │  - CalendarPrepWorker          │
│                      │   │  - TravelScoutWorker           │
│                      │   │  - IngestWorker                │
│ (unchanged)          │   │  - DebriefWorker               │
│                      │   │                                │
└──────────────────────┘   └────────────────────────────────┘
        │                          │
        │                          │
        └──────────┬───────────────┘
                   │
                   ▼
          ┌─────────────────┐
          │ Result (string) │
          └─────────────────┘
```

## Worker Types

| Worker | Commands | Allowed Tools | External Services |
|--------|----------|---|---|
| **inbox_triage** | `/note`, `/task`, `/place`, `/places`, `/bucketlist` | places_db, notes_db, task_db | sqlite |
| **calendar_prep** | `/appointment`, `/schedule` | calendar_db, notes_db, llm | google_calendar, notion |
| **travel_scout** | `/TripToggle`, `/explore_*` | places_db, explore_state, maps, llm | supabase, google_maps, chroma |
| **ingest** | `/ingest`, `/wiki-ingest` | chroma, ollama, url_fetcher, wikipedia, docs_storage | chroma, ollama, supabase |
| **debrief** | `/digest`, `/debrief` | chroma, llm, calendar_db, places_db, notes_db (read-only) | chroma, supabase |

## Tool/Scope Boundaries

Each worker is restricted to:
- **Allowed Tools**: The only databases/services it can access
- **Allowed Services**: External APIs it can invoke
- **External API Requirement**: Whether it needs API keys from `.env`

Example: InboxTriageWorker can only use places_db, notes_db, task_db (SQLite). It **cannot**:
- Call the LLM
- Access ChromaDB
- Ingest URLs
- Query calendar

This prevents:
- Credential leaks (worker can't access APIs outside its scope)
- Resource contention (worker can't monopolize ChromaDB)
- Blast radius (error in one worker doesn't corrupt shared state)

## Usage Patterns

### Pattern 1: Using the Router Directly

```python
from agents.orchestrator.router import route_command
from agents.orchestrator.worker_registry import get_worker_for_command

# Route a command
routed = route_command("/note buy groceries", user_context={"tier": "user"})

# Check what worker will handle it
if routed.worker_type:
    print(f"Worker: {routed.worker_type.value}")
    print(f"Tools: {routed.worker_type}...")  # See capabilities

# Validate capability before execution
from agents.orchestrator.router import validate_worker_access
allowed, denied = validate_worker_access(routed.worker_type, ["places_db", "llm"])
if denied:
    print(f"Worker is not allowed to use: {denied}")
```

### Pattern 2: Using the Orchestrator (MVP)

```python
from agents.orchestrator.orchestrator import run_with_routing

result = run_with_routing("/note buy groceries", sender_id="12345")
print(result)
```

### Pattern 3: Introspection/Debugging

```python
from agents.orchestrator.orchestrator import describe_routing

routing = describe_routing()
print(routing["routing_table"])  # Command → worker mapping
print(routing["workers"])  # Worker capabilities
```

### Pattern 4: Using a Worker Directly (for testing)

```python
from agents.inbox_triage.worker import InboxTriageWorker
from agents.orchestrator.router import RoutedTask, route_command

# Create a routed task
routed = route_command("/note test", user_context={"tier": "user"})

# Execute with the worker
worker = InboxTriageWorker()
result = worker.run(routed)
print(result)
```

## Backward Compatibility

Existing code continues to work:

```python
from agents.orchestrator import command_handler

# Old way (still works)
result = command_handler.run("/note buy groceries", sender_id="12345")
```

The routing layer is **opt-in**. The command_handler is the default execution path.

## Adding a New Worker

1. **Define the WorkerType** in `worker_registry.py`:
   ```python
   class WorkerType(Enum):
       MY_WORKER = "my_worker"  # Add this
   ```

2. **Add capabilities**:
   ```python
   WORKER_CAPABILITIES[WorkerType.MY_WORKER] = WorkerCapabilities(
       worker_type=WorkerType.MY_WORKER,
       allowed_tools={"tool1", "tool2"},
       allowed_services={"service1"},
       requires_external_api=False,
       description="What this worker does...",
   )
   ```

3. **Add command mappings** in `worker_registry.py`:
   ```python
   def get_worker_for_command(command: str) -> WorkerType | None:
       command_to_worker = {
           "/mycommand": WorkerType.MY_WORKER,
           # ... rest
       }
   ```

4. **Create the worker module** at `agents/my_worker/worker.py`:
   ```python
   from agents.orchestrator.worker_base import BaseWorker
   
   class MyWorker(BaseWorker):
       def __init__(self):
           super().__init__(WorkerType.MY_WORKER)
       
       def execute(self, payload: dict) -> str:
           # Logic here
           return result
   
   def run(routed_task) -> str:
       worker = MyWorker()
       return worker.run(routed_task)
   ```

5. **Add entrypoint** in `router.py`:
   ```python
   entrypoints = {
       WorkerType.MY_WORKER: "agents.my_worker.worker.run",
   }
   ```

## Testing

### Test the Routing Table

```bash
cd ~/AgenticHub/Persgraph
python -c "
from agents.orchestrator.orchestrator import describe_routing
import json
print(json.dumps(describe_routing(), indent=2))
"
```

### Test a Single Command

```bash
python -c "
from agents.orchestrator.router import route_command
r = route_command('/note buy groceries', {'tier': 'user'})
print(f'Worker: {r.worker_type}')
print(f'Command: {r.command}')
print(f'Args: {r.args}')
"
```

### Test Worker Capability Validation

```bash
python -c "
from agents.orchestrator.router import validate_worker_access, route_command
from agents.orchestrator.worker_registry import WorkerType

ok, denied = validate_worker_access(WorkerType.INBOX_TRIAGE, ['places_db', 'llm', 'chroma'])
print(f'Allowed: {ok}')
print(f'Denied tools: {denied}')
"
```

## Configuration

Set `ROUTING_DEBUG=1` to enable routing logging:

```bash
ROUTING_DEBUG=1 python scripts/command.py "/note test"
# Logs to stderr: [ROUTING] {'command': '/note', 'worker_type': 'inbox_triage', ...}
```

## MVP vs. Future

**MVP (current):**
- Routing layer exists and maps commands to workers ✅
- Tool/scope boundaries are defined in code ✅
- Workers delegate to existing command handlers ✅
- Backward compatibility maintained ✅

**Future iterations:**
- Spawn worker processes (not threads)
- Enforce capability isolation at runtime
- Add inter-worker queues for async execution
- Implement worker health checks and restarts
- Add metrics/tracing per worker
