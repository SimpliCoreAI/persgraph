#!/usr/bin/env python3
"""
Evaluate recorded responses with an LLM-as-judge.

This is a minimal offline eval helper:
- sample response events from the learning DB
- optionally judge one response by ID
- return structured JSON for later analysis

Usage:
    python3 scripts/eval_responses.py --limit 10
    python3 scripts/eval_responses.py --response-id <uuid>
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
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


@dataclass
class EvalRow:
    event_id: str
    prompt: str
    response: str
    judge: dict[str, Any]


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--response-id", type=str, default="")
    args = parser.parse_args()

    if args.response_id:
        events = learning_db.get_event_summary(limit=500)
        target = next((e for e in events if e["id"] == args.response_id), None)
        if not target:
            print(json.dumps({"error": "response id not found"}, indent=2))
            return 1
        rows = [{
            "event_id": target["id"],
            "prompt": target.get("metadata", {}).get("command", "unknown command"),
            "response": target.get("metadata", {}).get("response_text", ""),
            "metadata": target.get("metadata", {}),
        }]
    else:
        rows = _load_recent_response_events(args.limit)

    results = []
    for row in rows:
        judge = _judge_with_llm(row["prompt"], row["response"])
        results.append(EvalRow(row["event_id"], row["prompt"], row["response"], judge))

    print(json.dumps([asdict(r) for r in results], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
