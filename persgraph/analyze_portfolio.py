#!/usr/bin/env python3
"""
Portfolio & Investment Analysis
Generates: financial_report_portfolio.html
"""
import argparse
import csv, re, json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# ── Paths ───────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent
DATA_2025 = BASE_DIR / "data" / "transactions_2025.csv"
DATA_2026 = BASE_DIR / "data" / "transactions_2026.csv"
OUT_FILE  = BASE_DIR / "financial_report_portfolio.html"  # default; overridden by --year

# ── CLI Args ─────────────────────────────────────────────────────
_parser = argparse.ArgumentParser(description="Portfolio Analysis")
_parser.add_argument("--year", type=int, choices=[2025, 2026], default=None,
                     help="Filter to a specific year. Default: combined view.")
_args = _parser.parse_args()
year_filter = _args.year

if year_filter == 2025:
    OUT_FILE   = BASE_DIR / "financial_report_portfolio_2025.html"
    PAGE_TITLE = "\U0001f4bc Portfolio \u2014 2025 Full Year"
    SUBTITLE   = "Securities Trades \u00b7 Retirement Contributions \u00b7 Investment Income \u2014 2025 Full Year"
    YEAR_LABEL = "2025 Full Year"
elif year_filter == 2026:
    OUT_FILE   = BASE_DIR / "financial_report_portfolio_2026.html"
    PAGE_TITLE = "\U0001f4bc Portfolio \u2014 2026 YTD"
    SUBTITLE   = "Securities Trades \u00b7 Retirement Contributions \u00b7 Investment Income \u2014 2026 YTD"
    YEAR_LABEL = "2026 YTD"
else:
    PAGE_TITLE = "\U0001f4bc Portfolio & Investment Activity"
    SUBTITLE   = "Securities Trades \u00b7 Retirement Contributions \u00b7 Investment Income \u2014 2025\u20132026 YTD"
    YEAR_LABEL = "Both years combined"

# ── Theme ────────────────────────────────────────────────────────
BG      = "#0f1117"
CARD    = "#1a1d27"
ACCENT  = "#6c8ef5"
TEXT    = "#e0e4f0"
MUTED   = "#888"
BORDER  = "#2a2d3a"
GREEN   = "#4ecb71"
RED     = "#e05c5c"
AMBER   = "#f5a623"
PURPLE  = "#b47ef5"
CYAN    = "#4ecbcb"

# ── Account grouping ─────────────────────────────────────────────
def account_group(acct):
    a = acct.lower()
    if any(x in a for x in ["robinhood"]):
        return "Robinhood"
    if any(x in a for x in ["complete", "securities - ending"]):
        return "Morgan Stanley"
    if any(x in a for x in ["brokeragelink", "rollover ira"]):
        return "Fidelity"
    if any(x in a for x in ["workday", "visa 401k", "401(k)"]):
        return "401(k)"
    if "health savings" in a:
        return "HSA"
    return "Other"

# ── Ticker extraction ─────────────────────────────────────────────
# Words that are NOT real tickers
STOP_WORDS = {
    "INC", "COM", "CORP", "LTD", "LLC", "CL", "A", "B", "C",
    "TR", "SER", "UNIT", "ETF", "FUND", "GROUP", "CO", "PLC",
    "1", "2", "NEW", "OLD", "CLASS", "THE", "AND", "OF", "IN",
    "HLDGS", "HLDG", "HOLDINGS", "HOLDING", "TECHNOLOGIES",
    "TECNOLOGIES", "COMMUNICATIONS", "CORPORATION", "COMPANY",
    "SHARES", "ADR", "ADS", "PREFERRED", "PREF", "NOTE", "NOTES",
    "BANK", "FINANCIAL", "SERVICES", "MANAGEMENT",
}

def best_word(name):
    """Pick best ticker-like word from a company name string."""
    words = [w.upper() for w in name.split() if w.strip()]
    if not words:
        return None
    # First non-stop word (first = most unique part of company name)
    for w in words:
        if w not in STOP_WORDS and re.match(r'^[A-Za-z]{2,12}$', w):
            return w[:6].upper()
    return words[0][:6].upper() if words else None

def extract_ticker(desc):
    d = desc.strip()
    # "Cash Dividend Of $X.XX From TICKER"  — explicit ticker after From
    m = re.search(r"\bFrom\s+([A-Za-z]{1,6})\s*$", d, re.I)
    if m:
        t = m.group(1).upper()
        if t not in STOP_WORDS:
            return t
    # "Call TICKER ..." or "Put TICKER ..."
    m = re.match(r"(?:Call|Put)\s+([A-Za-z]{1,6})\b", d, re.I)
    if m:
        t = m.group(1).upper()
        if t not in STOP_WORDS:
            return t
    # "Call (TICKER) ..." Fidelity style
    m = re.match(r"(?:Call|Put)\s+\(([A-Za-z]{1,6})\)", d, re.I)
    if m:
        return m.group(1).upper()
    # "Buy X shares of NAME for..."
    m = re.match(r"Buy\s+[\d.xx]+\s+Shares?\s+Of\s+(.+?)\s+For\b", d, re.I)
    if m:
        return best_word(m.group(1).strip())
    # "Sell X shares of NAME for..."
    m = re.match(r"Sell\s+[\d.xx]+\s+Shares?\s+Of\s+(.+?)\s+For\b", d, re.I)
    if m:
        return best_word(m.group(1).strip())
    # "NAME Unsolicited Trade"
    m = re.match(r"^([A-Za-z\s]+?)\s+Unsolicited Trade\b", d, re.I)
    if m:
        return best_word(m.group(1).strip())
    # "NAME Dividend Reinvestment"
    m = re.match(r"^([A-Za-z\s]+?)\s+Dividend Reinvestment\b", d, re.I)
    if m:
        return best_word(m.group(1).strip())
    # "NAME - Dividend Received ..."
    m = re.match(r"^(.+?)\s+-\s+Dividend Received\b", d, re.I)
    if m:
        return best_word(m.group(1).strip())
    # "NAME - Reinvestment ..."
    m = re.match(r"^(.+?)\s+-\s+Reinvestment\b", d, re.I)
    if m:
        return best_word(m.group(1).strip())
    return None

