#!/usr/bin/env python3
"""
YoY Financial Analysis Report Generator
Produces a dark-themed interactive HTML report using Plotly.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ─── CONFIG ──────────────────────────────────────────────────────────────────
CSV_2025 = "/Users/jasleenkaur/AgenticHub/second-brain/persgraph/data/transactions_2025.csv"
CSV_2026 = "/Users/jasleenkaur/AgenticHub/second-brain/persgraph/data/transactions_2026.csv"
OUTPUT   = "/Users/jasleenkaur/AgenticHub/second-brain/persgraph/financial_report_yoy.html"

BG      = "#0f1117"
CARD    = "#1a1d27"
ACCENT  = "#6c8ef5"
TEXT    = "#e0e4f0"
MUTED   = "#8892a4"
BORDER  = "#2a2f45"
RED     = "#ff6b6b"
GREEN   = "#51cf66"
YELLOW  = "#ffd43b"
ORANGE  = "#ff922b"
PINK    = "#f06595"
TEAL    = "#20c997"
PURPLE  = "#cc5de8"

PALETTE = [ACCENT, TEAL, GREEN, YELLOW, ORANGE, PINK, RED, PURPLE, "#74c0fc", "#a9e34b",
           "#ffa94d", "#e599f7", "#63e6be", "#ffec99", "#a5d8ff", "#b2f2bb"]

# ─── CATEGORIES TO SKIP ──────────────────────────────────────────────────────
SKIP_CATS = {
    "Securities Trades", "Transfers", "Credit Card Payments",
    "Retirement Contributions", "Refunds & Reimbursements", "Uncategorized"
}

# ─── CATEGORY REMAPPING ──────────────────────────────────────────────────────
REMAP = {
    "Restaurants":          "Dining Out",
    "Groceries":            "Groceries",
    "General Merchandise":  "Shopping",
    "Online Services":      "Online Services / AI",
    "Entertainment":        "Entertainment",
    "Travel":               "Travel",
    "Gasoline/Fuel":        "Gas & Fuel",
    "Healthcare/Medical":   "Healthcare",
    "Insurance":            "Insurance",
    "Dues & Subscriptions": "Subscriptions",
    "Service Charges/Fees": "Bank Fees",
    "Telephone":            "Phone",
    "Utilities":            "Utilities",
    "Personal Care":        "Personal Care",
    "Home Improvement":     "Home",
    "Home Maintenance":     "Home",
    "Automotive":           "Automotive",
    "ATM/Cash":             "Cash/ATM",
    "Other Expenses":       "Other",
    "Loans":                "Loans",
    "Mortgages":            "Housing (Mortgage)",
    "Deposits":             "Income",
    "Interest":             "Interest Income",
    "Investment Income":    "Investment Income",
    "Education":            "Education",
    "Checks":               "Checks",
    "Hobbies":              "Hobbies",
    "Electronics":          "Electronics",
    "Clothing/Shoes":       "Clothing",
    "Rent":                 "Rent",
}

MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

AI_KEYWORDS = ["chatgpt","openai","claude","anthropic","grok","google fi","microsoft","github",
               "copilot","perplexity","midjourney","stability","notion","obsidian","notion"]

SUB_KEYWORDS = ["netflix","spotify","hulu","disney","apple","amazon prime","youtube",
                "chatgpt","claude","anthropic","github","notion","figma","adobe",
                "dropbox","icloud","google one","microsoft","xfinity","at&t","verizon",
                "t-mobile","google fi","linkedin","audible","kindle","duolingo","headspace",
                "calm","peloton","nytimes","wsj","hbo","paramount","peacock","espn",
                "twitch","crunchyroll","grok","perplexity","cursor","windsurf","replit"]

# ─── LOAD & CLEAN ─────────────────────────────────────────────────────────────
def load(path, year):
    df = pd.read_csv(path, parse_dates=["Date"])
    df["year"] = year
    df["month"] = df["Date"].dt.month
    df["month_name"] = df["Date"].dt.strftime("%b")
    df["dow"] = df["Date"].dt.day_name()
    df["day"] = df["Date"].dt.date
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0)
    # Expenses are negative in this dataset
    df["expense"] = df["Amount"].apply(lambda x: abs(x) if x < 0 else 0)
    df["income"]  = df["Amount"].apply(lambda x: x if x > 0 else 0)
    df["category_raw"] = df["Category"].fillna("Other Expenses")
    df = df[~df["category_raw"].isin(SKIP_CATS)].copy()
    df["category"] = df["category_raw"].map(REMAP).fillna(df["category_raw"])
    df["merchant"] = df["Description"].str.strip()
    return df

df25 = load(CSV_2025, 2025)
df26 = load(CSV_2026, 2026)

# Jan-May slices
df25_janmay = df25[df25["month"] <= 5].copy()
df26_janmay = df26.copy()  # 2026 is already Jan-May

# Expense-only frames
exp25     = df25[df25["expense"] > 0]
exp26     = df26[df26["expense"] > 0]
exp25_jm  = df25_janmay[df25_janmay["expense"] > 0]
exp26_jm  = df26_janmay[df26_janmay["expense"] > 0]

# ─── TAX ANOMALY HANDLING ────────────────────────────────────────────────────
# Taxes are one-time anomalies: included in total, excluded from monthly avg
tax25     = exp25[exp25["category_raw"] == "Taxes"]["expense"].sum()
tax26     = exp26[exp26["category_raw"] == "Taxes"]["expense"].sum()
tax25_jm  = exp25_jm[exp25_jm["category_raw"] == "Taxes"]["expense"].sum()
tax26_jm  = exp26_jm[exp26_jm["category_raw"] == "Taxes"]["expense"].sum()

# Frames without tax for monthly average calculations
exp25_notax    = exp25[exp25["category_raw"] != "Taxes"]
exp26_notax    = exp26[exp26["category_raw"] != "Taxes"]
exp25_jm_notax = exp25_jm[exp25_jm["category_raw"] != "Taxes"]
exp26_jm_notax = exp26_jm[exp26_jm["category_raw"] != "Taxes"]

# ─── STAT CALCULATIONS ───────────────────────────────────────────────────────
total25_fy  = exp25["expense"].sum()   # includes tax (for totals)
total25_jm  = exp25_jm["expense"].sum()
total26_ytd = exp26["expense"].sum()   # includes tax (for totals)
yoy_change  = ((total26_ytd - total25_jm) / total25_jm * 100) if total25_jm else 0
# Monthly averages EXCLUDE one-time tax payments
avg25_mo    = exp25_notax["expense"].sum() / 12
avg26_mo    = exp26_notax["expense"].sum() / 5

top_cat25   = exp25.groupby("category")["expense"].sum().idxmax()
top_cat26   = exp26.groupby("category")["expense"].sum().idxmax()

sub25 = exp25[exp25["merchant"].str.lower().str.contains("|".join(SUB_KEYWORDS), na=False)]["expense"].sum()
sub26 = exp26[exp26["merchant"].str.lower().str.contains("|".join(SUB_KEYWORDS), na=False)]["expense"].sum()

din25 = exp25[exp25["category"] == "Dining Out"]["expense"].sum()
din26 = exp26[exp26["category"] == "Dining Out"]["expense"].sum()

n_tx25 = len(df25)
n_tx26 = len(df26)

# ─── PLOTLY THEME DEFAULTS ───────────────────────────────────────────────────
LAYOUT_BASE = dict(
    paper_bgcolor=CARD,
    plot_bgcolor=CARD,
    font=dict(family="Inter, system-ui, sans-serif", color=TEXT, size=12),
    margin=dict(l=40, r=20, t=50, b=40),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=BORDER, font=dict(color=TEXT)),
    xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, tickfont=dict(color=MUTED)),
    yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, tickfont=dict(color=MUTED)),
)

def fig_to_html(fig, div_id):
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=div_id)

def apply_layout(fig, title="", **kwargs):
    layout = dict(**LAYOUT_BASE)
    layout.update(kwargs)
    if title:
        layout["title"] = dict(text=title, font=dict(color=TEXT, size=15), x=0.03)
    # Apply axis defaults to all axes
    for k, v in list(layout.items()):
        if k.startswith("xaxis") or k.startswith("yaxis"):
            pass
    fig.update_layout(**layout)
    fig.update_xaxes(gridcolor=BORDER, zerolinecolor=BORDER, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=BORDER, zerolinecolor=BORDER, tickfont=dict(color=MUTED))
    return fig

# ─── CHART 1: YoY Monthly Spending Comparison ────────────────────────────────
def chart_yoy_monthly():
    months = list(range(1, 6))
    vals25 = [exp25_jm[exp25_jm["month"]==m]["expense"].sum() for m in months]
    vals26 = [exp26_jm[exp26_jm["month"]==m]["expense"].sum() for m in months]
    labels = [MONTH_NAMES[m-1] for m in months]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=vals25, name="2025 (Jan–May)", marker_color="#4a6cf7",
                         text=[f"${v:,.0f}" for v in vals25], textposition="outside",
                         textfont=dict(color=TEXT, size=10)))
    fig.add_trace(go.Bar(x=labels, y=vals26, name="2026 (Jan–May)", marker_color=TEAL,
                         text=[f"${v:,.0f}" for v in vals26], textposition="outside",
                         textfont=dict(color=TEXT, size=10)))
    apply_layout(fig, "YoY Monthly Spending: Jan–May 2025 vs 2026", barmode="group",
                 yaxis=dict(tickprefix="$", tickformat=",.0f", gridcolor=BORDER, zerolinecolor=BORDER))
    return fig_to_html(fig, "chart1")

# ─── CHART 2: 2025 Full Year Monthly Breakdown ───────────────────────────────
def chart_2025_stacked():
    cats = exp25.groupby("category")["expense"].sum().nlargest(12).index.tolist()
    months = list(range(1, 13))
    fig = go.Figure()
    for i, cat in enumerate(cats):
        sub = exp25[exp25["category"]==cat]
        vals = [sub[sub["month"]==m]["expense"].sum() for m in months]
        fig.add_trace(go.Bar(x=MONTH_NAMES, y=vals, name=cat,
                             marker_color=PALETTE[i % len(PALETTE)]))
    apply_layout(fig, "2025 Full Year Monthly Spending by Category", barmode="stack",
                 yaxis=dict(tickprefix="$", tickformat=",.0f", gridcolor=BORDER, zerolinecolor=BORDER))
    return fig_to_html(fig, "chart2")

# ─── CHART 3: 2026 YTD Monthly Breakdown ─────────────────────────────────────
def chart_2026_stacked():
    cats = exp26.groupby("category")["expense"].sum().nlargest(12).index.tolist()
    months = list(range(1, 6))
    labels = [MONTH_NAMES[m-1] for m in months]
    fig = go.Figure()
    for i, cat in enumerate(cats):
        sub = exp26[exp26["category"]==cat]
        vals = [sub[sub["month"]==m]["expense"].sum() for m in months]
        fig.add_trace(go.Bar(x=labels, y=vals, name=cat,
                             marker_color=PALETTE[i % len(PALETTE)]))
    apply_layout(fig, "2026 YTD Monthly Spending by Category", barmode="stack",
                 yaxis=dict(tickprefix="$", tickformat=",.0f", gridcolor=BORDER, zerolinecolor=BORDER))
    return fig_to_html(fig, "chart3")

# ─── CHART 4: Category Comparison Jan–May ────────────────────────────────────
def chart_cat_comparison():
    cat25 = exp25_jm.groupby("category")["expense"].sum()
    cat26 = exp26_jm.groupby("category")["expense"].sum()
    combined = (cat25.add(cat26, fill_value=0)).nlargest(10).index.tolist()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=combined,
        y=[cat25.get(c, 0) for c in combined],
        name="2025 Jan–May", marker_color="#4a6cf7",
        text=[f"${cat25.get(c,0):,.0f}" for c in combined],
        textposition="outside", textfont=dict(color=TEXT, size=9)
    ))
    fig.add_trace(go.Bar(
        x=combined,
        y=[cat26.get(c, 0) for c in combined],
        name="2026 Jan–May", marker_color=TEAL,
        text=[f"${cat26.get(c,0):,.0f}" for c in combined],
        textposition="outside", textfont=dict(color=TEXT, size=9)
    ))
    apply_layout(fig, "Top 10 Categories: Jan–May 2025 vs 2026", barmode="group",
                 xaxis=dict(tickangle=-20, gridcolor=BORDER, zerolinecolor=BORDER),
                 yaxis=dict(tickprefix="$", tickformat=",.0f", gridcolor=BORDER, zerolinecolor=BORDER))
    return fig_to_html(fig, "chart4")

# ─── CHART 5: 2025 Spending Donut ────────────────────────────────────────────
def chart_donut_2025():
    cat_totals = exp25.groupby("category")["expense"].sum().nlargest(14)
    # Merge rest into "Other"
    all_totals = exp25.groupby("category")["expense"].sum()
    rest = all_totals[~all_totals.index.isin(cat_totals.index)].sum()
    labels = list(cat_totals.index) + ["Other"]
    values = list(cat_totals.values) + [rest]

    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.5,
        marker=dict(colors=PALETTE[:len(labels)], line=dict(color=BG, width=2)),
        textinfo="label+percent",
        textfont=dict(color=TEXT, size=10),
        hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>"
    ))
    apply_layout(fig, "2025 Full Year Spending by Category",
                 showlegend=False,
                 annotations=[dict(text=f"${total25_fy:,.0f}<br>Total", x=0.5, y=0.5,
                                   font=dict(color=TEXT, size=13), showarrow=False)])
    return fig_to_html(fig, "chart5")

# ─── CHART 6: 2026 Spending Donut ────────────────────────────────────────────
def chart_donut_2026():
    cat_totals = exp26.groupby("category")["expense"].sum().nlargest(14)
    all_totals = exp26.groupby("category")["expense"].sum()
    rest = all_totals[~all_totals.index.isin(cat_totals.index)].sum()
    labels = list(cat_totals.index) + ["Other"]
    values = list(cat_totals.values) + [rest]

    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.5,
        marker=dict(colors=PALETTE[:len(labels)], line=dict(color=BG, width=2)),
        textinfo="label+percent",
        textfont=dict(color=TEXT, size=10),
        hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>"
    ))
    apply_layout(fig, "2026 YTD Spending by Category",
                 showlegend=False,
                 annotations=[dict(text=f"${total26_ytd:,.0f}<br>Total", x=0.5, y=0.5,
                                   font=dict(color=TEXT, size=13), showarrow=False)])
    return fig_to_html(fig, "chart6")

# ─── CHART 7: Top 20 Merchants Treemap ───────────────────────────────────────
def chart_treemap():
    combined = pd.concat([exp25, exp26])
    merchants = combined.groupby("merchant")["expense"].sum().nlargest(20).reset_index()
    merchants.columns = ["merchant", "total"]

    fig = go.Figure(go.Treemap(
        labels=merchants["merchant"],
        parents=[""] * len(merchants),
        values=merchants["total"],
        texttemplate="<b>%{label}</b><br>$%{value:,.0f}",
        marker=dict(
            colors=merchants["total"],
            colorscale=[[0, "#1a1d27"], [0.3, "#3a4470"], [0.7, "#4a6cf7"], [1.0, TEAL]],
            showscale=False
        ),
        hovertemplate="<b>%{label}</b><br>Total: $%{value:,.0f}<extra></extra>"
    ))
    apply_layout(fig, "Top 20 Merchants by Combined Spend (2025 + 2026)")
    return fig_to_html(fig, "chart7")

# ─── CHART 8: Dining Out Deep Dive ───────────────────────────────────────────
def chart_dining():
    combined = pd.concat([exp25, exp26])
    dining = combined[combined["category"] == "Dining Out"]
    top = dining.groupby("merchant")["expense"].sum().nlargest(15).sort_values()

    fig = go.Figure(go.Bar(
        x=top.values, y=top.index, orientation="h",
        marker=dict(
            color=top.values,
            colorscale=[[0,"#2a1f3d"],[0.5,"#7c4dcd"],[1.0, PINK]],
            showscale=False
        ),
        text=[f"${v:,.0f}" for v in top.values],
        textposition="outside",
        textfont=dict(color=TEXT, size=10),
        hovertemplate="<b>%{y}</b><br>$%{x:,.0f}<extra></extra>"
    ))
    apply_layout(fig, "Top 15 Restaurants: Combined 2025 + 2026",
                 xaxis=dict(tickprefix="$", tickformat=",.0f", gridcolor=BORDER, zerolinecolor=BORDER),
                 height=500)
    return fig_to_html(fig, "chart8")

# ─── CHART 9: Subscriptions & Recurring ──────────────────────────────────────
def chart_subscriptions():
    combined = pd.concat([exp25, exp26])
    subs = combined[combined["merchant"].str.lower().str.contains("|".join(SUB_KEYWORDS), na=False)]
    
    by_year = subs.groupby(["merchant","year"])["expense"].sum().reset_index()
    top_merchants = subs.groupby("merchant")["expense"].sum().nlargest(20).index.tolist()
    by_year = by_year[by_year["merchant"].isin(top_merchants)]

    fig = go.Figure()
    for year, color in [(2025, "#4a6cf7"), (2026, TEAL)]:
        sub = by_year[by_year["year"]==year].sort_values("expense")
        fig.add_trace(go.Bar(
            x=sub["expense"], y=sub["merchant"], orientation="h",
            name=str(year), marker_color=color,
            text=[f"${v:,.0f}" for v in sub["expense"]],
            textposition="outside", textfont=dict(color=TEXT, size=9)
        ))
    apply_layout(fig, "Subscriptions & Recurring Services by Year", barmode="group",
                 xaxis=dict(tickprefix="$", tickformat=",.0f", gridcolor=BORDER, zerolinecolor=BORDER),
                 height=600)
    return fig_to_html(fig, "chart9")

# ─── CHART 10: AI/Tech Services ──────────────────────────────────────────────
def chart_ai_tech():
    combined = pd.concat([exp25, exp26])
    ai = combined[combined["merchant"].str.lower().str.contains("|".join(AI_KEYWORDS), na=False)]
    
    if ai.empty:
        fig = go.Figure()
        fig.add_annotation(text="No AI/Tech service transactions found", 
                          x=0.5, y=0.5, showarrow=False, font=dict(color=MUTED, size=14))
        apply_layout(fig, "AI & Tech Services Spend")
        return fig_to_html(fig, "chart10")

    by_year = ai.groupby(["merchant","year"])["expense"].sum().reset_index()
    top_merchants = ai.groupby("merchant")["expense"].sum().nlargest(15).index.tolist()
    by_year = by_year[by_year["merchant"].isin(top_merchants)]

    totals = by_year.groupby("merchant")["expense"].sum().sort_values()
    ordered = totals.index.tolist()

    fig = go.Figure()
    for year, color in [(2025, "#4a6cf7"), (2026, ORANGE)]:
        sub = by_year[by_year["year"]==year]
        sub = sub.set_index("merchant").reindex(ordered).fillna(0).reset_index()
        fig.add_trace(go.Bar(
            x=sub["expense"], y=sub["merchant"], orientation="h",
            name=str(year), marker_color=color,
            text=[f"${v:,.0f}" if v > 0 else "" for v in sub["expense"]],
            textposition="outside", textfont=dict(color=TEXT, size=9)
        ))
    apply_layout(fig, "AI & Tech Services Spend by Year", barmode="group",
                 xaxis=dict(tickprefix="$", tickformat=",.0f", gridcolor=BORDER, zerolinecolor=BORDER),
                 height=500)
    return fig_to_html(fig, "chart10")

# ─── CHART 11: Day of Week Heatmap ───────────────────────────────────────────
def chart_dow_heatmap():
    # Pivot: week-of-year vs day-of-week
    df = exp26.copy()
    df["week"] = df["Date"].dt.isocalendar().week.astype(int)
    df["dow_num"] = df["Date"].dt.dayofweek  # 0=Mon
    
    pivot = df.groupby(["week","dow_num"])["expense"].sum().reset_index()
    weeks = sorted(pivot["week"].unique())
    
    matrix = np.zeros((7, len(weeks)))
    week_idx = {w: i for i, w in enumerate(weeks)}
    for _, row in pivot.iterrows():
        d, w = int(row["dow_num"]), int(row["week"])
        if w in week_idx:
            matrix[d][week_idx[w]] += row["expense"]

    days_order = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    week_labels = [f"Wk {w}" for w in weeks]

    fig = go.Figure(go.Heatmap(
        z=matrix, x=week_labels, y=days_order,
        colorscale=[[0, CARD],[0.3,"#2a3a6e"],[0.6,"#4a6cf7"],[1.0, TEAL]],
        hoverongaps=False,
        hovertemplate="Week %{x}<br>%{y}<br>$%{z:,.0f}<extra></extra>",
        showscale=True,
        colorbar=dict(tickfont=dict(color=MUTED), title=dict(text="$", font=dict(color=MUTED)))
    ))
    apply_layout(fig, "2026 Day-of-Week Spending Heatmap",
                 xaxis=dict(tickangle=-45, gridcolor=BORDER, zerolinecolor=BORDER, tickfont=dict(color=MUTED, size=9)),
                 height=280)
    return fig_to_html(fig, "chart11")

# ─── CHART 12: Daily Spend + 7-day MA ────────────────────────────────────────
def chart_daily_spend():
    daily = exp26.groupby("day")["expense"].sum().reset_index()
    daily["day"] = pd.to_datetime(daily["day"])
    daily = daily.sort_values("day")
    daily["ma7"] = daily["expense"].rolling(7, min_periods=1).mean()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily["day"], y=daily["expense"],
        name="Daily Spend",
        marker_color="rgba(74, 108, 247, 0.4)",
        hovertemplate="%{x|%b %d}<br>$%{y:,.0f}<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=daily["day"], y=daily["ma7"],
        name="7-Day Moving Avg",
        line=dict(color=TEAL, width=2.5),
        hovertemplate="%{x|%b %d}<br>7-Day Avg: $%{y:,.2f}<extra></extra>"
    ))
    apply_layout(fig, "2026 Daily Spending + 7-Day Moving Average",
                 xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
                 yaxis=dict(tickprefix="$", tickformat=",.0f", gridcolor=BORDER, zerolinecolor=BORDER))
    return fig_to_html(fig, "chart12")

# ─── GENERATE ALL CHARTS ─────────────────────────────────────────────────────
print("Generating charts...")
c1  = chart_yoy_monthly()
c2  = chart_2025_stacked()
c3  = chart_2026_stacked()
c4  = chart_cat_comparison()
c5  = chart_donut_2025()
c6  = chart_donut_2026()
c7  = chart_treemap()
c8  = chart_dining()
c9  = chart_subscriptions()
c10 = chart_ai_tech()
c11 = chart_dow_heatmap()
c12 = chart_daily_spend()
print("Charts generated.")

# ─── RECOMMENDATIONS ─────────────────────────────────────────────────────────
def build_recommendations():
    recs = []

    # 1. Overall trend
    if yoy_change > 5:
        recs.append(("HIGH", "📈 Overall Spending Up",
            f"Jan–May 2026 spending is <b>{abs(yoy_change):.1f}% higher</b> than the same period in 2025 "
            f"(${total26_ytd:,.0f} vs ${total25_jm:,.0f}). Review discretionary categories and set a monthly budget cap."))
    elif yoy_change < -5:
        recs.append(("LOW", "✅ Overall Spending Down",
            f"Jan–May 2026 spending is <b>{abs(yoy_change):.1f}% lower</b> than 2025 — great progress! "
            f"(${total26_ytd:,.0f} vs ${total25_jm:,.0f}). Maintain the momentum."))
    else:
        recs.append(("MEDIUM", "📊 Spending Roughly Flat",
            f"Jan–May spending is nearly the same year-over-year ({yoy_change:+.1f}%). "
            "Identify categories where small cuts could free up savings capacity."))

    # 2. Dining
    din_jm25 = exp25_jm[exp25_jm["category"]=="Dining Out"]["expense"].sum()
    din_jm26 = exp26_jm[exp26_jm["category"]=="Dining Out"]["expense"].sum()
    if din_jm26 > din_jm25 * 1.1:
        delta = din_jm26 - din_jm25
        recs.append(("HIGH", "🍽️ Dining Out Trending Up",
            f"Dining Out spend jumped ${delta:,.0f} from Jan–May 2025 to 2026 "
            f"(${din_jm25:,.0f} → ${din_jm26:,.0f}). Consider cooking at home 1-2 more nights/week — "
            "that alone could save $200–400/month."))

    # 3. Subscriptions
    sub_jm25 = exp25_jm[exp25_jm["merchant"].str.lower().str.contains("|".join(SUB_KEYWORDS), na=False)]["expense"].sum()
    sub_jm26 = exp26_jm[exp26_jm["merchant"].str.lower().str.contains("|".join(SUB_KEYWORDS), na=False)]["expense"].sum()
    recs.append(("MEDIUM", "🔄 Subscription Audit Recommended",
        f"Subscription spend: ${sub_jm25:,.0f} in Jan–May 2025 vs ${sub_jm26:,.0f} in 2026. "
        "Review streaming services, SaaS tools, and gym memberships for overlap. "
        "Canceling just 3–4 unused subscriptions can save $50–150/month."))

    # 4. AI Tools
    ai25 = exp25[exp25["merchant"].str.lower().str.contains("|".join(AI_KEYWORDS), na=False)]["expense"].sum()
    ai26 = exp26[exp26["merchant"].str.lower().str.contains("|".join(AI_KEYWORDS), na=False)]["expense"].sum()
    if ai26 > 100:
        recs.append(("MEDIUM", "🤖 AI Tool Consolidation Opportunity",
            f"AI & tech services cost ${ai26:,.0f} YTD 2026 (vs ${ai25:,.0f} full year 2025). "
            "Evaluate whether you use multiple AI assistants (ChatGPT, Claude, Grok, Copilot) — "
            "pick your primary and cancel duplicates."))

    # 5. Shopping
    shop25 = exp25_jm[exp25_jm["category"]=="Shopping"]["expense"].sum()
    shop26 = exp26_jm[exp26_jm["category"]=="Shopping"]["expense"].sum()
    if shop26 > shop25 * 1.15:
        recs.append(("HIGH", "🛒 Shopping Spend Spiked",
            f"General merchandise/shopping jumped ${shop26-shop25:,.0f} YoY "
            f"(${shop25:,.0f} → ${shop26:,.0f}). "
            "Consider a 30-day wishlist rule before non-essential purchases."))

    # 6. Bank Fees
    fees25 = exp25["category"].eq("Bank Fees").sum()
    fees26 = exp26["category"].eq("Bank Fees").sum()
    fee_amt26 = exp26[exp26["category"]=="Bank Fees"]["expense"].sum()
    if fee_amt26 > 50:
        recs.append(("HIGH", "🏦 Eliminate Bank Fees",
            f"${fee_amt26:,.0f} paid in bank fees/service charges YTD 2026. "
            "Switch to a no-fee checking account (e.g., Ally, Marcus, Fidelity Cash Management) "
            "to eliminate these entirely."))

    # 7. Healthcare
    hc25 = exp25_jm[exp25_jm["category"]=="Healthcare"]["expense"].sum()
    hc26 = exp26_jm[exp26_jm["category"]=="Healthcare"]["expense"].sum()
    if hc26 > 200:
        recs.append(("LOW", "🏥 Max Your HSA",
            f"Healthcare spending is ${hc26:,.0f} Jan–May 2026. "
            "If you have an HSA-eligible plan, maximize contributions ($4,300 individual / $8,550 family for 2025) "
            "to pay medical expenses tax-free."))

    # 8. Travel
    trav25 = exp25_jm[exp25_jm["category"]=="Travel"]["expense"].sum()
    trav26 = exp26_jm[exp26_jm["category"]=="Travel"]["expense"].sum()
    if trav26 > 500:
        recs.append(("LOW", "✈️ Leverage Travel Rewards",
            f"Travel spend: ${trav26:,.0f} YTD. If you're not using a travel rewards card, "
            "switching could earn 2–5x points on flights and hotels — worth $200–500/yr in free travel."))

    # 9. Big wins
    cats_down = []
    for cat in exp25_jm.groupby("category")["expense"].sum().index:
        v25 = exp25_jm[exp25_jm["category"]==cat]["expense"].sum()
        v26 = exp26_jm[exp26_jm["category"]==cat]["expense"].sum()
        if v25 > 200 and v26 < v25 * 0.8:
            cats_down.append((cat, v25, v26, v25-v26))
    if cats_down:
        cats_down.sort(key=lambda x: -x[3])
        top = cats_down[0]
        recs.append(("LOW", f"🎉 Win: {top[0]} Spending Down",
            f"Great progress on {top[0]}: down ${top[3]:,.0f} YoY "
            f"(${top[1]:,.0f} → ${top[2]:,.0f} Jan–May). Keep it up!"))

    # 10. Emergency fund check
    recs.append(("LOW", "💰 Automate Your Savings",
        f"With avg monthly spend of ${avg26_mo:,.0f}, your emergency fund target should be "
        f"${avg26_mo*3:,.0f}–${avg26_mo*6:,.0f} (3–6 months). "
        "Automate a monthly transfer to a HYSA on payday to build this buffer hands-free."))

    return recs

recommendations = build_recommendations()

# ─── PRIORITY BADGE COLORS ────────────────────────────────────────────────────
BADGE_COLORS = {"HIGH": RED, "MEDIUM": YELLOW, "LOW": GREEN}

def rec_html(recs):
    html = ""
    for priority, title, body in recs:
        color = BADGE_COLORS.get(priority, MUTED)
        html += f"""
        <div class="rec-card">
          <div class="rec-header">
            <span class="badge" style="background:{color}20; color:{color}; border:1px solid {color}40;">{priority}</span>
            <h3 class="rec-title">{title}</h3>
          </div>
          <p class="rec-body">{body}</p>
        </div>"""
    return html

# ─── STAT CARDS HTML ─────────────────────────────────────────────────────────
yoy_color = RED if yoy_change > 0 else GREEN
yoy_arrow = "↑" if yoy_change > 0 else "↓"

stat_cards = f"""
<div class="stats-grid">
  <div class="stat-card">
    <div class="stat-label">2025 Full Year Spend</div>
    <div class="stat-value">${total25_fy:,.0f}</div>
    <div class="stat-sub">Jan–Dec 2025</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">2025 Jan–May Spend</div>
    <div class="stat-value">${total25_jm:,.0f}</div>
    <div class="stat-sub">Comparable period</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">2026 YTD Spend</div>
    <div class="stat-value">${total26_ytd:,.0f}</div>
    <div class="stat-sub">Jan–May 2026</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">YoY Change (Jan–May)</div>
    <div class="stat-value" style="color:{yoy_color}">{yoy_arrow} {abs(yoy_change):.1f}%</div>
    <div class="stat-sub">vs same period 2025</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Avg Monthly (2025)</div>
    <div class="stat-value">${avg25_mo:,.0f}</div>
    <div class="stat-sub">Excl. one-time taxes</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Avg Monthly (2026)</div>
    <div class="stat-value">${avg26_mo:,.0f}</div>
    <div class="stat-sub">Excl. one-time taxes</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Top Category 2025</div>
    <div class="stat-value" style="font-size:1.1rem">{top_cat25}</div>
    <div class="stat-sub">${exp25.groupby("category")["expense"].sum()[top_cat25]:,.0f} full year</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Top Category 2026</div>
    <div class="stat-value" style="font-size:1.1rem">{top_cat26}</div>
    <div class="stat-sub">${exp26.groupby("category")["expense"].sum()[top_cat26]:,.0f} YTD</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Subscriptions 2025</div>
    <div class="stat-value">${sub25:,.0f}</div>
    <div class="stat-sub">Full year total</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Subscriptions 2026</div>
    <div class="stat-value">${sub26:,.0f}</div>
    <div class="stat-sub">YTD total</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Dining Out 2025</div>
    <div class="stat-value">${din25:,.0f}</div>
    <div class="stat-sub">Full year total</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Dining Out 2026</div>
    <div class="stat-value">${din26:,.0f}</div>
    <div class="stat-sub">YTD total</div>
  </div>
  <div class="stat-card" style="border:1px solid #f5a62360">
    <div class="stat-label" style="color:#f5a623">Tax Payments 2025</div>
    <div class="stat-value" style="color:#f5a623">${tax25:,.0f}</div>
    <div class="stat-sub">IRS + state — one-time, excl. from avg</div>
  </div>
  <div class="stat-card" style="border:1px solid #f5a62360">
    <div class="stat-label" style="color:#f5a623">Tax Payments 2026</div>
    <div class="stat-value" style="color:#f5a623">${tax26:,.0f}</div>
    <div class="stat-sub">IRS + FTB — one-time, excl. from avg</div>
  </div>
