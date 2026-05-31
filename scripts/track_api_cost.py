#!/usr/bin/env python3
"""
API cost tracker — logs daily usage to data/api_costs.json.
Called by OpenClaw heartbeat; output is used for Telegram daily summary.

Usage: python scripts/track_api_cost.py --tokens-in 5000 --tokens-out 1200 --model claude-sonnet-4-6
"""

import argparse
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "api_costs.json"

# Approximate pricing per 1M tokens (update as needed)
PRICING = {
    "claude-sonnet-4-6":          {"input": 3.00,  "output": 15.00},
    "claude-3-5-haiku-20241022":  {"input": 0.80,  "output": 4.00},
    "claude-opus-4":              {"input": 15.00, "output": 75.00},
    "default":                    {"input": 3.00,  "output": 15.00},
}


def load() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"daily": {}, "total": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}}


def save(data: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def log_usage(tokens_in: int, tokens_out: int, model: str = "default") -> dict:
    pricing = PRICING.get(model, PRICING["default"])
    cost = (tokens_in / 1_000_000 * pricing["input"]) + (tokens_out / 1_000_000 * pricing["output"])

    today = date.today().isoformat()
    data = load()

    if today not in data["daily"]:
        data["daily"][today] = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0}

    data["daily"][today]["input_tokens"] += tokens_in
    data["daily"][today]["output_tokens"] += tokens_out
    data["daily"][today]["cost_usd"] = round(data["daily"][today]["cost_usd"] + cost, 6)
    data["daily"][today]["calls"] += 1

    data["total"]["input_tokens"] += tokens_in
    data["total"]["output_tokens"] += tokens_out
    data["total"]["cost_usd"] = round(data["total"]["cost_usd"] + cost, 6)

    save(data)
    return data["daily"][today]


def summary(days: int = 7) -> dict:
    data = load()
    today = date.today()
    result = {}
    for i in range(days):
        d = (today - __import__("datetime").timedelta(days=i)).isoformat()
        result[d] = data["daily"].get(d, {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0})
    return {
        "daily": result,
        "total": data.get("total", {}),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Log API usage and cost")
    subparsers = parser.add_subparsers(dest="command")

    log_parser = subparsers.add_parser("log", help="Log a usage event")
    log_parser.add_argument("--tokens-in",  type=int, required=True)
    log_parser.add_argument("--tokens-out", type=int, required=True)
    log_parser.add_argument("--model",      default="default")

    subparsers.add_parser("summary", help="Print 7-day summary")

    args = parser.parse_args()

    if args.command == "log":
        result = log_usage(args.tokens_in, args.tokens_out, args.model)
        print(json.dumps(result, indent=2))
    elif args.command == "summary":
        print(json.dumps(summary(), indent=2))
    else:
        print(json.dumps(summary(), indent=2))