def is_option(desc):
    d = desc.strip().lower()
    return d.startswith("call ") or d.startswith("put ") or "you bought" in d or "you sold" in d

# ── Load data ─────────────────────────────────────────────────────
def load_csv(path, year):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                amt = float(row["Amount"])
            except (ValueError, KeyError):
                amt = 0.0
            rows.append({
                "date":     row.get("Date", "").strip(),
                "account":  row.get("Account", "").strip(),
                "desc":     row.get("Description", "").strip(),
                "category": row.get("Category", "").strip(),
                "amount":   amt,
                "year":     year,
            })
    return rows

if year_filter == 2025:
    rows_2025 = load_csv(DATA_2025, 2025)
    rows_2026 = []
elif year_filter == 2026:
    rows_2025 = []
    rows_2026 = load_csv(DATA_2026, 2026)
else:
    rows_2025 = load_csv(DATA_2025, 2025)
    rows_2026 = load_csv(DATA_2026, 2026)
all_rows = rows_2025 + rows_2026

# ── Filter by investment categories ──────────────────────────────
def get_month(row):
    try:
        dt = datetime.strptime(row["date"], "%Y-%m-%d")
        return f"{dt.year}-{dt.month:02d}"
    except Exception:
        return None

securities   = [r for r in all_rows if r["category"] == "Securities Trades"]
ret_contribs = [r for r in all_rows if r["category"] == "Retirement Contributions"]
inv_income   = [r for r in all_rows if r["category"] == "Investment Income"]

# ── Chart 1: Monthly Net Investment Activity ──────────────────────
# buys = amount < 0 in Securities Trades; sells = amount > 0
monthly_buys_sells = defaultdict(lambda: {"buy": 0.0, "sell": 0.0})
for r in securities:
    m = get_month(r)
    if not m:
        continue
    if r["amount"] < 0:
        monthly_buys_sells[m]["buy"] += abs(r["amount"])
    elif r["amount"] > 0:
        monthly_buys_sells[m]["sell"] += r["amount"]

# Build full month labels for both years
months_2025 = [f"2025-{mm:02d}" for mm in range(1, 13)]
months_2026 = [f"2026-{mm:02d}" for mm in range(1, 13)]
if year_filter == 2025:
    all_months = months_2025
elif year_filter == 2026:
    all_months = months_2026
else:
    all_months = sorted(set(monthly_buys_sells.keys()) | set(months_2025) | set(months_2026))

def fmt_month(m):
    dt = datetime.strptime(m, "%Y-%m")
    return dt.strftime("%b %y")

chart1_labels = [fmt_month(m) for m in all_months]
chart1_buys_2025  = [round(monthly_buys_sells.get(m, {}).get("buy", 0), 2)  for m in months_2025]
chart1_sells_2025 = [round(monthly_buys_sells.get(m, {}).get("sell", 0), 2) for m in months_2025]
chart1_buys_2026  = [round(monthly_buys_sells.get(m, {}).get("buy", 0), 2)  for m in months_2026]
chart1_sells_2026 = [round(monthly_buys_sells.get(m, {}).get("sell", 0), 2) for m in months_2026]
chart1_net_2025   = [round(chart1_sells_2025[i] - chart1_buys_2025[i], 2) for i in range(12)]
chart1_net_2026   = [round(chart1_sells_2026[i] - chart1_buys_2026[i], 2) for i in range(12)]

# ── Chart 2: Investment Income by Month ──────────────────────────
def classify_income(desc):
    d = desc.lower()
    if "dividend" in d or "cash div" in d:
        return "Dividends"
    if "cd" in d or "certificate" in d or "transfer interest" in d:
        return "CD Interest"
    if "bond" in d:
        return "Bond Interest"
    return "Other"

monthly_income = defaultdict(lambda: defaultdict(float))
for r in inv_income:
    m = get_month(r)
    if not m:
        continue
    cat = classify_income(r["desc"])
    monthly_income[m][cat] += r["amount"]

chart2_labels = [fmt_month(m) for m in all_months]
income_types  = ["Dividends", "CD Interest", "Bond Interest", "Other"]
chart2_data   = {ic: [round(monthly_income.get(m, {}).get(ic, 0), 2) for m in all_months] for ic in income_types}

# ── Chart 3: Dividend Income by Ticker ───────────────────────────
ticker_divs = defaultdict(float)
for r in inv_income:
    if "dividend" in r["desc"].lower() or "cash div" in r["desc"].lower():
        t = extract_ticker(r["desc"])
        if t and len(t) <= 6:
            ticker_divs[t] += r["amount"]
top_div_tickers = sorted(ticker_divs.items(), key=lambda x: -x[1])[:15]
chart3_labels = [t for t, _ in top_div_tickers]
chart3_vals   = [round(v, 2) for _, v in top_div_tickers]

# ── Chart 4: Retirement Contributions by Month ────────────────────
monthly_ret = defaultdict(lambda: {"401k": 0.0, "IRA": 0.0, "HSA": 0.0})
for r in ret_contribs:
    m = get_month(r)
    if not m:
        continue
    ag = account_group(r["account"])
    if ag == "401(k)":
        monthly_ret[m]["401k"] += r["amount"]
    elif "ira" in r["account"].lower() or "rollover" in r["account"].lower():
        monthly_ret[m]["IRA"] += r["amount"]
    elif ag == "HSA" or "health savings" in r["account"].lower():
        monthly_ret[m]["HSA"] += r["amount"]

