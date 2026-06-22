# Cost Agent — Phase Roadmap (1-3)

---

## Phase 1: Core MVP — Cost Capture & Attribution (Current)

### Duration: 1-2 weeks  
### Complexity: Medium  
### Risk Level: Low-Medium

### Scope
- Lightweight Langfuse poller (read-only)
- Token-based cost calculation
- Attribution (user_id, operation, model)
- State persistence (JSON)
- Unit + integration tests
- **Backward compatibility maintained**

### Key Deliverables
1. `core/poller.py` — Fetch Langfuse observations asynchronously
2. `core/calculator.py` — Cost math (tokens × pricing)
3. `core/attribution.py` — Extract user/op/model from traces
4. `shared/pricing.py` — Pricing tables (versioned)
5. `shared/formatters.py`, `shared/constants.py` — Helpers
6. `tests/` — Unit + integration tests (mock Langfuse)
7. JSON data files — `cost_by_user.json`, `cost_by_operation.json`, `cost_by_model.json`

### Entry Criteria
- [ ] Langfuse integration working in Persgraph (verified)
- [ ] Existing `tracing.py` API documented and stable
- [ ] Directory structure approved (agents/cost-agent/)

### Exit Criteria
- [x] IMPLEMENTATION_PLAN.md + PHASE_ROADMAP.md written
- [ ] All Phase 1 files implemented
- [ ] Unit tests pass (>80% coverage)
- [ ] Integration test passes (mock Langfuse + JSON I/O)
- [ ] 7-day smoke test completed (no duplicates, no errors)
- [ ] Cost accuracy verified (±1% vs. Langfuse UI)
- [ ] Backward compatible (legacy `track_api_cost.py` unaffected)
- [ ] Code reviewed (no security issues, no hardcoded secrets)

### Dependencies
- Langfuse Python SDK (v4+) — ✅ already in Persgraph
- `second_brain/config.py` (for settings) — ✅ existing
- `second_brain/tracing.py` (for patterns) — ✅ existing

### Known Unknowns
- **Langfuse API pagination behavior** — will validate during implementation
- **Trace context structure** — may need to add user_id tags in orchestrator (Phase 2)
- **Rate limiting strategy** — will implement backoff during Phase 1

---

## Phase 2: Reporting & Alerts (Next Sprint)

### Duration: 2-3 weeks  
### Complexity: Medium-High  
### Risk Level: Medium

### Scope
- Daily cost summary (Telegram + email)
- Budget threshold alerts
- Dashboard integration (Streamlit or Grafana)
- Orchestrator audit trail integration
- Operational monitoring

### Key Deliverables
1. `reporters/daily_summary.py` — Format + send daily report
2. `reporters/budget_alerts.py` — Threshold monitoring + alerts
3. Dashboard page (Streamlit) or Grafana datasource config
4. Cost event integration with orchestrator audit trail
5. Alert routing (Telegram, email, Slack)
6. Scheduled background task in orchestrator

### Entry Criteria
- [ ] Phase 1 complete + stable (7-day smoke test passed)
- [ ] Cost data flowing into JSON files reliably
- [ ] Phase 1 tests all passing

### Exit Criteria
- [ ] Daily reports deliver on schedule (23:59 UTC cutoff)
- [ ] Budget alerts trigger within 1 hour of threshold
- [ ] Dashboard renders cost data (<2s load time)
- [ ] Audit trail integration working (trace_id → cost record join)
- [ ] All Phase 2 tests passing

### Dependencies
- Phase 1 complete
- Telegram/email sending infrastructure (already in Persgraph)
- Orchestrator background worker pool (already exists)

### Open Questions
- Should budget limits be per-user or per-team? (recommendation: per-user in Phase 2, per-team in Phase 3)
- Alert frequency: daily, weekly, or both? (recommendation: daily threshold, weekly rollup)
- Dashboard tool: Streamlit or Grafana? (recommendation: Streamlit for speed, Grafana for production)

---

## Phase 3: Advanced Features (Backlog)

### Duration: 4+ weeks  
### Complexity: High  
### Risk Level: Medium-High

