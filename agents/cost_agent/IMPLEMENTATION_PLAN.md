# Cost Agent MVP — Implementation Plan & Acceptance Criteria

**Date Created:** 2026-06-19  
**Target Phase:** MVP (Phase 1 + Phase 2)  
**Status:** DRAFT → APPROVED

---

## Executive Summary

Implement a lightweight cost attribution agent integrated with Langfuse tracing as a *system trace layer*, capable of:
1. **Capturing cost metadata** from Langfuse observations (input/output tokens, model used, API pricing)
2. **Attributing costs** to users, agents, and operations for fine-grained cost reporting
3. **Reporting and alerting** on spend patterns (daily, weekly summaries, budget thresholds)
4. Maintaining **backward compatibility** with existing cost tracking in `scripts/track_api_cost.py`

The cost agent lives under `agents/cost-agent/` and operates as a *passive observer* of Langfuse traces, not as an active command in the orchestrator (no /cost-agent command).

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│ Langfuse Cloud (Observability Backend)                           │
│  ├── Observations (spans + models + tokens + latency)            │
│  └── Traces (request → operation → sub-operations)               │
└──────────────────────────────────────────────────────────────────┘
                              ▲
                              │ (async polling + webhooks)
┌──────────────────────────────────────────────────────────────────┐
│ Cost Agent (agents/cost-agent/)                                  │
│  ├── Langfuse Poller: fetch observations periodically            │
│  ├── Cost Calculator: extract model, tokens, apply pricing       │
│  ├── Attribution Engine: assign costs to users/ops/agents        │
│  ├── Reporter: daily/weekly summaries, budget alerts             │
│  └── Shared Helpers: pricing tables, formatters                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Storage (data/cost_*.json, future: database)                     │
│  ├── cost_agent_state.json (poller cursor, last_seen_trace_id)   │
│  ├── cost_by_user.json (daily/cumulative costs by Telegram ID)   │
│  ├── cost_by_operation.json (daily costs by operation type)      │
│  └── cost_by_model.json (daily costs by LLM model)               │
└──────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌──────────────────────────────────────────────────────────────────┐
│ Orchestrator (existing routing & approval layer)                 │
│  └── Audit trail includes trace IDs → cost agent joins on them   │
└──────────────────────────────────────────────────────────────────┘
```

**Key Design Decisions:**
- **Passive observer:** Cost agent does not inject into command flow; it polls Langfuse asynchronously.
- **Langfuse as single source of truth:** All cost calculations derive from Langfuse trace data (tokens, models, latencies).
- **Pricing tables:** Centralized, versioned pricing (per provider/model, in effect date).
- **Attribution metadata:** User ID (from trace tags/context), agent name, operation category.
- **Backward compatible:** Legacy `track_api_cost.py` still works; cost agent extends it with richer metadata.

---

## Directory Structure (Phase 1)

```
agents/cost-agent/
├── __init__.py                    # Package init + public API
├── IMPLEMENTATION_PLAN.md         # This file
├── PHASE_ROADMAP.md               # Phase 1-3 details + timing
├── core/
│   ├── __init__.py
│   ├── poller.py                  # Langfuse trace fetcher (async)
│   ├── calculator.py              # Token → cost calculation
│   └── attribution.py             # Cost → user/op/agent assignment
├── shared/
│   ├── __init__.py
│   ├── pricing.py                 # Pricing tables, versioned
│   ├── formatters.py              # JSON/report formatting
│   └── constants.py               # Tags, collection names, limits
├── reporters/
│   ├── __init__.py
│   ├── daily_summary.py           # Daily cost report (email/Telegram)
│   └── budget_alerts.py           # Spend thresholds + notifications
└── tests/
    ├── __init__.py
    ├── test_calculator.py         # Unit tests for cost math
    ├── test_attribution.py        # Attribution logic tests
    └── test_integration.py        # End-to-end mock Langfuse tests