chart4_labels  = [fmt_month(m) for m in all_months]
chart4_401k    = [round(monthly_ret.get(m, {}).get("401k", 0), 2) for m in all_months]
chart4_ira     = [round(monthly_ret.get(m, {}).get("IRA", 0), 2)  for m in all_months]
chart4_hsa     = [round(monthly_ret.get(m, {}).get("HSA", 0), 2)  for m in all_months]

total_ret_2025 = sum(r["amount"] for r in ret_contribs if r["year"] == 2025)
total_ret_2026 = sum(r["amount"] for r in ret_contribs if r["year"] == 2026)

# ── Chart 5: Top 20 Most Traded Tickers (Treemap) ─────────────────
ticker_vol = defaultdict(float)
for r in securities:
    t = extract_ticker(r["desc"])
    if t and len(t) <= 6:
        ticker_vol[t] += abs(r["amount"])
top_traded = sorted(ticker_vol.items(), key=lambda x: -x[1])[:20]
chart5_labels = [t for t, _ in top_traded]
chart5_vals   = [round(v, 2) for _, v in top_traded]
chart5_parents = [""] * len(chart5_labels)

# ── Chart 6: Options Activity ─────────────────────────────────────
monthly_opts = defaultdict(lambda: {"calls_buy": 0.0, "calls_sell": 0.0, "puts_buy": 0.0, "puts_sell": 0.0})
for r in securities:
    d = r["desc"].strip().lower()
    m = get_month(r)
    if not m:
        continue
    is_call = d.startswith("call ")
    is_put  = d.startswith("put ")
    # Also Fidelity style: "Call (TICKER)..." with "you bought/sold"
    if not is_call and not is_put:
        if re.search(r"call\s*\(", d):
            is_call = True
        elif re.search(r"put\s*\(", d):
            is_put = True
    if not (is_call or is_put):
        continue
    is_buy  = r["amount"] < 0
    is_sell = r["amount"] > 0
    if is_call:
        if is_buy:
            monthly_opts[m]["calls_buy"]  += abs(r["amount"])
        else:
            monthly_opts[m]["calls_sell"] += r["amount"]
    elif is_put:
        if is_buy:
            monthly_opts[m]["puts_buy"]   += abs(r["amount"])
        else:
            monthly_opts[m]["puts_sell"]  += r["amount"]

chart6_labels     = [fmt_month(m) for m in all_months]
chart6_calls_buy  = [round(monthly_opts.get(m, {}).get("calls_buy",  0), 2) for m in all_months]
chart6_calls_sell = [round(monthly_opts.get(m, {}).get("calls_sell", 0), 2) for m in all_months]
chart6_puts_buy   = [round(monthly_opts.get(m, {}).get("puts_buy",   0), 2) for m in all_months]
chart6_puts_sell  = [round(monthly_opts.get(m, {}).get("puts_sell",  0), 2) for m in all_months]

total_options_activity = sum(
    monthly_opts[m]["calls_buy"] + monthly_opts[m]["calls_sell"] +
    monthly_opts[m]["puts_buy"]  + monthly_opts[m]["puts_sell"]
    for m in monthly_opts
)

# ── Chart 7: Account Activity Breakdown (Donut) ───────────────────
account_vol = defaultdict(float)
for r in securities:
    ag = account_group(r["account"])
    account_vol[ag] += abs(r["amount"])
chart7_labels = list(account_vol.keys())
chart7_vals   = [round(v, 2) for v in account_vol.values()]

# ── Chart 8: Monthly Buy vs Sell Ratio ───────────────────────────
chart8_labels = [fmt_month(m) for m in all_months]
chart8_ratio  = []
for m in all_months:
    b = monthly_buys_sells[m]["buy"]
    s = monthly_buys_sells[m]["sell"]
    if b > 0:
        chart8_ratio.append(round(s / b, 3))
    else:
        chart8_ratio.append(None)

# ── Chart 9: Cumulative Investment Income ────────────────────────
cum_income_2025 = []
cum_income_2026 = []
running_2025 = 0.0
running_2026 = 0.0
for m in months_2025:
    running_2025 += sum(monthly_income.get(m, {}).values())
    cum_income_2025.append(round(running_2025, 2))
for m in months_2026:
    running_2026 += sum(monthly_income.get(m, {}).values())
    cum_income_2026.append(round(running_2026, 2))
chart9_labels_2025 = [fmt_month(m) for m in months_2025]
chart9_labels_2026 = [fmt_month(m) for m in months_2026]

# ── Chart 10: Top Buys vs Top Sells ──────────────────────────────
ticker_buys  = defaultdict(float)
ticker_sells = defaultdict(float)
for r in securities:
    t = extract_ticker(r["desc"])
    if t and len(t) <= 6:
        if r["amount"] < 0:
            ticker_buys[t]  += abs(r["amount"])
        elif r["amount"] > 0:
            ticker_sells[t] += r["amount"]

top10_buys  = sorted(ticker_buys.items(),  key=lambda x: -x[1])[:10]
top10_sells = sorted(ticker_sells.items(), key=lambda x: -x[1])[:10]
chart10_buy_labels  = [t for t, _ in top10_buys]
chart10_buy_vals    = [round(v, 2) for _, v in top10_buys]
chart10_sell_labels = [t for t, _ in top10_sells]
chart10_sell_vals   = [round(v, 2) for _, v in top10_sells]