### Scope
- Cost prediction (time series forecasting)
- Optimization recommendations (anomaly detection)
- Multi-tenant billing (cost allocation rules)
- Database migration (JSON → SQL)
- Cost governance (approval workflows for high-spend operations)

### Key Deliverables
1. `predictor/forecaster.py` — 7-day cost prediction (moving avg, ARIMA, etc.)
2. `optimizer/recommender.py` — Identify expensive operations; suggest optimizations
3. `billing/rules.py` — Configurable cost allocation rules
4. `billing/database.py` — SQL schema + migration scripts
5. `governance/approval_workflow.py` — Human-in-the-loop for high-cost operations
6. Phase 3 tests (forecasting accuracy, rule engine logic)

### Entry Criteria
- [ ] Phase 2 complete + stable
- [ ] Cost data flowing reliably for ≥30 days (for forecasting training)
- [ ] User feedback on Phase 1-2 features positive

### Exit Criteria
- [ ] Cost predictor accuracy (MAPE <10%)
- [ ] Optimization hints generating actionable recommendations
- [ ] Database migration complete; no data loss
- [ ] Approval workflow integrated with command handler
- [ ] All Phase 3 tests passing

### Known Risks
- **Forecasting accuracy:** Limited training data in early phases; expect MAPE >15% initially
- **Cost allocation complexity:** Rules engine may become unwieldy; recommend declarative config
- **Database migration:** Risk of data loss; extensive testing required

### Deferred to Phase 3
- ML-based anomaly detection (cost spike alerts)
- Cost optimization ML models (predict savings from architecture changes)
- Chargeback/billing system (customer invoicing)

---

## Cross-Phase Considerations

### Backward Compatibility
- **Phases 1-3:** Legacy `scripts/track_api_cost.py` remains untouched
- **Phase 1:** New JSON files in `data/cost_*.json` (separate from `api_costs.json`)
- **Phase 2:** Audit trail integration uses cost_agent data; no changes to orchestrator internals
- **Phase 3:** Database migration is additive; JSON files remain as fallback

### Testing Strategy
| Phase | Unit Tests | Integration | Smoke Test | Manual Validation |
|-------|------------|-------------|------------|-------------------|
| 1 | ✅ Core logic | ✅ Mock Langfuse | ✅ 7 days | ✅ Cost accuracy |
| 2 | ✅ Reporters | ✅ End-to-end | ✅ 14 days | ✅ Alert triggers |
| 3 | ✅ Predictor | ✅ DB migration | ✅ 30 days | ✅ Forecast accuracy |

### Monitoring & Observability
| Phase | Logs | Metrics | Alerts |
|-------|------|---------|--------|
| 1 | Poller debug logs | Observations fetched, cost calculated | Langfuse unavailable (silent skip) |
| 2 | Reporter logs | Daily summaries sent, alerts triggered | Budget threshold exceeded |
| 3 | DB query logs | Prediction error (MAPE), rule matches | Anomalies detected |

### Team Roles & Responsibilities
- **Author/Reviewer:** Claude Sonnet (planning, code review, Q&A)
- **Executor:** Claude Haiku (implementation, testing, deployment)
- **Operator:** Main agent (deployment, monitoring, on-call)

---

## Timeline Estimate

```
┌─────────────────────────────────────────────────────────────────┐
│ Phase 1 (MVP)                  Phase 2           Phase 3        │
│ ├─ Weeks 1-2                   Weeks 3-5         Weeks 6-10+    │
│ ├─ Poller + calculator         Reporters +       Predictor +    │
│ ├─ Attribution                 Alerts            Optimization   │
│ ├─ Unit/integration tests      Dashboard         DB migration   │
│ └─ Smoke test (7 days)         Integration       Governance     │
└─────────────────────────────────────────────────────────────────┘
```

**Realistic Timeline:**
- **Phase 1:** 1-2 weeks (implementation + 7-day smoke test)
- **Phase 2:** 2-3 weeks (after Phase 1 stable)
- **Phase 3:** 4+ weeks (after Phase 2 + 30 days data history)
- **Total to Phase 3 completion:** ~3 months