</div>
"""

# ─── BUILD HTML ───────────────────────────────────────────────────────────────
now = datetime.now().strftime("%B %d, %Y at %I:%M %p")

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Financial Analysis: 2025 vs 2026</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --bg: {BG};
    --card: {CARD};
    --accent: {ACCENT};
    --text: {TEXT};
    --muted: {MUTED};
    --border: {BORDER};
    --red: {RED};
    --green: {GREEN};
    --yellow: {YELLOW};
  }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    line-height: 1.6;
    min-height: 100vh;
  }}

  /* ── Header ── */
  .header {{
    background: linear-gradient(135deg, {CARD} 0%, #13162b 100%);
    border-bottom: 1px solid {BORDER};
    padding: 2.5rem 2rem 2rem;
    text-align: center;
  }}
  .header h1 {{
    font-size: clamp(1.5rem, 4vw, 2.4rem);
    font-weight: 700;
    background: linear-gradient(90deg, {ACCENT}, {TEAL});
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: .4rem;
  }}
  .header .subtitle {{
    color: {MUTED};
    font-size: .95rem;
  }}

  /* ── Layout ── */
  .container {{
    max-width: 1400px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
  }}

  .section-title {{
    font-size: 1.1rem;
    font-weight: 600;
    color: {ACCENT};
    text-transform: uppercase;
    letter-spacing: .08em;
    margin: 2.5rem 0 1rem;
    padding-bottom: .5rem;
    border-bottom: 1px solid {BORDER};
  }}

  /* ── Stat Cards ── */
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
  }}
  .stat-card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 1.2rem 1rem;
    transition: border-color .2s, transform .2s;
  }}
  .stat-card:hover {{
    border-color: {ACCENT};
    transform: translateY(-2px);
  }}
  .stat-label {{
    font-size: .72rem;
    color: {MUTED};
    text-transform: uppercase;
    letter-spacing: .06em;
    margin-bottom: .3rem;
  }}
  .stat-value {{
    font-size: 1.45rem;
    font-weight: 700;
    color: {TEXT};
    line-height: 1.2;
  }}
  .stat-sub {{
    font-size: .72rem;
    color: {MUTED};
    margin-top: .2rem;
  }}

  /* ── Chart Cards ── */
  .chart-card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 1rem;
    margin-bottom: 1.25rem;
    overflow: hidden;
  }}
  .chart-card .js-plotly-plot {{
    border-radius: 10px;
  }}

  .charts-2col {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.25rem;
  }}
  @media (max-width: 900px) {{
    .charts-2col {{ grid-template-columns: 1fr; }}
  }}

  /* ── Recommendations ── */
  .rec-card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    margin-bottom: .9rem;
    transition: border-color .2s;
  }}
  .rec-card:hover {{ border-color: {ACCENT}; }}
  .rec-header {{
    display: flex;
    align-items: center;
    gap: .75rem;
    margin-bottom: .5rem;
  }}
  .badge {{
    font-size: .65rem;
    font-weight: 700;
    padding: .2rem .55rem;
    border-radius: 999px;
    letter-spacing: .05em;
    white-space: nowrap;
  }}
  .rec-title {{
    font-size: 1rem;
    font-weight: 600;
    color: {TEXT};
  }}
  .rec-body {{
    font-size: .88rem;
    color: {MUTED};
    line-height: 1.65;
  }}

  /* ── Footer ── */
  .footer {{
    text-align: center;
    padding: 2rem;
    color: {MUTED};
    font-size: .8rem;
    border-top: 1px solid {BORDER};
    margin-top: 3rem;
  }}
</style>
</head>
<body>

<div class="header">
  <h1>💳 Financial Analysis: 2025 vs 2026</h1>
  <div class="subtitle">Personal spending report &nbsp;·&nbsp; Jan–May comparison &nbsp;·&nbsp; Generated {now}</div>
</div>

<div class="container">

  <!-- STAT CARDS -->
  <div class="section-title">📊 Key Metrics at a Glance</div>
  {stat_cards}

  <!-- SECTION: TRENDS -->
  <div class="section-title">📈 Spending Trends</div>

  <div class="chart-card">{c1}</div>

  <div class="charts-2col">
    <div class="chart-card">{c5}</div>
    <div class="chart-card">{c6}</div>
  </div>

  <div class="chart-card">{c4}</div>
  <div class="chart-card">{c2}</div>
  <div class="chart-card">{c3}</div>

  <!-- SECTION: MERCHANTS -->
  <div class="section-title">🏪 Merchant Intelligence</div>

  <div class="chart-card">{c7}</div>
  <div class="chart-card">{c8}</div>

  <!-- SECTION: SUBSCRIPTIONS & AI -->
  <div class="section-title">🔄 Subscriptions & AI Tools</div>

  <div class="chart-card">{c9}</div>
  <div class="chart-card">{c10}</div>

  <!-- SECTION: BEHAVIOR -->
  <div class="section-title">🧠 Spending Behavior (2026)</div>

  <div class="chart-card">{c11}</div>
  <div class="chart-card">{c12}</div>

  <!-- SECTION: RECOMMENDATIONS -->
  <div class="section-title">💡 Smart Recommendations</div>
  {rec_html(recommendations)}

</div>

<div class="footer">
  Generated {now} &nbsp;·&nbsp;
  2025 transactions: {n_tx25:,} &nbsp;·&nbsp;
  2026 transactions: {n_tx26:,} &nbsp;·&nbsp;
  Categories skipped: Securities Trades, Transfers, Credit Card Payments, Retirement Contributions, Refunds &amp; Reimbursements, Uncategorized
</div>

</body>
</html>
"""

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Report written: {OUTPUT}")
print(f"REPORT_DONE:{OUTPUT}")