# ── Stat Cards ───────────────────────────────────────────────────
total_buy_vol   = sum(abs(r["amount"]) for r in securities if r["amount"] < 0)
total_sell_vol  = sum(r["amount"] for r in securities if r["amount"] > 0)
net_activity    = total_sell_vol - total_buy_vol
total_dividends = sum(r["amount"] for r in inv_income if "dividend" in r["desc"].lower() or "cash div" in r["desc"].lower())
total_ret_all   = sum(r["amount"] for r in ret_contribs)
most_traded     = max(ticker_vol.items(), key=lambda x: x[1])[0] if ticker_vol else "N/A"
hsa_contribs    = sum(r["amount"] for r in ret_contribs if "health savings" in r["account"].lower() or account_group(r["account"]) == "HSA")

# 401k and IRA breakdown for recommendations
total_401k_2025 = sum(r["amount"] for r in ret_contribs if r["year"] == 2025 and account_group(r["account"]) == "401(k)")
total_401k_2026 = sum(r["amount"] for r in ret_contribs if r["year"] == 2026 and account_group(r["account"]) == "401(k)")
total_ira_2025  = sum(r["amount"] for r in ret_contribs if r["year"] == 2025 and ("ira" in r["account"].lower() or "rollover" in r["account"].lower()))
total_ira_2026  = sum(r["amount"] for r in ret_contribs if r["year"] == 2026 and ("ira" in r["account"].lower() or "rollover" in r["account"].lower()))

# Concentration risk: top ticker as % of total volume
top_ticker_vol    = top_traded[0][1] if top_traded else 0
top_ticker_pct    = (top_ticker_vol / total_buy_vol * 100) if total_buy_vol > 0 else 0
conc_ticker       = top_traded[0][0] if top_traded else "N/A"

def fmt_currency(v):
    return f"${v:,.0f}"

# ── Recommendations ──────────────────────────────────────────────
IRS_401K_LIMIT_2025 = 23500
IRS_IRA_LIMIT_2025  = 7000

recs = []
# 1. Diversification
if len(top_traded) >= 5:
    top5_vol = sum(v for _, v in top_traded[:5])
    top5_pct = (top5_vol / (total_buy_vol + total_sell_vol) * 100) if (total_buy_vol + total_sell_vol) > 0 else 0
    recs.append({
        "icon": "📊",
        "title": "Diversification",
        "body": f"Your top 5 traded tickers ({', '.join(t for t, _ in top_traded[:5])}) account for "
                f"{top5_pct:.1f}% of total trading volume. "
                f"{'Consider broadening exposure to reduce single-name concentration risk.' if top5_pct > 60 else 'Portfolio appears reasonably diversified across multiple positions.'}"
    })

# 2. Retirement contribution pace
pct_401k_2025 = (total_401k_2025 / IRS_401K_LIMIT_2025 * 100)
pct_401k_2026_annualized = (total_401k_2026 / IRS_401K_LIMIT_2025 * 100)
recs.append({
    "icon": "🏦",
    "title": "Retirement Contribution Pace",
    "body": f"2025 401(k) contributions: {fmt_currency(total_401k_2025)} ({pct_401k_2025:.1f}% of ${IRS_401K_LIMIT_2025:,} IRS limit). "
            f"2026 YTD: {fmt_currency(total_401k_2026)}. "
            f"{'✅ On track for max contribution.' if pct_401k_2025 >= 95 else '⚠️ Consider increasing contribution rate to maximize tax-advantaged savings.'}"
            f" IRA contributions 2025: {fmt_currency(total_ira_2025)} (limit: ${IRS_IRA_LIMIT_2025:,})."
})

# 3. Options risk
if total_options_activity > 0:
    opts_pct = (total_options_activity / total_buy_vol * 100) if total_buy_vol > 0 else 0
    recs.append({
        "icon": "⚠️",
        "title": "Options Activity Risk",
        "body": f"Options trades total {fmt_currency(total_options_activity)} across the period "
                f"({opts_pct:.1f}% of total buy volume). "
                f"{'Options carry elevated risk including total loss of premium. Ensure positions are sized appropriately relative to portfolio.' if opts_pct > 10 else 'Options activity is modest relative to overall portfolio — manageable risk level.'}"
    })

# 4. Dividend reinvestment
drip_count = sum(1 for r in securities if "reinvestment" in r["desc"].lower() or "dividend reinvest" in r["desc"].lower())
recs.append({
    "icon": "🔄",
    "title": "Dividend Reinvestment (DRIP)",
    "body": f"Detected {drip_count} dividend reinvestment transactions. "
            f"Total dividends received: {fmt_currency(total_dividends)}. "
            "DRIP accelerates compounding over time — great for long-term growth positions. "
            "Review whether all dividend-paying holdings should reinvest or pay cash depending on your income needs."
})

# 5. Concentration risk
if top_ticker_pct > 20:
    recs.append({
        "icon": "🔴",
        "title": "Concentration Risk Detected",
        "body": f"{conc_ticker} accounts for {top_ticker_pct:.1f}% of total securities trade volume. "
                f"Single-stock concentration above 20% significantly increases portfolio volatility. "
                f"Consider trimming to reduce idiosyncratic risk."
    })
else:
    recs.append({
        "icon": "✅",
        "title": "Concentration Risk Within Bounds",
        "body": f"Top traded ticker ({conc_ticker}) accounts for {top_ticker_pct:.1f}% of total trade volume — "
                f"within acceptable limits. Continue monitoring as new positions are added."
    })

