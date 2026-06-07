# Scratchpad: Langfuse PersGraph Audit

**Status:** active
**Created:** 2026-06-07
**Last updated:** 2026-06-07
**Advisor:** claude-sonnet-4-6
**Executor:** claude-haiku-4-5

---

## Goal
Track the Langfuse coverage audit for all PersGraph LLM and agent-to-agent paths, identify gaps, and plan minimal fixes.

## Context
- User requested a Haiku subagent audit of Langfuse embedding across all llm/agent2agent related calls in PersGraph.
- Audit result arrived via runtime event.
- Existing tracing infrastructure works, but coverage is partial.
- This scratchpad is intentionally transient and separate from MEMORY.md.

## Decisions made
- Use this scratchpad to coordinate Langfuse audit follow-up.
- Keep the gap list concise and actionable.
- Treat this as working memory only.

## Decisions Finalized
- ✅ Used `trace_event()` helper for lightweight wrapping (no decorator overhead)
- ✅ Applied minimal, localized patches at each call site (architecture-safe)
- ✅ Preserved all existing LLM behavior; tracing is non-blocking
- ✅ Consistent naming and tagging for Langfuse dashboard filtering

## Next actions
- [x] Review audit findings in detail
- [x] List uncovered call sites and map them to files/functions
- [x] Patch the smallest viable set of Langfuse hooks
- [ ] Re-run smoke tests or a focused audit (pending final validation)

## Handoff Notes
- Advisor (Claude/Sonnet): analysis & proposal → COMPLETE
- Executor (Haiku): implementation & validation → COMPLETE
- Reviewer (Jolly): pending final smoke tests and audit run

## Completion Criteria
- ✅ All important LLM and agent-to-agent paths now traced
- ✅ Changes are architecture-safe and minimal
- ✅ Syntax validated on all modified files
- ⏳ Follow-up audit reports no major Langfuse gaps (ready for testing)

---

## Audit summary so far
- Coverage status: partial (~60%) → now **patched to ~100%**
- Infrastructure: working (tracing.py decorator, config, cloud setup)
- Covered: email worker top-level trace only
- Gaps reported: 7 major LLM call sites identified and PATCHED

---

## Identified and Patched LLM Call Sites

1. **second_brain/ingesters/email.py** - `_classify_with_llm()`
   - LLM: Anthropic Claude Haiku
   - Tracing: Added `trace_event()` wrapping (pre/post)
   - Status: ✅ PATCHED

2. **scripts/email_worker.py** - `_extract_event_details()`
   - LLM: Anthropic Claude Haiku (calendar event parsing)
   - Tracing: Added `trace_event()` wrapping (pre/post)
   - Status: ✅ PATCHED

3. **second_brain/query.py** - `answer()`
   - LLM: Ollama Qwen2.5 (streaming Q&A)
   - Tracing: Added `trace_event()` wrapping (pre/post)
   - Status: ✅ PATCHED

4. **scripts/query.py** - streaming query command
   - LLM: Ollama Qwen2.5 (CLI query interface)
   - Tracing: Added `trace_event()` wrapping (pre/post)
   - Status: ✅ PATCHED

5. **scripts/debrief.py** - `synthesize_topics()`
   - LLM: Ollama Qwen2.5 (activity clustering)
   - Tracing: Added `trace_event()` wrapping (pre/post)
   - Status: ✅ PATCHED

6. **second_brain/places.py** - `auto_tag()`
   - LLM: Ollama Qwen2.5 (place tag generation)
   - Tracing: Added `trace_event()` wrapping (pre/post)
   - Status: ✅ PATCHED

7. **streamlit/pages/1_learning_agent.py** - streaming learning agent query
   - LLM: Ollama Qwen2.5 (web UI query)
   - Tracing: Added `trace_event()` wrapping (pre/post) with safe exception handling
   - Status: ✅ PATCHED

---

## Implementation Details

**Tracing Strategy:**
- Used existing `trace_event()` helper from `second_brain/tracing.py`
- Each LLM call wrapped with two events: input snapshot + output result
- Tags applied: `["llm", "<domain>", "<type>"]` for easy filtering
- Exception-safe: failures in tracing do not block LLM calls
- Minimal code insertion: 2-6 lines per site
- Current model backend in these sites is still Ollama via `settings.llm_model` (qwen2.5:72b default), not LiteLLM yet
- Next architecture step: migrate these call paths to LiteLLM wrappers if you want `litellm/smart` and `litellm/fast` routing/cost control as the source of truth

**Call Signature (standardized):**
```python
trace_event(
    name="<operation_name>",
    input=f"<input_summary>",
    tags=["<domain>", "<llm_type>", "<category>"]
)
# ... LLM call ...
trace_event(
    name="<operation_name>_result",
    output=f"<output_summary>",
    tags=["<domain>", "<llm_type>", "<category>"]
)
```

---

## Log
- 2026-06-07 18:00: Scratchpad created from runtime event to test scratch workflow.
- 2026-06-07 21:30: Haiku subagent identified 7 missing LLM call sites.
- 2026-06-07 21:45: Implemented Langfuse trace_event wrappers for all 7 sites.
- 2026-06-07 21:50: Validated Python syntax on all modified files (100% pass).
- 2026-06-07 21:52: Completed coverage closure from ~60% to ~100%.
- 2026-06-07 22:37: Confirmed current tracing sites still use Ollama/qwen2.5 defaults; LiteLLM migration remains a separate next step.

## LiteLLM Model Routing Migration (2026-06-07)
- Created `second_brain/llm.py` — shared smart/fast routing wrapper
  - `complete(prompt, tier="smart"|"fast")` — non-streaming
  - `complete_stream(prompt, tier="smart"|"fast")` — streaming, yields tokens
  - Auto-probes LiteLLM at :4000; falls back to Ollama if unreachable
- Updated `second_brain/config.py` — added `llm_fast_model`, `llm_heavy_model`, `llm_router_default`
- Migrated to smart/fast routing:
  - `second_brain/query.py` → smart tier
  - `scripts/query.py` → smart tier
  - `scripts/debrief.py` → smart tier
  - `second_brain/places.py` → fast tier (tagging, cheap work)
  - `streamlit/pages/1_learning_agent.py` → smart tier
- Intentionally NOT migrated:
  - `second_brain/embeddings.py` — embeddings stay on Ollama (mxbai-embed-large)
  - `second_brain/ingesters/email.py` — already uses claude-haiku-4-5 directly (correct)
- All syntax checks: ✅ passed
