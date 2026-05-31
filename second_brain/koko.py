"""
Koko Finance MCP client — credit card intelligence.
https://kokofinance.net/mcp/

No API key required. Covers 100+ US cards.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx

KOKO_URL = "https://kokofinance.net/mcp/"
TIMEOUT = httpx.Timeout(timeout=30.0, connect=10.0)

# Jolly's card portfolio — update with real Koko card IDs once confirmed
DEFAULT_PORTFOLIO = [
    "amex-gold",
    "amex-platinum",
    "chase-sapphire-preferred",
    "citi-double-cash",
    "discover-it-cash-back",
    "robinhood-gold-card",
]


def _call(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call a Koko MCP tool."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool,
            "arguments": arguments,
        },
    }
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.post(KOKO_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

    if "error" in data:
        raise Exception(f"Koko error: {data['error']}")

    # Extract text content from MCP response
    result = data.get("result", {})
    content = result.get("content", [])
    if content and isinstance(content, list):
        return {"raw": result, "text": content[0].get("text", json.dumps(result))}
    return {"raw": result, "text": json.dumps(result)}


def which_card_at_merchant(
    merchant: str,
    portfolio: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Best card from portfolio for a specific merchant."""
    return _call("which_card_at_merchant", {
        "merchant": merchant,
        "portfolio": portfolio or DEFAULT_PORTFOLIO,
    })


def recommend_for_category(
    category: str,
    portfolio: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Best card for a spending category (dining, travel, groceries, etc.)."""
    return _call("recommend_card_for_category", {
        "category": category,
        "portfolio": portfolio or DEFAULT_PORTFOLIO,
    })


def optimize_portfolio(
    portfolio: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Portfolio health score + keep/cancel verdicts."""
    return _call("optimize_portfolio", {
        "portfolio": portfolio or DEFAULT_PORTFOLIO,
    })


def compare_cards(cards: list[str]) -> dict[str, Any]:
    """Side-by-side comparison of 2-3 cards."""
    return _call("compare_cards", {"cards": cards})


def check_merchant_benefits(
    merchant: str,
    portfolio: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Check if any card has statement credits at a merchant."""
    return _call("check_merchant_benefits", {
        "merchant": merchant,
        "portfolio": portfolio or DEFAULT_PORTFOLIO,
    })


def get_card_details(card: str) -> dict[str, Any]:
    """Full details for a specific card."""
    return _call("get_card_details", {"card": card})


def search_cards(query: str, max_annual_fee: Optional[int] = None) -> dict[str, Any]:
    """Search 100+ US credit cards."""
    args: dict[str, Any] = {"query": query}
    if max_annual_fee is not None:
        args["max_annual_fee"] = max_annual_fee
    return _call("search_credit_cards", args)