# 6. Investment income growth
total_income_2025 = cum_income_2025[-1] if cum_income_2025 else 0
total_income_2026 = cum_income_2026[-1] if cum_income_2026 else 0
recs.append({
    "icon": "💰",
    "title": "Investment Income Trajectory",
    "body": f"Total investment income 2025: {fmt_currency(total_income_2025)}. "
            f"2026 YTD: {fmt_currency(total_income_2026)}. "
            f"{'Income stream is growing — passive income is on an upward trajectory. 🎉' if total_income_2026 > total_income_2025 * 0.4 else 'Consider increasing dividend-paying holdings to build a stronger passive income stream.'}"
})

# ── Pre-compute year-conditional chart traces (inserted into HTML f-string) ───────
if year_filter == 2025:
    _c1_traces = (
        f"  {{ name: 'Buys',  x: months25, y: {json.dumps(chart1_buys_2025)},  type: 'bar', marker: {{ color: RED }}, offsetgroup: 'g' }},\n"
        f"  {{ name: 'Sells', x: months25, y: {json.dumps(chart1_sells_2025)}, type: 'bar', marker: {{ color: GREEN }}, offsetgroup: 'g' }},\n"
        f"  {{ name: 'Net',   x: months25, y: {json.dumps(chart1_net_2025)},   type: 'scatter', mode: 'lines+markers',\n"
        f"     marker: {{ color: ACCENT, size: 6 }}, line: {{ color: ACCENT, width: 2 }}, yaxis: 'y2' }},\n"
    )
    _c9_traces = (
        f"  {{ name: '2025 Cumulative', x: months25, y: {json.dumps(cum_income_2025)},\n"
        f"     type: 'scatter', mode: 'lines+markers', fill: 'tozeroy',\n"
        f"     line: {{ color: ACCENT, width: 2 }}, fillcolor: ACCENT + '22', marker: {{ size: 5 }} }},\n"
    )
elif year_filter == 2026:
    _c1_traces = (
        f"  {{ name: 'Buys',  x: months26, y: {json.dumps(chart1_buys_2026)},  type: 'bar', marker: {{ color: RED }}, offsetgroup: 'g' }},\n"
        f"  {{ name: 'Sells', x: months26, y: {json.dumps(chart1_sells_2026)}, type: 'bar', marker: {{ color: GREEN }}, offsetgroup: 'g' }},\n"
        f"  {{ name: 'Net',   x: months26, y: {json.dumps(chart1_net_2026)},   type: 'scatter', mode: 'lines+markers',\n"
        f"     marker: {{ color: ACCENT, size: 6 }}, line: {{ color: ACCENT, width: 2 }}, yaxis: 'y2' }},\n"
    )
    _c9_traces = (
        f"  {{ name: '2026 Cumulative', x: months26, y: {json.dumps(cum_income_2026)},\n"
        f"     type: 'scatter', mode: 'lines+markers', fill: 'tozeroy',\n"
        f"     line: {{ color: AMBER, width: 2 }}, fillcolor: AMBER + '22', marker: {{ size: 5, color: AMBER }} }},\n"
    )
else:
    _c1_traces = (
        f"  {{ name: 'Buys 2025',  x: months25, y: {json.dumps(chart1_buys_2025)},  type: 'bar', marker: {{ color: RED }},   offsetgroup: '2025' }},\n"
        f"  {{ name: 'Sells 2025', x: months25, y: {json.dumps(chart1_sells_2025)}, type: 'bar', marker: {{ color: GREEN }}, offsetgroup: '2025', base: 0 }},\n"
        f"  {{ name: 'Buys 2026',  x: months26, y: {json.dumps(chart1_buys_2026)},  type: 'bar', marker: {{ color: RED, opacity: 0.5 }},   offsetgroup: '2026' }},\n"
        f"  {{ name: 'Sells 2026', x: months26, y: {json.dumps(chart1_sells_2026)}, type: 'bar', marker: {{ color: GREEN, opacity: 0.5 }}, offsetgroup: '2026' }},\n"
        f"  {{ name: 'Net 2025', x: months25, y: {json.dumps(chart1_net_2025)}, type: 'scatter', mode: 'lines+markers',\n"
        f"     marker: {{ color: ACCENT, size: 6 }}, line: {{ color: ACCENT, width: 2 }}, yaxis: 'y2' }},\n"
        f"  {{ name: 'Net 2026', x: months26, y: {json.dumps(chart1_net_2026)}, type: 'scatter', mode: 'lines+markers',\n"
        f"     marker: {{ color: AMBER, size: 6 }}, line: {{ color: AMBER, width: 2, dash: 'dash' }}, yaxis: 'y2' }},\n"
    )
    _c9_traces = (
        f"  {{ name: '2025 Cumulative', x: months25, y: {json.dumps(cum_income_2025)},\n"
        f"     type: 'scatter', mode: 'lines+markers', fill: 'tozeroy',\n"
        f"     line: {{ color: ACCENT, width: 2 }}, fillcolor: ACCENT + '22', marker: {{ size: 5 }} }},\n"
        f"  {{ name: '2026 Cumulative', x: months26, y: {json.dumps(cum_income_2026)},\n"
        f"     type: 'scatter', mode: 'lines+markers',\n"
        f"     line: {{ color: AMBER, width: 2, dash: 'dash' }}, marker: {{ size: 5, color: AMBER }} }},\n"
    )

# ── HTML ──────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Portfolio & Investment Analysis</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --bg: {BG}; --card: {CARD}; --accent: {ACCENT};
  --text: {TEXT}; --muted: {MUTED}; --border: {BORDER};
  --green: {GREEN}; --red: {RED}; --amber: {AMBER};
  --purple: {PURPLE}; --cyan: {CYAN};
}}
body {{ background: var(--bg); color: var(--text); font-family: 'Inter', system-ui, sans-serif; padding: 24px; }}
h1 {{ font-size: 26px; font-weight: 700; color: var(--accent); margin-bottom: 6px; }}
.subtitle {{ font-size: 13px; color: var(--muted); margin-bottom: 28px; }}

