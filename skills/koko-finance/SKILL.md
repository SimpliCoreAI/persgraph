# Koko Finance — Credit Card Intelligence

Use this skill when Jolly asks about:
- Which credit card to use for a purchase or merchant
- Comparing credit cards
- Optimizing credit card portfolio
- Checking card benefits or credits at a merchant
- Annual fee renewal decisions

## API

Base URL: `https://kokofinance.net/mcp/`
No API key required.

## Key Tools (call via HTTP POST)

### which_card_at_merchant
Best card from portfolio for a specific merchant.
```json
{"method": "tools/call", "params": {"name": "which_card_at_merchant", "arguments": {"merchant": "Costco", "portfolio": ["amex_gold", "chase_sapphire_preferred", "citi_double_cash", "discover_it", "robinhood_gold"]}}}
```

### recommend_card_for_category
Best card for a spending category.
```json
{"method": "tools/call", "params": {"name": "recommend_card_for_category", "arguments": {"category": "dining", "portfolio": ["amex_gold", "chase_sapphire_preferred"]}}}
```

### optimize_portfolio
Portfolio health score + keep/cancel verdicts.
```json
{"method": "tools/call", "params": {"name": "optimize_portfolio", "arguments": {"portfolio": ["amex_gold", "chase_sapphire_preferred", "citi_double_cash", "discover_it", "robinhood_gold"]}}}
```

### compare_cards
Side-by-side comparison of 2-3 cards.
```json
{"method": "tools/call", "params": {"name": "compare_cards", "arguments": {"cards": ["amex_gold", "chase_sapphire_preferred"]}}}
```

### check_merchant_benefits
Check if any card has credits at a merchant.
```json
{"method": "tools/call", "params": {"name": "check_merchant_benefits", "arguments": {"merchant": "Saks Fifth Avenue", "portfolio": ["amex_platinum"]}}}
```

### get_card_details
Full details for a specific card.
```json
{"method": "tools/call", "params": {"name": "get_card_details", "arguments": {"card": "amex_gold"}}}
```

## Jolly's Cards
- amex_1 (Amex — update with real card ID)
- amex_2 (Amex — update with real card ID)
- chase_1 (Chase — update with real card ID)
- citi_1 (Citi — update with real card ID)
- discover_it
- robinhood_gold

## How to Use

1. User asks "which card should I use at Whole Foods?"
2. Call `which_card_at_merchant` with merchant="Whole Foods" and Jolly's portfolio
3. Parse response and explain recommendation clearly
4. Always mention the reward rate and reason

## Notes
- All tools are fast (<100ms for most)
- No personal financial data sent — only card names and merchant names
- If Koko doesn't recognize a card name, try variations (e.g. "amex-gold", "american-express-gold")