```

---

## Phase 1 — Core MVP (This Sprint)

### Goals
- ✅ Establish lightweight poller that reads Langfuse observations
- ✅ Implement cost calculator (tokens + pricing tables)
- ✅ Basic attribution (extract user_id, model, operation from traces)
- ✅ Store state in JSON (cost_agent_state.json, cost_by_user.json, cost_by_operation.json)
- ✅ Validate with unit tests + integration test
- ✅ Preserve backward compatibility

### Deliverables
1. **`core/poller.py`** — Async Langfuse client wrapper
   - Fetch observations created after `last_seen_timestamp`
   - Handle pagination, retries, and rate limits
   - Extract trace_id, model, input_tokens, output_tokens, metadata

2. **`core/calculator.py`** — Cost calculation logic
   - `calculate_cost(model, input_tokens, output_tokens) → (cost_usd, provider)`
   - Fallback to default pricing if model not found
   - Handle edge cases: zero tokens, unknown models

3. **`core/attribution.py`** — Extract cost attributes
   - `extract_user_id(observation) → str | None` (from tags or trace context)
   - `extract_operation(observation) → str | None` (llm_type, domain)
   - `extract_model_info(observation) → dict` (model, provider)

4. **`shared/pricing.py`** — Centralized pricing tables
   - Dict[model, Dict[provider, Dict["input"|"output", price_per_1m_tokens]]]
   - Version comments for each pricing update date

5. **`shared/formatters.py`** & **`shared/constants.py`** — Helpers
   - JSON serialization with decimal precision
   - Tag enums (llm, user_id, operation_type)
   - Collection names (cost_by_user, cost_by_operation, etc.)

6. **State & data files** (created on first run)
   - `data/cost_agent_state.json` — `{ last_seen_trace_id, last_seen_timestamp, poller_version }`
   - `data/cost_by_user.json` — `{ daily: { YYYY-MM-DD: { user_id: cost_usd } }, total: { user_id: cost_usd } }`
   - `data/cost_by_operation.json` — `{ daily: { YYYY-MM-DD: { op_type: cost_usd } }, total: { op_type: cost_usd } }`
   - `data/cost_by_model.json` — `{ daily: { YYYY-MM-DD: { model: cost_usd } }, total: { model: cost_usd } }`

7. **Unit tests** (`tests/`)
   - Cost calculation logic (various models, token counts)
   - Attribution extraction (trace metadata parsing)
   - JSON state persistence

### Acceptance Criteria (Phase 1)

| # | Criterion | Details | Status |
|---|-----------|---------|--------|
| 1.1 | Poller retrieves Langfuse observations | Successfully fetch observations via Langfuse API; handle auth + pagination | PENDING |
| 1.2 | Cost calculation is accurate | Test against known model + token counts; results ±1% of expected cost | PENDING |
| 1.3 | Attribution captures user_id & operation | Extract from trace metadata; fallback to "unknown" if missing | PENDING |
| 1.4 | State persists correctly | `last_seen_timestamp` advances; no duplicate cost records on re-run | PENDING |
| 1.5 | Backward compatible | Legacy `track_api_cost.py` still works; cost agent data files are separate | PENDING |
| 1.6 | Error resilient | Langfuse unavailable → poller skips silently; no data loss | PENDING |
| 1.7 | All tests pass | Unit + integration tests run successfully; mocked Langfuse API | PENDING |
| 1.8 | Code reviewed & safe | No unintended side effects; no secrets hardcoded; safe to deploy | PENDING |

---

## Phase 2 — Reporting & Alerts (Next Sprint)

### Goals
- Implement daily cost summary (email + Telegram)
- Budget threshold alerts (daily limit exceeded)
- Dashboard views (cost by user, model, operation, time)
- Integration with orchestrator audit trail

### Deliverables
1. **`reporters/daily_summary.py`**
   - Format daily cost report (Markdown table)
   - Send via Telegram to user (or admin channel)
   - Include top operations, models, users

2. **`reporters/budget_alerts.py`**
   - Define per-user budget limits (config)
   - Alert when daily spend exceeds threshold (Telegram + email)
   - Weekly rollup alert

3. **Dashboard integration**
   - Grafana/Streamlit page showing cost trends
   - Drill-down by user, operation, model, time range

### Acceptance Criteria (Phase 2)
- [ ] Daily summary reports deliver on schedule
- [ ] Budget alerts trigger correctly
- [ ] Dashboard renders cost data without lag (<2s load)
- [ ] Report formatting is clear and actionable

---

## Phase 3 — Advanced Features (Future)

### Goals
- ML cost estimation (predict daily spend based on recent trends)
- Cost optimization recommendations (identify expensive operations)
- Multi-tenant billing (assign costs across teams/projects)
- Database migration (JSON → SQL for historical queries)

### Deliverables (sketch)
1. **Cost predictor** — Time series forecasting (7-day moving avg)
2. **Optimization hints** — Identify operations with >3 std dev cost spikes
3. **Billing rules** — Configurable cost allocation rules for shared services
4. **Database schema** — Tables for observations, costs, attributions, prices

---

## Implementation Safety & Risks

### Risk: Data Integrity
**Risk:** Cost records duplicated if poller crashes between fetch + state write.  
**Mitigation:** 
- Use atomic writes for state file (write-to-temp, then rename).
- Trace ID is unique key; check for duplicates before updating cost records.
- Idempotent cost calculations (same trace_id → same cost, always).

### Risk: Langfuse API Rate Limits
**Risk:** Poller hits rate limits and misses traces.  
**Mitigation:**
- Implement exponential backoff (start 1s, cap at 60s).
- Respect `Retry-After` header.
- Log rate limit events; alert on sustained throttling.

### Risk: Pricing Stale or Incorrect
**Risk:** Pricing tables outdated; cost calculations wrong.  
**Mitigation:**
- Version pricing tables with effective dates.
- Manual update process (config review in PR).
- Validation test: sample cost against known invoice costs.

### Risk: Attribution Errors (User ID Missing)
**Risk:** Traces lack user context; costs can't be attributed.  
**Mitigation:**
- Fallback to "unknown_user" category.
- Log missing attributions; alert on >10% unmapped costs.
- Recommendation: add user_id tag to all traces (orchestrator responsibility).

### Risk: Backward Compatibility Breakage
**Risk:** Changes to cost tracking break legacy scripts.  
**Mitigation:**
- Keep `track_api_cost.py` untouched; cost agent is separate.
- New JSON files in `data/cost_*.json`; don't modify `api_costs.json`.
- Maintain same JSON structure (daily, total keys) in new files.

---

## Testing Strategy

### Unit Tests
```python
# tests/test_calculator.py
test_calculate_cost_known_model()
test_calculate_cost_unknown_model_fallback()
test_calculate_cost_zero_tokens()