/* Stat Cards */
.cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 14px; margin-bottom: 32px; }}
.card {{
  background: var(--card); border: 1px solid var(--border);
  border-radius: 12px; padding: 18px 20px;
}}
.card-label {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; }}
.card-value {{ font-size: 22px; font-weight: 700; color: var(--accent); }}
.card-sub   {{ font-size: 12px; color: var(--muted); margin-top: 4px; }}

/* Charts */
.charts-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 32px;
}}
.chart-full {{ grid-column: 1 / -1; }}
.chart-box {{
  background: var(--card); border: 1px solid var(--border);
  border-radius: 12px; padding: 18px;
}}
.chart-title {{ font-size: 13px; font-weight: 600; color: var(--text); margin-bottom: 12px; }}
.chart-wrap {{ width: 100%; }}

/* Recommendations */
.recs-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 14px; margin-bottom: 32px; }}
.rec {{
  background: var(--card); border: 1px solid var(--border);
  border-radius: 12px; padding: 18px;
}}
.rec-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
.rec-icon {{ font-size: 20px; }}
.rec-title {{ font-size: 14px; font-weight: 600; color: var(--accent); }}
.rec-body {{ font-size: 13px; color: var(--muted); line-height: 1.6; }}

.section-title {{
  font-size: 16px; font-weight: 700; color: var(--text);
  margin-bottom: 16px; padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}}
</style>
</head>
<body>
<h1>{PAGE_TITLE}</h1>
<div class="subtitle">{SUBTITLE}</div>

<!-- ── Stat Cards ── -->
<div class="section-title">📊 Summary Statistics</div>
<div class="cards">
  <div class="card">
    <div class="card-label">Total Buy Volume</div>
    <div class="card-value">{fmt_currency(total_buy_vol)}</div>
    <div class="card-sub">{YEAR_LABEL}</div>
  </div>
  <div class="card">
    <div class="card-label">Total Sell Volume</div>
    <div class="card-value">{fmt_currency(total_sell_vol)}</div>
    <div class="card-sub">{YEAR_LABEL}</div>
  </div>
  <div class="card">
    <div class="card-label">Net Cash Flow Activity</div>
    <div class="card-value" style="color: {'var(--green)' if net_activity >= 0 else 'var(--red)'}">
      {fmt_currency(net_activity)}
    </div>
    <div class="card-sub">Sells − Buys (not P&L)</div>
  </div>
  <div class="card">
    <div class="card-label">Total Dividends</div>
    <div class="card-value" style="color:var(--green)">{fmt_currency(total_dividends)}</div>
    <div class="card-sub">All dividend income</div>
  </div>
  <div class="card">
    <div class="card-label">Retirement Contributions</div>
    <div class="card-value">{fmt_currency(total_ret_all)}</div>
    <div class="card-sub">401k + IRA + HSA</div>
  </div>
  <div class="card">
    <div class="card-label">Most Traded Ticker</div>
    <div class="card-value" style="font-size:18px">{most_traded}</div>
    <div class="card-sub">{fmt_currency(ticker_vol.get(most_traded, 0))} volume</div>
  </div>
  <div class="card">
    <div class="card-label">Options Activity</div>
    <div class="card-value" style="color:var(--amber)">{fmt_currency(total_options_activity)}</div>
    <div class="card-sub">Calls + Puts (buy & sell)</div>
  </div>
  <div class="card">
    <div class="card-label">HSA Contributions</div>
    <div class="card-value">{fmt_currency(hsa_contribs)}</div>
    <div class="card-sub">Health Savings Account</div>
  </div>
</div>

<!-- ── Charts ── -->
<div class="section-title">📈 Investment Charts</div>
<div class="charts-grid">

  <!-- Chart 1: Monthly Net Investment Activity -->
  <div class="chart-box chart-full">
    <div class="chart-title">1. Monthly Net Investment Activity — Buys vs Sells (2025 & 2026)</div>
    <div class="chart-wrap" id="chart1"></div>
  </div>

  <!-- Chart 2: Investment Income by Month -->
  <div class="chart-box chart-full">
    <div class="chart-title">2. Investment Income by Month — Stacked by Type</div>
    <div class="chart-wrap" id="chart2"></div>
  </div>

  <!-- Chart 3: Dividend Income by Ticker -->
  <div class="chart-box">
    <div class="chart-title">3. Dividend Income — Top 15 Tickers</div>
    <div class="chart-wrap" id="chart3"></div>
  </div>

  <!-- Chart 4: Retirement Contributions by Month -->
  <div class="chart-box">
    <div class="chart-title">4. Retirement Contributions by Month</div>
    <div class="chart-wrap" id="chart4"></div>
  </div>

  <!-- Chart 5: Treemap -->
  <div class="chart-box">
    <div class="chart-title">5. Top 20 Most Traded Tickers — Volume Treemap</div>
    <div class="chart-wrap" id="chart5"></div>
  </div>

  <!-- Chart 6: Options Activity -->
  <div class="chart-box">
    <div class="chart-title">6. Options Activity — Calls vs Puts by Month</div>
    <div class="chart-wrap" id="chart6"></div>
  </div>

  <!-- Chart 7: Account Donut -->
  <div class="chart-box">
    <div class="chart-title">7. Account Activity Breakdown — Dollar Volume</div>
    <div class="chart-wrap" id="chart7"></div>
  </div>

  <!-- Chart 8: Buy/Sell Ratio -->
  <div class="chart-box">
    <div class="chart-title">8. Monthly Buy vs Sell Ratio (>1 = Net Seller)</div>
    <div class="chart-wrap" id="chart8"></div>
  </div>

  <!-- Chart 9: Cumulative Investment Income -->
  <div class="chart-box">
    <div class="chart-title">9. Cumulative Investment Income — 2025 vs 2026</div>
    <div class="chart-wrap" id="chart9"></div>
  </div>

  <!-- Chart 10: Top Buys vs Top Sells -->
  <div class="chart-box chart-full">
    <div class="chart-title">10. Top 10 Tickers: Buy Volume vs Sell Volume</div>
    <div class="chart-wrap" id="chart10"></div>
  </div>

