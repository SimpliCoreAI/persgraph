#!/usr/bin/env python3
"""
Evaluate recorded responses with an LLM-as-judge and close the learning loop.

This closes the response-learning loop end to end:
- sample "response" events from the learning DB
- judge each response (LLM-as-judge, with safe fallback)
- PERSIST each judge result back into the learning DB as an `outcome`
  (outcome_type="judged") linked to the originating response event
- return structured JSON for later analysis

The persisted outcomes are then picked up by `second_brain.learning_learner`
(skills/preferences inference), completing the loop:

    response event -> judge -> outcome -> learner -> skills/preferences

Usage:
    python3 scripts/eval_responses.py --limit 10
    python3 scripts/eval_responses.py --response-id <uuid>
    python3 scripts/eval_responses.py --limit 20 --no-persist   # dry run
    python3 scripts/eval_responses.py --limit 20 --reeval       # re-judge already-judged
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict, field
from typing import Any

from second_brain import learning_db


JUDGE_PROMPT = """You are an exacting evaluator of assistant responses.
Score the response from 1-5 on:
- correctness
- completeness
- clarity
- groundedness
- usefulness
- tone
- tool_fidelity

Return JSON only with keys:
{
  "overall_score": number,
  "correctness": number,
  "completeness": number,
  "clarity": number,
  "groundedness": number,
  "usefulness": number,
  "tone": number,
  "tool_fidelity": number,
  "critique": string,
  "improvements": [string, ...]
}

Prompt:
{prompt}

Response:
{response}
"""

# outcome_type used when a judge result is persisted back into learning_db.
JUDGE_OUTCOME_TYPE = "judged"


@dataclass
class EvalRow:
    event_id: str
    prompt: str
    response: str
    judge: dict[str, Any]
    outcome_id: str = ""
    persisted: bool = False
    skipped_reason: str = ""


def _load_recent_response_events(limit: int) -> list[dict[str, Any]]:
    events = learning_db.get_event_summary(limit=limit)
    rows: list[dict[str, Any]] = []
    for ev in events:
        meta = ev.get("metadata") or {}
        if ev.get("event_type") != "response":
            continue
        rows.append({
            "event_id": ev["id"],
            "prompt": meta.get("command", "unknown command"),
            "response": meta.get("response_text", ""),
            "metadata": meta,
        })
    return rows


def _already_judged_event_ids(limit: int = 5000) -> set[str]:
    """Return set of event_ids that already have a `judged` outcome.

    Used to make the eval loop idempotent so a cron run does not
    re-judge the same response repeatedly.
    """
    judged: set[str] = set()
    try:
        outcomes = learning_db.get_outcome_summary(limit=limit)
    except Exception:
        return judged
    for o in outcomes:
        if o.get("outcome_type") == JUDGE_OUTCOME_TYPE:
            # get_outcome_summary does not return event_id, so fall back to
            # the since-based query which does.
            pass
    # get_outcome_summary intentionally omits event_id; use get_outcomes_since
    # (returns event_id) over all history.
    try:
        all_outcomes = learning_db.get_outcomes_since("1970-01-01T00:00:00", limit=limit)
    except Exception:
        all_outcomes = []
    for o in all_outcomes:
        if o.get("outcome_type") == JUDGE_OUTCOME_TYPE and o.get("event_id"):
            judged.add(o["event_id"])
    return judged


def _judge_with_llm(prompt: str, response: str) -> dict[str, Any]:
    try:
        from second_brain.llm import complete
        raw = complete(JUDGE_PROMPT.format(prompt=prompt, response=response), tier="smart", max_tokens=800)
        return json.loads(raw)
    except Exception as e:
        return {
            "overall_score": 0,
            "correctness": 0,
            "completeness": 0,
            "clarity": 0,
            "groundedness": 0,
            "usefulness": 0,
            "tone": 0,
            "tool_fidelity": 0,
            "critique": f"Judge unavailable: {e}",
            "improvements": [],
        }


def _persist_judge_outcome(event_id: str, prompt: str, judge: dict[str, Any]) -> str:
    """Persist a judge result back into learning_db as an outcome.

    The outcome links to the originating response event and carries the
    full structured judge result in metadata so the learner can later
    consume per-dimension scores.
    """
    overall = judge.get("overall_score", 0) or 0
    try:
        overall_num = float(overall)
    except (TypeError, ValueError):
        overall_num = 0.0

    outcome_id = learning_db.record_outcome(
        event_id=event_id,
        outcome_type=JUDGE_OUTCOME_TYPE,
        suggestion_title=(prompt or "")[:120],
        suggestion_category="response",
        feedback=str(judge.get("critique", ""))[:500],
        metadata={
            "source": "eval_responses",
            "overall_score": overall_num,
            "scores": {
                k: judge.get(k)
                for k in (
                    "correctness", "completeness", "clarity",
                    "groundedness", "usefulness", "tone", "tool_fidelity",
                )
            },
            "improvements": judge.get("improvements", []),
        },
    )
    return outcome_id


def evaluate(
    limit: int = 10,
    response_id: str = "",
    persist: bool = True,
    reeval: bool = False,
) -> list[EvalRow]:
    """Judge recent (or one specific) response event(s) and optionally persist.

    Returns a list of EvalRow with judge results and persistence status.
    Importable so the /eval command and tests can reuse the same path.
    """
    if response_id:
        events = learning_db.get_event_summary(limit=500)
        target = next((e for e in events if e["id"] == response_id), None)
        if not target:
            return []
        meta = target.get("metadata", {}) or {}
        rows = [{
            "event_id": target["id"],
            "prompt": meta.get("command", "unknown command"),
            "response": meta.get("response_text", ""),
            "metadata": meta,
        }]
    else:
        rows = _load_recent_response_events(limit)

    judged_ids: set[str] = set() if reeval else _already_judged_event_ids()

    results: list[EvalRow] = []
    for row in rows:
        eid = row["event_id"]
        if not reeval and eid in judged_ids:
            results.append(EvalRow(
                eid, row["prompt"], row["response"], judge={},
                persisted=False, skipped_reason="already_judged",
            ))
            continue

        judge = _judge_with_llm(row["prompt"], row["response"])
        eval_row = EvalRow(eid, row["prompt"], row["response"], judge)

        if persist:
            outcome_id = _persist_judge_outcome(eid, row["prompt"], judge)
            eval_row.outcome_id = outcome_id
            eval_row.persisted = bool(outcome_id)

        results.append(eval_row)

    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--response-id", type=str, default="")
    parser.add_argument("--no-persist", action="store_true",
                        help="Dry run: judge but do not write outcomes")
    parser.add_argument("--reeval", action="store_true",
                        help="Re-judge events even if already judged")
    args = parser.parse_args()

    results = evaluate(
        limit=args.limit,
        response_id=args.response_id,
        persist=not args.no_persist,
        reeval=args.reeval,
    )

    if args.response_id and not results:
        print(json.dumps({"error": "response id not found"}, indent=2))
        return 1

    print(json.dumps([asdict(r) for r in results], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
