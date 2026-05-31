#!/usr/bin/env python3
"""
Financial Transaction Analyzer
Generates a comprehensive Plotly HTML report with charts + recommendations.
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json
from datetime import datetime
from collections import defaultdict
import re

CSV_PATH = "/Users/jasleenkaur/AgenticHub/Persgraph/persgraph/data/transactions_2026.csv"
OUTPUT_PATH = "/Users/jasleenkaur/AgenticHub/Persgraph/persgraph/financial_report.html"

# ─── Load & Clean ───────────────────────────────────────────────────────────

df = pd.read_csv(CSV_PATH)
df.columns = [c.strip() for c in df.columns]
df['Date'] = pd.to_datetime(df['Date'])
df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
df['Month'] = df['Date'].dt.to_period('M').astype(str)
df['Week'] = df['Date'].dt.isocalendar().week
df['DayOfWeek'] = df['Date'].dt.day_name()

# ─── Category Remapping (clean up + group) ──────────────────────────────────

SKIP_CATEGORIES = {
    'Securities Trades', 'Transfers', 'Credit Card Payments',
    'Retirement Contributions', 'Refunds & Reimbursements'
}

# Tax payments: included in TOTAL expenses but excluded from monthly average (one-time anomalies)
TAX_CATEGORY = 'Taxes'
TAX_DISPLAY = 'Taxes (One-Time)'

REMAP = {
    'Restaurants': 'Dining Out',
    'Groceries': 'Groceries',
    'General Merchandise': 'Shopping',
    'Online Services': 'Online Services / AI',
    'Entertainment': 'Entertainment',
    'Travel': 'Travel',
    'Gasoline/Fuel': 'Gas & Fuel',
    'Healthcare/Medical': 'Healthcare',
    'Insurance': 'Insurance',
    'Dues & Subscriptions': 'Subscriptions',
    'Service Charges/Fees': 'Bank Fees',
    'Telephone': 'Phone',
    'Utilities': 'Utilities',
    'Personal Care': 'Personal Care',
    'Home Improvement': 'Home',
    'Home Maintenance': 'Home',
    'Automotive': 'Automotive',
    'ATM/Cash': 'Cash/ATM',
    'Other Expenses': 'Other',
    'Loans': 'Loans',
    'Mortgages': 'Housing (Mortgage)',
    'Taxes': 'Taxes (One-Time)',
    'Clothing/Shoes': 'Clothing',
    'Deposits': 'Income',
    'Interest': 'Interest Income',
    'Investment Income': 'Investment Income',
    'Education': 'Education',
    'Checks': 'Checks',
    'Hobbies': 'Hobbies',
    'Printing': 'Other',
    'Electronics': 'Electronics',
}

df['CleanCategory'] = df['Category'].map(REMAP).fillna(df['Category'])

# Spending only (negative amounts, exclude noise categories)
expenses_df = df[
    (df['Amount'] < 0) &
    (~df['Category'].isin(SKIP_CATEGORIES))
].copy()
expenses_df['AbsAmount'] = expenses_df['Amount'].abs()

# Tax entries: tracked separately, excluded from monthly avg
tax_df = expenses_df[expenses_df['Category'] == TAX_CATEGORY].copy()
tax_total = tax_df['AbsAmount'].sum()

# For monthly averages: exclude tax payments
expenses_no_tax = expenses_df[expenses_df['Category'] != TAX_CATEGORY].copy()

# Income only
income_df = df[
    (df['Amount'] > 0) &
    (df['Category'].isin(['Deposits', 'Interest', 'Investment Income']))
].copy()

# All spending including transfers/CC payments for cash flow
all_out = df[df['Amount'] < 0].copy()
all_in = df[df['Amount'] > 0].copy()

# ─── Color Palette ──────────────────────────────────────────────────────────

COLORS = px.colors.qualitative.Bold
BG = '#0f1117'
CARD = '#1a1d27'
TEXT = '#e8e8f0'
ACCENT = '#6c8ef5'

LAYOUT_DEFAULTS = dict(
    paper_bgcolor=BG,
    plot_bgcolor=CARD,
    font=dict(color=TEXT, family='Inter, sans-serif'),
    margin=dict(l=40, r=40, t=60, b=40),
)

def styled(fig, title=''):
    fig.update_layout(**LAYOUT_DEFAULTS, title=dict(text=title, font=dict(size=16, color=ACCENT)))
    fig.update_xaxes(gridcolor='#2a2d3a', zeroline=False)
    fig.update_yaxes(gridcolor='#2a2d3a', zeroline=False)
    return fig

# ─── Chart 1: Monthly Spending by Category (Stacked Bar) ────────────────────

monthly_cat = expenses_df.groupby(['Month', 'CleanCategory'])['AbsAmount'].sum().reset_index()
pivot = monthly_cat.pivot_table(index='Month', columns='CleanCategory', values='AbsAmount', fill_value=0)
pivot = pivot.sort_index()

fig1 = go.Figure()
for i, col in enumerate(pivot.columns):
    fig1.add_trace(go.Bar(
        name=col,
        x=pivot.index.tolist(),
        y=pivot[col].tolist(),
        marker_color=COLORS[i % len(COLORS)],
        hovertemplate=f'<b>{col}</b><br>%{{x}}: $%{{y:,.2f}}<extra></extra>'
    ))
fig1.update_layout(barmode='stack')
styled(fig1, '📊 Monthly Spending by Category')

# ─── Chart 2: Category Pie / Donut ──────────────────────────────────────────

cat_totals = expenses_df.groupby('CleanCategory')['AbsAmount'].sum().sort_values(ascending=False)
fig2 = go.Figure(go.Pie(
    labels=cat_totals.index.tolist(),
    values=cat_totals.values.tolist(),
    hole=0.45,
    marker=dict(colors=COLORS),
    hovertemplate='<b>%{label}</b><br>$%{value:,.2f} (%{percent})<extra></extra>',
    textinfo='label+percent',
    textfont=dict(size=11)
))
styled(fig2, '🍩 Spending Breakdown (All Months)')

# ─── Chart 3: Top 15 Merchants Treemap ──────────────────────────────────────

merchant_totals = expenses_df.groupby('Description')['AbsAmount'].sum().sort_values(ascending=False).head(20)
fig3 = go.Figure(go.Treemap(
    labels=merchant_totals.index.tolist(),
    values=merchant_totals.values.tolist(),
    parents=[''] * len(merchant_totals),
    marker=dict(
        colorscale='Blues',
        colors=merchant_totals.values.tolist(),
        showscale=True,
        colorbar=dict(title='$')
    ),
    hovertemplate='<b>%{label}</b><br>$%{value:,.2f}<extra></extra>',
    texttemplate='<b>%{label}</b><br>$%{value:,.0f}',
))
styled(fig3, '🌳 Top 20 Merchants by Spend')

# ─── Chart 4: Day of Week Heatmap ────────────────────────────────────────────

dow_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
dow_data = expenses_df.groupby(['DayOfWeek', 'CleanCategory'])['AbsAmount'].sum().reset_index()
dow_pivot = dow_data.pivot_table(index='DayOfWeek', columns='CleanCategory', values='AbsAmount', fill_value=0)
dow_pivot = dow_pivot.reindex([d for d in dow_order if d in dow_pivot.index])

fig4 = go.Figure(go.Heatmap(
    z=dow_pivot.values.tolist(),
    x=dow_pivot.columns.tolist(),
    y=dow_pivot.index.tolist(),
    colorscale='Viridis',
    hovertemplate='<b>%{y} — %{x}</b><br>$%{z:,.2f}<extra></extra>',
    colorbar=dict(title='$')
))
styled(fig4, '📅 Spending Heatmap: Day of Week × Category')
fig4.update_layout(xaxis_tickangle=-45)

# ─── Chart 5: Daily Spending Line ────────────────────────────────────────────

daily = expenses_df.groupby('Date')['AbsAmount'].sum().reset_index()
daily_7ma = daily.set_index('Date')['AbsAmount'].rolling(7).mean().reset_index()

fig5 = go.Figure()
fig5.add_trace(go.Bar(
    x=daily['Date'], y=daily['AbsAmount'],
    name='Daily Spend',
    marker_color='rgba(108,142,245,0.4)',
    hovertemplate='%{x|%b %d}: $%{y:,.2f}<extra></extra>'
))
fig5.add_trace(go.Scatter(
    x=daily_7ma['Date'], y=daily_7ma['AbsAmount'],
    name='7-Day Avg',
    line=dict(color='#f5a623', width=2),
    hovertemplate='7d avg: $%{y:,.2f}<extra></extra>'
))
styled(fig5, '📈 Daily Spending with 7-Day Moving Average')

# ─── Chart 6: Subscriptions & Recurring ─────────────────────────────────────

sub_keywords = ['Netflix', 'Spotify', 'Hbo Max', 'Disney Plus', 'Amazon Prime',
                'Sling Tv', 'Xbox', 'Chatgpt', 'Claude', 'Anthropic', 'Medium',
                'Oura Ring', 'Google *fi', 'Vonage', 'Adt Security', 'Hippo Insurance',
                'Geico', 'Uber One', 'Microsoft', 'Google *cloud', 'Google *wyze',
                'Google *grok', 'Forhims', 'Transunion', 'Joinfansclub', 'Findfansclub',
                'Paddle.net', 'Ring Solo', 'Northwest Federal', 'Fastrak', 'At&t',
                'Aig', 'Fitbit', 'Amazon Kindle']

def is_sub(desc):
    return any(k.lower() in desc.lower() for k in sub_keywords)

sub_df = expenses_df[expenses_df['Description'].apply(is_sub)].copy()
sub_monthly = sub_df.groupby(['Month', 'Description'])['AbsAmount'].sum().reset_index()
sub_total = sub_df.groupby('Description')['AbsAmount'].sum().sort_values(ascending=True)

fig6 = go.Figure(go.Bar(
    x=sub_total.values.tolist(),
    y=sub_total.index.tolist(),
    orientation='h',
    marker=dict(
        color=sub_total.values.tolist(),
        colorscale='Sunset',
        showscale=True,
        colorbar=dict(title='Total $')
    ),
    hovertemplate='<b>%{y}</b>: $%{x:,.2f}<extra></extra>'
))
styled(fig6, '🔁 Subscriptions & Recurring Expenses')
fig6.update_layout(height=500)

# ─── Chart 7: Income vs Spending ─────────────────────────────────────────────

monthly_inc = income_df.groupby('Month')['Amount'].sum().reset_index()
monthly_exp = expenses_df.groupby('Month')['AbsAmount'].sum().reset_index()

months_all = sorted(set(monthly_inc['Month'].tolist() + monthly_exp['Month'].tolist()))
inc_map = dict(zip(monthly_inc['Month'], monthly_inc['Amount']))
exp_map = dict(zip(monthly_exp['Month'], monthly_exp['AbsAmount']))

fig7 = go.Figure()
fig7.add_trace(go.Bar(
    name='Income (Deposits + Interest)',
    x=months_all,
    y=[inc_map.get(m, 0) for m in months_all],
    marker_color='#4ecb71',
    hovertemplate='Income %{x}: $%{y:,.2f}<extra></extra>'
))
fig7.add_trace(go.Bar(
    name='Expenses',
    x=months_all,
    y=[exp_map.get(m, 0) for m in months_all],
    marker_color='#e05c5c',
    hovertemplate='Expenses %{x}: $%{y:,.2f}<extra></extra>'
))
styled(fig7, '💰 Income vs Expenses by Month')
fig7.update_layout(barmode='group')

# ─── Chart 8: AI / Tech Subscriptions Focused ────────────────────────────────

ai_keywords = ['Chatgpt', 'Claude', 'Anthropic', 'Google *grok', 'Microsoft',
               'Google *cloud', 'Google *fi', 'Google *wyze']
ai_df = expenses_df[expenses_df['Description'].apply(
    lambda d: any(k.lower() in d.lower() for k in ai_keywords)
)]
ai_total = ai_df.groupby('Description')['AbsAmount'].sum().sort_values(ascending=False)

fig8 = go.Figure(go.Bar(
    x=ai_total.index.tolist(),
    y=ai_total.values.tolist(),
    marker=dict(color=COLORS[:len(ai_total)]),
    hovertemplate='<b>%{x}</b>: $%{y:,.2f}<extra></extra>'
))
styled(fig8, '🤖 AI & Tech Services Spending')

# ─── Chart 9: Dining Breakdown ────────────────────────────────────────────────

dining_df = expenses_df[expenses_df['CleanCategory'] == 'Dining Out'].copy()
top_dining = dining_df.groupby('Description')['AbsAmount'].sum().sort_values(ascending=False).head(15)
fig9 = go.Figure(go.Bar(
    x=top_dining.index.tolist(),
    y=top_dining.values.tolist(),
    marker=dict(
        color=top_dining.values.tolist(),
        colorscale='Reds',
        showscale=True
    ),
    hovertemplate='<b>%{x}</b>: $%{y:,.2f}<extra></extra>'
))
styled(fig9, '🍔 Top Dining Spots')
fig9.update_layout(xaxis_tickangle=-45)

# ─── Summary Stats ────────────────────────────────────────────────────────────

total_exp = expenses_df['AbsAmount'].sum()
total_inc = income_df['Amount'].sum()
avg_daily = expenses_no_tax.groupby('Date')['AbsAmount'].sum().mean()
top_cat = cat_totals.index[0]
top_cat_amt = cat_totals.iloc[0]
sub_total_amt = sub_df['AbsAmount'].sum()
dining_total = dining_df['AbsAmount'].sum()
months_covered = df['Month'].nunique()
# Monthly avg excludes one-time tax payments
avg_monthly_exp = expenses_no_tax['AbsAmount'].sum() / months_covered if months_covered else 0
tax_total_display = tax_total

# Recurring % 
rec_pct = (sub_total_amt / total_exp * 100) if total_exp > 0 else 0

# ─── Recommendations ─────────────────────────────────────────────────────────

recommendations = []

# 1. Dining
if dining_total > 1000:
    recommendations.append({
        'icon': '🍔',
        'title': 'High Dining Spend',
        'amount': f'${dining_total:,.0f} total',
        'detail': f'Dining out is your top or near-top expense at ${dining_total:,.0f}. '
                  f'Top spots: {", ".join(top_dining.head(3).index.tolist())}. '
                  f'Meal prepping 2x/week could save $200-400/month.',
        'priority': 'high'
    })

# 2. Subscriptions
if sub_total_amt > 500:
    recommendations.append({
        'icon': '🔁',
        'title': 'Subscription Audit Needed',
        'amount': f'${sub_total_amt:,.0f} total',
        'detail': f'You\'re spending ${sub_total_amt:,.0f} on subscriptions/recurring. '
                  f'Review duplicates (multiple streaming services, AI tools). '
                  f'Potential savings: $50-100/month by consolidating.',
        'priority': 'high'
    })

# 3. AI tools
ai_total_amt = ai_df['AbsAmount'].sum()
if ai_total_amt > 50:
    recommendations.append({
        'icon': '🤖',
        'title': 'AI Tool Consolidation',
        'amount': f'${ai_total_amt:,.0f} total',
        'detail': f'Paying for ChatGPT, Claude, Grok, and Google Fi separately. '
                  f'Consider consolidating to 1-2 primary AI tools. '
                  f'You\'re building SwarmForge — maybe self-host one layer?',
        'priority': 'medium'
    })

# 4. Costco/Wholesale
costco_df = expenses_df[expenses_df['Description'].str.contains('Costco', case=False, na=False)]
costco_total = costco_df['AbsAmount'].sum()
if costco_total > 500:
    recommendations.append({
        'icon': '🏪',
        'title': 'Bulk Purchase Spikes',
        'amount': f'${costco_total:,.0f} total',
        'detail': f'Costco spend is ${costco_total:,.0f}. Large single transactions suggest '
                  f'bulk buying — this is generally smart but watch for impulse buys. '
                  f'Track what actually gets used.',
        'priority': 'low'
    })

# 5. Late fees / bank charges
fees_df = expenses_df[expenses_df['Description'].str.contains('Late Fee|Interest Charge|Service Charge', case=False, na=False)]
fees_total = fees_df['AbsAmount'].sum()
if fees_total > 20:
    recommendations.append({
        'icon': '⚠️',
        'title': 'Avoidable Bank Fees',
        'amount': f'${fees_total:,.0f}',
        'detail': f'Late fees and interest charges totaling ${fees_total:,.0f}. '
                  f'Set up autopay on all cards — this is pure waste.',
        'priority': 'high'
    })

# 6. Doordash/Uber Eats
delivery_df = expenses_df[expenses_df['Description'].str.contains('Doordash|Uber Eats|Grubhub', case=False, na=False)]
delivery_total = delivery_df['AbsAmount'].sum()
if delivery_total > 100:
    recommendations.append({
        'icon': '🛵',
        'title': 'Food Delivery Premium',
        'amount': f'${delivery_total:,.0f} total',
        'detail': f'${delivery_total:,.0f} on Doordash/Uber Eats. Delivery fees + tips '
                  f'add 30-40% vs pickup. Picking up from same restaurants saves significantly.',
        'priority': 'medium'
    })

# 7. Amazon spend
amzn_df = expenses_df[expenses_df['Description'].str.contains('Amazon', case=False, na=False)]
amzn_total = amzn_df['AbsAmount'].sum()
if amzn_total > 200:
    recommendations.append({
        'icon': '📦',
        'title': 'Amazon Impulse Control',
        'amount': f'${amzn_total:,.0f} total',
        'detail': f'${amzn_total:,.0f} across Amazon Marketplace, Prime Video, Kindle. '
                  f'Try the 24-hour cart rule: add to cart, buy next day only if still needed.',
        'priority': 'medium'
    })

# ─── Build HTML ──────────────────────────────────────────────────────────────

def fig_to_html(fig):
    return fig.to_html(full_html=False, include_plotlyjs=False, config={'responsive': True})

priority_badge = {
    'high': '<span style="background:#e05c5c;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold">HIGH</span>',
    'medium': '<span style="background:#f5a623;color:#000;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold">MEDIUM</span>',
    'low': '<span style="background:#4ecb71;color:#000;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold">LOW</span>',
}

rec_html = ''
for r in recommendations:
    rec_html += f'''
    <div class="rec-card" style="border-left:4px solid {'#e05c5c' if r['priority']=='high' else '#f5a623' if r['priority']=='medium' else '#4ecb71'}">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <h3 style="margin:0;font-size:16px">{r['icon']} {r['title']}</h3>
            <div style="display:flex;gap:8px;align-items:center">
                <span style="color:#6c8ef5;font-weight:bold;font-size:15px">{r['amount']}</span>
                {priority_badge[r['priority']]}
            </div>
        </div>
        <p style="margin:0;color:#b0b3c8;font-size:14px;line-height:1.6">{r['detail']}</p>
    </div>'''

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Financial Report — Jan–May 2026</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: {BG}; color: {TEXT}; font-family: 'Inter', system-ui, sans-serif; padding: 24px; }}
  h1 {{ font-size: 28px; font-weight: 700; color: {ACCENT}; margin-bottom: 4px; }}
  h2 {{ font-size: 20px; font-weight: 600; color: {ACCENT}; margin: 32px 0 16px; }}
  .subtitle {{ color: #888; font-size: 14px; margin-bottom: 32px; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }}
  .stat-card {{ background: {CARD}; border-radius: 12px; padding: 20px; border: 1px solid #2a2d3a; }}
  .stat-label {{ font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 0.8px; }}
  .stat-value {{ font-size: 26px; font-weight: 700; color: {ACCENT}; margin-top: 6px; }}
  .stat-sub {{ font-size: 12px; color: #666; margin-top: 4px; }}
  .chart-card {{ background: {CARD}; border-radius: 12px; padding: 20px; margin-bottom: 24px; border: 1px solid #2a2d3a; }}
  .chart-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }}
  .rec-card {{ background: {CARD}; border-radius: 12px; padding: 20px; margin-bottom: 16px; border: 1px solid #2a2d3a; }}
  .section-divider {{ border: none; border-top: 1px solid #2a2d3a; margin: 32px 0; }}
  @media (max-width: 768px) {{ .chart-grid {{ grid-template-columns: 1fr; }} }}
  .badge {{ display: inline-block; background: #2a2d3a; color: #888; padding: 3px 10px; border-radius: 20px; font-size: 12px; margin-right: 8px; }}
</style>
</head>
<body>

<h1>📊 Financial Report</h1>
<p class="subtitle">Jan 1 – May 25, 2026 &nbsp;·&nbsp; {len(df):,} transactions &nbsp;·&nbsp; {months_covered} months &nbsp;·&nbsp; Generated {datetime.now().strftime("%b %d, %Y")}</p>

<!-- STAT CARDS -->
<div class="stats-grid">
  <div class="stat-card">
    <div class="stat-label">Total Expenses</div>
    <div class="stat-value">${total_exp:,.0f}</div>
    <div class="stat-sub">Avg ${avg_monthly_exp:,.0f}/month</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Income (Deposits)</div>
    <div class="stat-value">${total_inc:,.0f}</div>
    <div class="stat-sub">Salary + Interest</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Avg Daily Spend</div>
    <div class="stat-value">${avg_daily:,.0f}</div>
    <div class="stat-sub">Excl. transfers, trades & taxes</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Biggest Category</div>
    <div class="stat-value">{top_cat}</div>
    <div class="stat-sub">${top_cat_amt:,.0f} total</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Subscriptions</div>
    <div class="stat-value">${sub_total_amt:,.0f}</div>
    <div class="stat-sub">{rec_pct:.1f}% of expenses</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Dining Out</div>
    <div class="stat-value">${dining_total:,.0f}</div>
    <div class="stat-sub">Restaurants + delivery</div>
  </div>
  <div class="stat-card" style="border-color:#f5a623">
    <div class="stat-label">Tax Payments (One-Time)</div>
    <div class="stat-value" style="color:#f5a623">${tax_total_display:,.0f}</div>
    <div class="stat-sub">IRS + state — excluded from avg</div>
  </div>
</div>

<hr class="section-divider">

<!-- CHARTS -->
<h2>📈 Spending Trends</h2>

<div class="chart-card">
{fig_to_html(fig1)}
</div>

<div class="chart-grid">
  <div class="chart-card">{fig_to_html(fig2)}</div>
  <div class="chart-card">{fig_to_html(fig7)}</div>
</div>

<div class="chart-card">
{fig_to_html(fig5)}
</div>

<hr class="section-divider">
<h2>🏪 Merchant Analysis</h2>

<div class="chart-card">
{fig_to_html(fig3)}
</div>

<div class="chart-grid">
  <div class="chart-card">{fig_to_html(fig9)}</div>
  <div class="chart-card">{fig_to_html(fig8)}</div>
</div>

<hr class="section-divider">
<h2>📅 Behavioral Patterns</h2>

<div class="chart-card">
{fig_to_html(fig4)}
</div>

<div class="chart-card">
{fig_to_html(fig6)}
</div>

<hr class="section-divider">
<h2>💡 Recommendations</h2>
<p style="color:#888;font-size:13px;margin-bottom:20px">Based on your Jan–May 2026 transaction data. Prioritized by impact.</p>

{rec_html}

<hr class="section-divider">
<p style="color:#444;font-size:12px;text-align:center">Generated by OpenClaw Financial Analyzer · Data: {len(df):,} transactions · {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>

</body>
</html>'''

with open(OUTPUT_PATH, 'w') as f:
    f.write(html)

print(f"✅ Report generated: {OUTPUT_PATH}")
print(f"   Transactions analyzed: {len(df):,}")
print(f"   Expense categories: {expenses_df['CleanCategory'].nunique()}")
print(f"   Date range: {df['Date'].min().date()} → {df['Date'].max().date()}")
print(f"   Total expenses: ${total_exp:,.2f}")
print(f"   Recommendations: {len(recommendations)}")