</div>

<!-- ── Recommendations ── -->
<div class="section-title">💡 Recommendations</div>
<div class="recs-grid">
{"".join(f'''
  <div class="rec">
    <div class="rec-header">
      <span class="rec-icon">{r["icon"]}</span>
      <span class="rec-title">{r["title"]}</span>
    </div>
    <div class="rec-body">{r["body"]}</div>
  </div>
''' for r in recs)}
</div>

<script>
const BG = '{BG}', CARD = '{CARD}', ACCENT = '{ACCENT}', TEXT = '{TEXT}', MUTED = '{MUTED}';
const GREEN = '{GREEN}', RED = '{RED}', AMBER = '{AMBER}', PURPLE = '{PURPLE}', CYAN = '{CYAN}';

const layout_base = (title='', xaxis={{}}, yaxis={{}}, extra={{}}) => ({{
  paper_bgcolor: CARD, plot_bgcolor: CARD,
  font: {{ color: TEXT, family: 'Inter, system-ui, sans-serif', size: 11 }},
  margin: {{ t: 30, b: 60, l: 60, r: 20 }},
  title: title ? {{ text: title, font: {{ size: 13 }} }} : undefined,
  xaxis: {{ gridcolor: '#2a2d3a', color: MUTED, ...xaxis }},
  yaxis: {{ gridcolor: '#2a2d3a', color: MUTED, ...yaxis }},
  legend: {{ bgcolor: 'transparent', font: {{ color: TEXT, size: 11 }} }},
  ...extra
}});

const months25 = {json.dumps([fmt_month(m) for m in months_2025])};
const months26 = {json.dumps([fmt_month(m) for m in months_2026])};
const allMonths = {json.dumps(chart1_labels)};

// ── Chart 1 ─────────────────────────────────────────────────────
Plotly.newPlot('chart1', [
{_c1_traces}], {{
  ...layout_base('', {{}}, {{ title: 'Volume ($)' }}, {{
    yaxis2: {{ title: 'Net ($)', overlaying: 'y', side: 'right', gridcolor: 'transparent', color: MUTED }},
    barmode: 'group',
    height: 380
  }})
}}, {{responsive: true}});

// ── Chart 2 ─────────────────────────────────────────────────────
const incomeTypes = {json.dumps(income_types)};
const incomeColors = [ACCENT, AMBER, PURPLE, CYAN];
const chart2Data = {json.dumps(chart2_data)};
Plotly.newPlot('chart2',
  incomeTypes.map((t, i) => ({{
    name: t, x: allMonths, y: chart2Data[t], type: 'bar',
    marker: {{ color: incomeColors[i] }}
  }})),
  {{ ...layout_base('', {{}}, {{ title: 'Income ($)' }}, {{ barmode: 'stack', height: 320 }}) }},
  {{responsive: true}}
);

// ── Chart 3 ─────────────────────────────────────────────────────
Plotly.newPlot('chart3', [{{
  type: 'bar', orientation: 'h',
  x: {json.dumps(chart3_vals[::-1])},
  y: {json.dumps(chart3_labels[::-1])},
  marker: {{ color: ACCENT, opacity: 0.85 }},
  text: {json.dumps([f'${v:,.0f}' for v in chart3_vals[::-1]])},
  textposition: 'outside', textfont: {{ color: TEXT, size: 11 }}
}}], {{
  ...layout_base('', {{ title: 'Dividend Received ($)' }}, {{}}, {{ height: 400, margin: {{ l: 80, r: 80 }} }})
}}, {{responsive: true}});

// ── Chart 4 ─────────────────────────────────────────────────────
Plotly.newPlot('chart4', [
  {{ name: '401(k)', x: allMonths, y: {json.dumps(chart4_401k)}, type: 'bar', marker: {{ color: ACCENT }} }},
  {{ name: 'IRA',    x: allMonths, y: {json.dumps(chart4_ira)},  type: 'bar', marker: {{ color: PURPLE }} }},
  {{ name: 'HSA',    x: allMonths, y: {json.dumps(chart4_hsa)},  type: 'bar', marker: {{ color: CYAN }} }},
], {{
  ...layout_base('', {{}}, {{ title: 'Contributions ($)' }}, {{
    barmode: 'group', height: 360,
    annotations: [
      {{ text: `2025: ${ {json.dumps(round(total_ret_2025,0))} }`, xref:'paper', yref:'paper', x:0.01, y:0.99, showarrow:false, font:{{color:MUTED,size:11}} }},
      {{ text: `2026 YTD: ${ {json.dumps(round(total_ret_2026,0))} }`, xref:'paper', yref:'paper', x:0.01, y:0.93, showarrow:false, font:{{color:MUTED,size:11}} }},
    ]
  }})
}}, {{responsive: true}});