# tests/test_attribution.py
test_extract_user_id_from_trace_tags()
test_extract_user_id_missing_fallback()
test_extract_operation_type()

# tests/test_pricing.py
test_pricing_table_all_models_covered()
test_pricing_versioning()
```

### Integration Tests
```python
# tests/test_integration.py
test_poller_with_mock_langfuse()
test_full_cost_flow_observation_to_json()
test_state_persistence_and_replay()
```

### Manual Smoke Tests (Phase 1 completion)
- [ ] Run poller against live Langfuse; confirm observations fetched
- [ ] Verify JSON output (cost_by_user.json, cost_by_operation.json)
- [ ] Compare costs to legacy `track_api_cost.py` output; within 1%
- [ ] Restart poller; confirm no duplicate costs

---

## Configuration & Deployment

### Environment Variables (existing settings.py)
- `LANGFUSE_SECRET_KEY` — Already configured
- `LANGFUSE_PUBLIC_KEY` — Already configured
- `LANGFUSE_HOST` — Already configured (default: https://us.cloud.langfuse.com)

### New Config (to add to `second_brain/config.py`)
```python
# Cost agent settings
cost_agent_enabled: bool = True
cost_agent_poll_interval_seconds: int = 300  # 5 min
cost_agent_budget_daily_usd: float = 50.0  # per user (soft limit)
cost_agent_alert_slack_channel: str = ""  # optional
```

### Deployment Steps
1. Create `agents/cost-agent/` directory structure
2. Add unit + integration tests
3. Run tests (all pass)
4. First run: poller creates state file, no errors
5. Verify JSON files created in `data/`
6. Schedule poller as cron job or background task

---

## Success Metrics

### MVP Success (Phase 1)
- ✅ Poller runs without errors for 7 consecutive days
- ✅ Cost records in JSON files; no duplicates
- ✅ Cost accuracy within 1% of manual Langfuse dashboard check
- ✅ Backward compatible (legacy scripts unaffected)
- ✅ Test coverage >80% for core modules

### Phase 2 Success
- [ ] Daily summaries delivered on time (24h accuracy)
- [ ] Budget alerts triggered correctly (within 1 hour of threshold)
- [ ] Dashboard loads <2s; displays accurate cost trends

### Phase 3 Success (Future)
- [ ] Cost predictor accuracy (MAPE <10%)
- [ ] Optimization hints reduce top operation costs by >5%
- [ ] Database migration complete; historical queries <100ms

---

## Blockers & Open Questions

### Q1: Should cost agent be a scheduled worker (cron) or background task?
- **A:** Phase 1: command-line script + cron job. Phase 2: integrate with orchestrator background worker pool.

### Q2: How to handle multi-user billing (team costs)?
- **A:** Phase 1: flat rate per user. Phase 2: add cost allocation rules (team_id, project_id tags).

### Q3: What if Langfuse data is incomplete (missing tokens)?
- **A:** Phase 1: skip incomplete observations. Phase 2: estimate based on model/latency.

### Q4: Should cost agent write to orchestrator audit trail?
- **A:** Phase 2: cost events in audit log. Phase 1: separate logs only.

---

## Next Steps

1. **Approval:** Review this plan; green-light implementation
2. **Implementation:** Create Phase 1 files per directory structure
3. **Testing:** Run unit + integration tests; validate with live Langfuse
4. **Smoke test:** 7-day run without issues
5. **Handoff:** Phase 1 complete; hand off to Phase 2 planning

---

**Author:** Subagent (Cost Agent MVP)  
**Review Status:** DRAFT  
**Last Updated:** 2026-06-19 22:45 UTC