---

## Success Metrics

### Phase 1 (MVP)
| Metric | Target | Method |
|--------|--------|--------|
| **Poller uptime** | >99% over 7 days | Monitor logs |
| **Cost accuracy** | ±1% vs. Langfuse UI | Manual spot-check |
| **Test coverage** | >80% for core/ | pytest coverage report |
| **No duplicates** | 0 duplicate cost records | Trace ID audit |
| **Backward compatible** | Legacy scripts unaffected | Run both old + new parallel |

### Phase 2 (Reporting)
| Metric | Target | Method |
|--------|--------|--------|
| **Report delivery** | 24h accuracy (23:59 UTC cutoff) | Time-stamp checks |
| **Alert latency** | <1 hour from threshold exceeded | Event logs |
| **Dashboard performance** | <2s page load | Browser timings |
| **User satisfaction** | Reports actionable + clear | Feedback survey |

### Phase 3 (Advanced)
| Metric | Target | Method |
|--------|--------|--------|
| **Forecast accuracy** | MAPE <10% | Compare vs. actuals |
| **Optimization hit rate** | >50% of recommendations adopted | User feedback |
| **Database query latency** | <100ms for historical queries | Query benchmarks |

---

## Risk Mitigation

### Phase 1
| Risk | Severity | Mitigation |
|------|----------|-----------|
| Langfuse API changes | Medium | Monitor Langfuse changelog; design poller to be version-agnostic |
| Missing user attribution | Medium | Fallback to "unknown_user"; alert on >10% unmapped |
| Cost calculation errors | High | Extensive unit tests; compare vs. Langfuse UI |
| State file corruption | Low | Atomic writes (write-to-temp, rename); validate JSON on load |

### Phase 2
| Risk | Severity | Mitigation |
|------|----------|-----------|
| Alert notification failures | Medium | Log failures; implement retry logic |
| Dashboard lag under load | Low | Materialized views; cache aggregates |
| User confusion (new reports) | Low | Clear documentation; example output |

### Phase 3
| Risk | Severity | Mitigation |
|------|----------|-----------|
| Forecast accuracy poor | Medium | Use conservative predictions; always include confidence interval |
| DB migration data loss | High | Extensive testing; dual-write phase; rollback procedure |
| Rules engine complexity | Medium | Declarative YAML config; unit tests per rule |

---

## Decision Log

### D1: Single Source of Truth
**Decision:** Langfuse traces are the single source of truth for cost calculation.  
**Rationale:** Langfuse captures actual model usage (tokens, latency, errors); better than inferring from side channels.  
**Alternative:** Query LLM provider APIs directly (OpenAI, Anthropic). → Rejected: too many API calls, rate limits.

### D2: Passive Observer
**Decision:** Cost agent does not inject into command flow; polls Langfuse asynchronously.  
**Rationale:** Decouples cost tracking from command latency; easier to debug + test.  
**Alternative:** Inline cost capture at LLM call sites. → Rejected: adds latency, couples concerns.

### D3: JSON for Phase 1 State
**Decision:** Use JSON files for cost state (not database) in Phase 1.  
**Rationale:** Simplicity, no external dependencies, easy to inspect/debug.  
**Migration:** Phase 3 will migrate to SQL for scalability + querying.

### D4: Pricing Tables in Code
**Decision:** Version pricing in code (not config database).  
**Rationale:** Immutable pricing history; easy to review in PR; no additional service.  
**Alternative:** Pull from pricing API. → Rejected: adds latency, complexity.

---

## References

- [Langfuse Python SDK](https://docs.langfuse.com/sdk/python)
- [Persgraph Tracing](../../../second_brain/tracing.py)
- [Existing Cost Tracking](../../../scripts/track_api_cost.py)
- [Orchestrator Architecture](../orchestrator/MVP_SUMMARY.md)

---

**Version:** 1.0  
**Author:** Subagent (Cost Agent MVP)  
**Status:** DRAFT  
**Last Updated:** 2026-06-19 22:47 UTC