// ── Chart 5: Treemap ─────────────────────────────────────────────
Plotly.newPlot('chart5', [{{
  type: 'treemap',
  labels: {json.dumps(chart5_labels)},
  values: {json.dumps(chart5_vals)},
  parents: {json.dumps(chart5_parents)},
  textinfo: 'label+value+percent parent',
  marker: {{ colorscale: [[0, '#1a1d27'], [1, ACCENT]], showscale: false }},
  hovertemplate: '<b>%{{label}}</b><br>Volume: $%{{value:,.0f}}<extra></extra>'
}}], {{
  paper_bgcolor: CARD, plot_bgcolor: CARD,
  font: {{ color: TEXT, family: 'Inter', size: 11 }},
  margin: {{ t: 10, b: 10, l: 10, r: 10 }},
  height: 380
}}, {{responsive: true}});

// ── Chart 6: Options ─────────────────────────────────────────────
Plotly.newPlot('chart6', [
  {{ name: 'Calls Bought', x: allMonths, y: {json.dumps(chart6_calls_buy)},  type: 'bar', marker: {{ color: '#2ecc71' }} }},
  {{ name: 'Calls Sold',   x: allMonths, y: {json.dumps(chart6_calls_sell)}, type: 'bar', marker: {{ color: '#27ae60' }} }},
  {{ name: 'Puts Bought',  x: allMonths, y: {json.dumps(chart6_puts_buy)},   type: 'bar', marker: {{ color: '#e74c3c' }} }},
  {{ name: 'Puts Sold',    x: allMonths, y: {json.dumps(chart6_puts_sell)},  type: 'bar', marker: {{ color: '#c0392b' }} }},
], {{
  ...layout_base('', {{}}, {{ title: 'Volume ($)' }}, {{ barmode: 'group', height: 340 }})
}}, {{responsive: true}});

// ── Chart 7: Donut ───────────────────────────────────────────────
Plotly.newPlot('chart7', [{{
  type: 'pie', hole: 0.55,
  labels: {json.dumps(chart7_labels)},
  values: {json.dumps(chart7_vals)},
  marker: {{ colors: [ACCENT, AMBER, GREEN, PURPLE, CYAN, RED] }},
  textinfo: 'label+percent',
  textfont: {{ color: TEXT, size: 12 }},
  hovertemplate: '<b>%{{label}}</b><br>$%{{value:,.0f}}<br>%{{percent}}<extra></extra>'
}}], {{
  paper_bgcolor: CARD, plot_bgcolor: CARD,
  font: {{ color: TEXT, family: 'Inter' }},
  margin: {{ t: 20, b: 20, l: 20, r: 20 }},
  height: 320,
  legend: {{ bgcolor: 'transparent', font: {{ color: TEXT }} }}
}}, {{responsive: true}});

// ── Chart 8: Ratio line ───────────────────────────────────────────
const ratio_vals = {json.dumps(chart8_ratio)};
Plotly.newPlot('chart8', [
  {{ x: allMonths, y: ratio_vals, type: 'scatter', mode: 'lines+markers',
     line: {{ color: ACCENT, width: 2 }}, marker: {{ size: 7, color: ratio_vals.map(v => v > 1 ? GREEN : (v < 1 ? RED : MUTED)) }},
     name: 'Sell/Buy Ratio',
     hovertemplate: '%{{x}}<br>Ratio: %{{y:.2f}}<extra></extra>' }},
  {{ x: allMonths, y: allMonths.map(() => 1), type: 'scatter', mode: 'lines',
     line: {{ color: MUTED, width: 1, dash: 'dash' }}, name: 'Breakeven (1.0)', showlegend: true }}
], {{
  ...layout_base('', {{}}, {{ title: 'Sell/Buy Ratio', range: [0, null] }}, {{ height: 300 }})
}}, {{responsive: true}});

// ── Chart 9: Cumulative income ────────────────────────────────────
Plotly.newPlot('chart9', [
{_c9_traces}], {{
  ...layout_base('', {{}}, {{ title: 'Cumulative Income ($)' }}, {{ height: 300 }})
}}, {{responsive: true}});

// ── Chart 10: Top Buys vs Sells ───────────────────────────────────
Plotly.newPlot('chart10', [
  {{ name: 'Top Buys', type: 'bar', orientation: 'h',
     x: {json.dumps(chart10_buy_vals[::-1])},
     y: {json.dumps([f'BUY: {t}' for t in chart10_buy_labels[::-1]])},
     marker: {{ color: RED, opacity: 0.85 }},
     text: {json.dumps([f'${v:,.0f}' for v in chart10_buy_vals[::-1]])},
     textposition: 'outside', textfont: {{ color: TEXT, size: 10 }}
  }},
  {{ name: 'Top Sells', type: 'bar', orientation: 'h',
     x: {json.dumps(chart10_sell_vals[::-1])},
     y: {json.dumps([f'SELL: {t}' for t in chart10_sell_labels[::-1]])},
     marker: {{ color: GREEN, opacity: 0.85 }},
     text: {json.dumps([f'${v:,.0f}' for v in chart10_sell_vals[::-1]])},
     textposition: 'outside', textfont: {{ color: TEXT, size: 10 }}
  }},
], {{
  ...layout_base('', {{ title: 'Volume ($)' }}, {{}}, {{
    barmode: 'overlay', height: 460,
    margin: {{ l: 110, r: 100 }}
  }})
}}, {{responsive: true}});
</script>
</body>
</html>"""

OUT_FILE.write_text(html, encoding="utf-8")
print(f"✅ Generated: {OUT_FILE}")
print(f"   Total buy volume: {fmt_currency(total_buy_vol)}")
print(f"   Total sell volume: {fmt_currency(total_sell_vol)}")
print(f"   Total dividends: {fmt_currency(total_dividends)}")
print(f"   Total retirement contributions: {fmt_currency(total_ret_all)}")
print(f"   Options activity: {fmt_currency(total_options_activity)}")
print(f"   Most traded ticker: {most_traded}")
