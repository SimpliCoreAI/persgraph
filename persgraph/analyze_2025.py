#!/usr/bin/env python3
"""
Financial Transaction Analyzer — 2025 Full-Year Report
Generates a comprehensive Plotly HTML report with 12 charts + recommendations.
Output: financial_report_2025.html
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from datetime import datetime

FINANCE_DIR = Path(__file__).parent
CSV_PATH = FINANCE_DIR / "data" / "transactions_2025.csv"
OUTPUT_PATH = FINANCE_DIR / "financial_report_2025.html"

# ─── Load & Clean ────────────────────────────────────────────────────────────

df = pd.read_csv(CSV_PATH)
df.columns = [c.strip() for c in df.columns]
df['Date'] = pd.to_datetime(df['Date'])
df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
df['Month'] = df['Date'].dt.to_period('M').astype(str)
df['DayOfWeek'] = df['Date'].dt.day_name()

# ─── Category Remapping ──────────────────────────────────────────────────────

SKIP_CATEGORIES = {
    'Securities Trades', 'Transfers', 'Credit Card Payments',
    'Retirement Contributions', 'Refunds & Reimbursements', 'Uncategorized'
}

TAX_CATEGORY = 'Taxes'

REMAP = {
    'Restaurants': 'Dining Out',
    'Groceries': 'Groceries',
    'General Merchandise': 'Shopping',
    'Online Services': 'Online Services/AI',
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
    'Electronics': 'Electronics',
    'Rent': 'Rent',
}

df['CleanCategory'] = df['Category'].map(REMAP).fillna(df['Category'])

# Spending only (negative = expense, exclude noise)
expenses_df = df[
    (df['Amount'] < 0) &
    (~df['Category'].isin(SKIP_CATEGORIES))
].copy()
expenses_df['AbsAmount'] = expenses_df['Amount'].abs()

# Tax entries tracked separately, excluded from monthly averages
tax_df = expenses_df[expenses_df['Category'] == TAX_CATEGORY].copy()
tax_total = tax_df['AbsAmount'].sum()
expenses_no_tax = expenses_df[expenses_df['Category'] != TAX_CATEGORY].copy()

# Income
income_df = df[
    (df['Amount'] > 0) &
    (df['Category'].isin(['Deposits', 'Interest', 'Investment Income']))
].copy()

# ─── Color Palette ────────────────────────────────────────────────────────────

COLORS = px.colors.qualitative.Bold
BG    = '#0f1117'
CARD  = '#1a1d27'
TEXT  = '#e8e8f0'
ACCENT = '#6c8ef5'

LAYOUT_DEFAULTS = dict(
    paper_bgcolor=BG,
    plot_bgcolor=CARD,
    font=dict(color=TEXT, family='Inter, sans-serif'),
    margin=dict(l=40, r=40, t=60, b=40),
)

def styled(fig, title=''):
    fig.update_layout(
        **LAYOUT_DEFAULTS,
        title=dict(text=title, font=dict(size=16, color=ACCENT))
    )
    fig.update_xaxes(gridcolor='#2a2d3a', zeroline=False)
    fig.update_yaxes(gridcolor='#2a2d3a', zeroline=False)
    return fig

# ─── Chart 1: Monthly Spending by Category — Stacked Bar ─────────────────────

# All 12 months guaranteed
all_months = [f'2025-{m:02d}' for m in range(1, 13)]
monthly_cat = expenses_df.groupby(['Month', 'CleanCategory'])['AbsAmount'].sum().reset_index()
pivot1 = monthly_cat.pivot_table(index='Month', columns='CleanCategory', values='AbsAmount', fill_value=0)
pivot1 = pivot1.reindex(all_months, fill_value=0)

fig1 = go.Figure()
for i, col in enumerate(pivot1.columns):
    fig1.add_trace(go.Bar(
        name=col,
        x=pivot1.index.tolist(),
        y=pivot1[col].tolist(),
        marker_color=COLORS[i % len(COLORS)],
        hovertemplate=f'<b>{col}</b><br>%{{x}}: $%{{y:,.2f}}<extra></extra>'
    ))
fig1.update_layout(barmode='stack')
styled(fig1, '📊 Monthly Spending by Category — 2025 (All 12 Months)')

# ─── Chart 2: Spending Donut — Full Year by Category ─────────────────────────

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
styled(fig2, '🍩 Full-Year 2025 Spending Breakdown')

# ─── Chart 3: Income vs Expenses by Month — Grouped Bar ──────────────────────

monthly_inc = income_df.groupby('Month')['Amount'].sum().reset_index()
monthly_exp = expenses_df.groupby('Month')['AbsAmount'].sum().reset_index()
inc_map = dict(zip(monthly_inc['Month'], monthly_inc['Amount']))
exp_map = dict(zip(monthly_exp['Month'], monthly_exp['AbsAmount']))

fig3 = go.Figure()
fig3.add_trace(go.Bar(
    name='Income (Deposits + Interest)',
    x=all_months,
    y=[inc_map.get(m, 0) for m in all_months],
    marker_color='#4ecb71',
    hovertemplate='Income %{x}: $%{y:,.2f}<extra></extra>'
))
fig3.add_trace(go.Bar(
    name='Expenses',
    x=all_months,
    y=[exp_map.get(m, 0) for m in all_months],
    marker_color='#e05c5c',
    hovertemplate='Expenses %{x}: $%{y:,.2f}<extra></extra>'
))
fig3.update_layout(barmode='group')
styled(fig3, '💰 Income vs Expenses by Month — 2025')

# ─── Chart 4: Daily Spend + 7-Day Moving Average ─────────────────────────────

daily = expenses_df.groupby('Date')['AbsAmount'].sum().reset_index()
daily_sorted = daily.sort_values('Date')
daily_7ma = daily_sorted.set_index('Date')['AbsAmount'].rolling(7).mean().reset_index()

fig4 = go.Figure()
fig4.add_trace(go.Bar(
    x=daily_sorted['Date'], y=daily_sorted['AbsAmount'],
    name='Daily Spend',
    marker_color='rgba(108,142,245,0.4)',
    hovertemplate='%{x|%b %d}: $%{y:,.2f}<extra></extra>'
))
fig4.add_trace(go.Scatter(
    x=daily_7ma['Date'], y=daily_7ma['AbsAmount'],
    name='7-Day Avg',
    line=dict(color='#f5a623', width=2),
    hovertemplate='7d avg: $%{y:,.2f}<extra></extra>'
))
styled(fig4, '📈 Daily Spending + 7-Day Moving Average — 2025')

# ─── Chart 5: Top 20 Merchants Treemap ───────────────────────────────────────

merchant_totals = (
    expenses_df.groupby('Description')['AbsAmount']
    .sum().sort_values(ascending=False).head(20)
)
fig5 = go.Figure(go.Treemap(
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
styled(fig5, '🌳 Top 20 Merchants by Spend — 2025')

# ─── Chart 6: Top 15 Dining Spots — Bar Chart ────────────────────────────────

dining_df = expenses_df[expenses_df['CleanCategory'] == 'Dining Out'].copy()
top_dining = (
    dining_df.groupby('Description')['AbsAmount']
    .sum().sort_values(ascending=False).head(15)
)
fig6 = go.Figure(go.Bar(
    x=top_dining.index.tolist(),
    y=top_dining.values.tolist(),
    marker=dict(color=top_dining.values.tolist(), colorscale='Reds', showscale=True),
    hovertemplate='<b>%{x}</b>: $%{y:,.2f}<extra></extra>'
))
fig6.update_layout(xaxis_tickangle=-45)
styled(fig6, '🍔 Top 15 Dining Spots — 2025')

# ─── Chart 7: Subscriptions & Recurring — Horizontal Bar ─────────────────────

sub_keywords = [
    'Netflix', 'Spotify', 'Hbo Max', 'Disney Plus', 'Amazon Prime',
    'Sling Tv', 'Xbox', 'Chatgpt', 'Claude', 'Anthropic', 'Medium',
    'Oura Ring', 'Google *fi', 'Vonage', 'Adt Security', 'Hippo Insurance',
    'Geico', 'Uber One', 'Microsoft', 'Google *cloud', 'Google *wyze',
    'Google *grok', 'Forhims', 'Transunion', 'Joinfansclub', 'Findfansclub',
    'Paddle.net', 'Ring Solo', 'Northwest Federal', 'Fastrak', 'At&t',
    'Aig', 'Fitbit', 'Amazon Kindle', 'Github', 'Grok', 'Apple',
    'iCloud', 'Dropbox', 'Hulu', 'Paramount', 'Peacock', 'Duolingo',
]

def is_sub(desc):
    return any(k.lower() in str(desc).lower() for k in sub_keywords)

sub_df = expenses_df[expenses_df['Description'].apply(is_sub)].copy()
sub_total_by_merchant = sub_df.groupby('Description')['AbsAmount'].sum().sort_values(ascending=True)

fig7 = go.Figure(go.Bar(
    x=sub_total_by_merchant.values.tolist(),
    y=sub_total_by_merchant.index.tolist(),
    orientation='h',
    marker=dict(
        color=sub_total_by_merchant.values.tolist(),
        colorscale='Sunset', showscale=True,
        colorbar=dict(title='Total $')
    ),
    hovertemplate='<b>%{y}</b>: $%{x:,.2f}<extra></extra>'
))
fig7.update_layout(height=max(400, len(sub_total_by_merchant) * 22))
styled(fig7, '🔁 Subscriptions & Recurring Expenses — 2025')

# ─── Chart 8: AI/Tech Services ────────────────────────────────────────────────

ai_keywords = [
    'Chatgpt', 'Claude', 'Anthropic', 'Grok', 'Google *grok',
    'Microsoft', 'Google *cloud', 'Google *fi', 'Github', 'Vonage',
    'Google *wyze', 'Gemini',
]
ai_df = expenses_df[expenses_df['Description'].apply(
    lambda d: any(k.lower() in str(d).lower() for k in ai_keywords)
)]
ai_total = ai_df.groupby('Description')['AbsAmount'].sum().sort_values(ascending=False)

fig8 = go.Figure(go.Bar(
    x=ai_total.index.tolist(),
    y=ai_total.values.tolist(),
    marker=dict(color=COLORS[:len(ai_total)]),
    hovertemplate='<b>%{x}</b>: $%{y:,.2f}<extra></extra>'
))
fig8.update_layout(xaxis_tickangle=-35)
styled(fig8, '🤖 AI & Tech Services Spending — 2025')

# ─── Chart 9: Day of Week × Category Heatmap ─────────────────────────────────

dow_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
dow_data = expenses_df.groupby(['DayOfWeek', 'CleanCategory'])['AbsAmount'].sum().reset_index()
dow_pivot = dow_data.pivot_table(
    index='DayOfWeek', columns='CleanCategory', values='AbsAmount', fill_value=0
)
dow_pivot = dow_pivot.reindex([d for d in dow_order if d in dow_pivot.index])

fig9 = go.Figure(go.Heatmap(
    z=dow_pivot.values.tolist(),
    x=dow_pivot.columns.tolist(),
    y=dow_pivot.index.tolist(),
    colorscale='Viridis',
    hovertemplate='<b>%{y} — %{x}</b><br>$%{z:,.2f}<extra></extra>',
    colorbar=dict(title='$')
))
fig9.update_layout(xaxis_tickangle=-45)
styled(fig9, '📅 Spending Heatmap: Day of Week × Category — 2025')

# ─── Chart 10: Monthly Category Trend Lines — Top 5 Categories ───────────────

top5_cats = (
    expenses_no_tax.groupby('CleanCategory')['AbsAmount']
    .sum().sort_values(ascending=False).head(5).index.tolist()
)
trend_df = (
    expenses_no_tax[expenses_no_tax['CleanCategory'].isin(top5_cats)]
    .groupby(['Month', 'CleanCategory'])['AbsAmount'].sum().reset_index()
)

fig10 = go.Figure()
for i, cat in enumerate(top5_cats):
    cat_data = trend_df[trend_df['CleanCategory'] == cat]
    month_vals = dict(zip(cat_data['Month'], cat_data['AbsAmount']))
    fig10.add_trace(go.Scatter(
        x=all_months,
        y=[month_vals.get(m, 0) for m in all_months],
        name=cat,
        mode='lines+markers',
        line=dict(color=COLORS[i % len(COLORS)], width=2),
        marker=dict(size=6),
        hovertemplate=f'<b>{cat}</b><br>%{{x}}: $%{{y:,.2f}}<extra></extra>'
    ))
styled(fig10, '📉 Monthly Trend — Top 5 Spending Categories — 2025')

# ─── Chart 11: Gasoline/Fuel Spend by Month ──────────────────────────────────

gas_df = expenses_df[expenses_df['CleanCategory'] == 'Gas & Fuel'].copy()
gas_monthly = gas_df.groupby('Month')['AbsAmount'].sum().reindex(all_months, fill_value=0)

fig11 = go.Figure(go.Bar(
    x=gas_monthly.index.tolist(),
    y=gas_monthly.values.tolist(),
    marker=dict(
        color=gas_monthly.values.tolist(),
        colorscale='YlOrRd', showscale=False,
    ),
    hovertemplate='%{x}: $%{y:,.2f}<extra></extra>'
))
styled(fig11, '⛽ Gasoline/Fuel Spend by Month — 2025')

# ─── Chart 12: Housing Costs by Month ────────────────────────────────────────

housing_cats = ['Housing (Mortgage)', 'Rent']
housing_df = expenses_df[expenses_df['CleanCategory'].isin(housing_cats)].copy()

# Property tax from tax entries
prop_tax_df = tax_df[tax_df['Description'].str.contains(
    r'property tax|county tax|treasurer|assessor', case=False, na=False
)].copy() if len(tax_df) > 0 else pd.DataFrame(columns=['Month', 'AbsAmount', 'CleanCategory'])
if len(prop_tax_df) > 0:
    prop_tax_df['CleanCategory'] = 'Property Tax'

housing_combined = pd.concat([housing_df, prop_tax_df], ignore_index=True)

fig12 = go.Figure()
for cat in housing_combined['CleanCategory'].unique():
    cat_data = housing_combined[housing_combined['CleanCategory'] == cat]
    monthly_data = cat_data.groupby('Month')['AbsAmount'].sum().reindex(all_months, fill_value=0)
    fig12.add_trace(go.Bar(
        name=cat,
        x=all_months,
        y=monthly_data.values.tolist(),
        hovertemplate=f'<b>{cat}</b><br>%{{x}}: $%{{y:,.2f}}<extra></extra>'
    ))
fig12.update_layout(barmode='stack')
styled(fig12, '🏠 Housing Costs by Month — 2025 (Mortgage + Rent + Property Tax)')

# ─── Summary Stats ────────────────────────────────────────────────────────────

total_exp = expenses_df['AbsAmount'].sum()
total_inc = income_df['Amount'].sum()
months_covered = 12  # Full year
avg_monthly_exp = expenses_no_tax['AbsAmount'].sum() / months_covered
tax_total_display = tax_total
top_cat = cat_totals.index[0]
top_cat_amt = cat_totals.iloc[0]
sub_total_amt = sub_df['AbsAmount'].sum()
dining_total = dining_df['AbsAmount'].sum()
inv_income = income_df[income_df['Category'] == 'Investment Income']['Amount'].sum()
total_transactions = len(df)
rec_pct = (sub_total_amt / total_exp * 100) if total_exp > 0 else 0

# ─── Recommendations ──────────────────────────────────────────────────────────

recommendations = []

# 1. Dining
if dining_total > 2000:
    recommendations.append({
        'icon': '🍔', 'title': 'High Dining Spend', 'priority': 'high',
        'amount': f'${dining_total:,.0f}',
        'detail': (
            f'You spent ${dining_total:,.0f} dining out in 2025 — that\'s ${dining_total/12:,.0f}/month. '
            f'Top spots: {", ".join(top_dining.head(3).index.tolist())}. '
            f'Cooking 2 extra nights/week could save $150-300/month.'
        )
    })

# 2. Subscriptions
if sub_total_amt > 1000:
    recommendations.append({
        'icon': '🔁', 'title': 'Subscription Audit', 'priority': 'high',
        'amount': f'${sub_total_amt:,.0f}',
        'detail': (
            f'${sub_total_amt:,.0f} across {len(sub_total_by_merchant)} recurring services in 2025. '
            f'That\'s ${sub_total_amt/12:,.0f}/month. Do a 15-min audit — '
            f'cancel anything unused for 3+ months. Potential savings: $50-150/month.'
        )
    })

# 3. AI tools
ai_total_amt = ai_df['AbsAmount'].sum()
if ai_total_amt > 100:
    recommendations.append({
        'icon': '🤖', 'title': 'AI Tool Consolidation', 'priority': 'medium',
        'amount': f'${ai_total_amt:,.0f}',
        'detail': (
            f'${ai_total_amt:,.0f} on AI & tech services in 2025. '
            f'Multiple overlapping subscriptions (ChatGPT, Claude, Grok, GitHub Copilot). '
            f'Pick your 1-2 primary tools and cut the rest.'
        )
    })

# 4. Delivery fees
delivery_df = expenses_df[expenses_df['Description'].str.contains(
    r'Doordash|Uber Eats|Grubhub|Instacart', case=False, na=False
)]
delivery_total = delivery_df['AbsAmount'].sum()
if delivery_total > 200:
    recommendations.append({
        'icon': '🛵', 'title': 'Food Delivery Fees', 'priority': 'medium',
        'amount': f'${delivery_total:,.0f}',
        'detail': (
            f'${delivery_total:,.0f} on delivery in 2025. Delivery + tips add 30-40% premium. '
            f'Switching to pickup from the same restaurants saves significantly.'
        )
    })

# 5. Amazon
amzn_df = expenses_df[expenses_df['Description'].str.contains('Amazon', case=False, na=False)]
amzn_total = amzn_df['AbsAmount'].sum()
if amzn_total > 500:
    recommendations.append({
        'icon': '📦', 'title': 'Amazon Impulse Control', 'priority': 'medium',
        'amount': f'${amzn_total:,.0f}',
        'detail': (
            f'${amzn_total:,.0f} on Amazon in 2025. '
            f'Try the 24-hour rule: add to cart, check back tomorrow. '
            f'Also audit Prime subscriptions — video, music, etc.'
        )
    })

# 6. Bank fees
fees_df = expenses_df[expenses_df['Description'].str.contains(
    r'Late Fee|Interest Charge|Service Charge|Overdraft', case=False, na=False
)]
fees_total = fees_df['AbsAmount'].sum()
if fees_total > 20:
    recommendations.append({
        'icon': '⚠️', 'title': 'Avoidable Bank Fees', 'priority': 'high',
        'amount': f'${fees_total:,.0f}',
        'detail': (
            f'${fees_total:,.0f} in late fees / interest charges — pure waste. '
            f'Set up autopay on all cards and accounts right now.'
        )
    })

# 7. Housing costs
housing_total = housing_combined['AbsAmount'].sum()
if housing_total > 0:
    pct = housing_total / total_exp * 100
    recommendations.append({
        'icon': '🏠', 'title': 'Housing as % of Spend', 'priority': 'low',
        'amount': f'${housing_total:,.0f} ({pct:.0f}%)',
        'detail': (
            f'Housing (mortgage/rent + property tax) was ${housing_total:,.0f} '
            f'= {pct:.0f}% of total expenses in 2025. '
            f'Rule of thumb: keep housing under 30% of gross income.'
        )
    })

# 8. Savings rate
net_flow = total_inc - expenses_no_tax['AbsAmount'].sum()
if total_inc > 0:
    savings_rate = net_flow / total_inc * 100
    recommendations.append({
        'icon': '💰', 'title': 'Savings Rate', 'priority': 'low' if savings_rate > 15 else 'medium',
        'amount': f'{savings_rate:.1f}%',
        'detail': (
            f'Tracked income: ${total_inc:,.0f}, tracked expenses (excl. taxes): '
            f'${expenses_no_tax["AbsAmount"].sum():,.0f}. '
            f'Apparent savings rate: {savings_rate:.1f}% of tracked income. '
            f'Note: this excludes payroll pre-tax deductions, 401k, etc.'
        )
    })

# ─── Build HTML ───────────────────────────────────────────────────────────────

def fig_to_html(fig):
    return fig.to_html(full_html=False, include_plotlyjs=False, config={'responsive': True})

priority_badge = {
    'high':   '<span style="background:#e05c5c;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold">HIGH</span>',
    'medium': '<span style="background:#f5a623;color:#000;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold">MEDIUM</span>',
    'low':    '<span style="background:#4ecb71;color:#000;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold">LOW</span>',
}

rec_html = ''
for r in recommendations:
    border = '#e05c5c' if r['priority'] == 'high' else '#f5a623' if r['priority'] == 'medium' else '#4ecb71'
    rec_html += f'''
    <div class="rec-card" style="border-left:4px solid {border}">
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
<title>Financial Report — Full Year 2025</title>
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
</style>
</head>
<body>

<h1>📊 Full-Year 2025 Financial Report</h1>
<p class="subtitle">
  Jan 1 – Dec 31, 2025 &nbsp;·&nbsp; {total_transactions:,} transactions &nbsp;·&nbsp;
  12 months &nbsp;·&nbsp; Generated {datetime.now().strftime("%b %d, %Y %H:%M")}
</p>

<!-- ── STAT CARDS ───────────────────────────────────────────── -->
<div class="stats-grid">
  <div class="stat-card">
    <div class="stat-label">Total 2025 Expenses</div>
    <div class="stat-value">${total_exp:,.0f}</div>
    <div class="stat-sub">All categories incl. taxes</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Avg Monthly (excl. taxes)</div>
    <div class="stat-value">${avg_monthly_exp:,.0f}</div>
    <div class="stat-sub">Recurring spend / 12 months</div>
  </div>
  <div class="stat-card" style="border-color:#f5a623">
    <div class="stat-label">Tax Payments (One-Time)</div>
    <div class="stat-value" style="color:#f5a623">${tax_total_display:,.0f}</div>
    <div class="stat-sub">IRS + FTB + TurboTax + Property</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Top Spending Category</div>
    <div class="stat-value" style="font-size:18px">{top_cat}</div>
    <div class="stat-sub">${top_cat_amt:,.0f} total</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Dining Out</div>
    <div class="stat-value">${dining_total:,.0f}</div>
    <div class="stat-sub">${dining_total/12:,.0f}/month avg</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Subscriptions</div>
    <div class="stat-value">${sub_total_amt:,.0f}</div>
    <div class="stat-sub">{rec_pct:.1f}% of total expenses</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Investment Income</div>
    <div class="stat-value">${inv_income:,.0f}</div>
    <div class="stat-sub">Dividends + capital gains</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Total Transactions</div>
    <div class="stat-value">{total_transactions:,}</div>
    <div class="stat-sub">Full year 2025</div>
  </div>
</div>

<hr class="section-divider">

<!-- ── SPENDING TRENDS ─────────────────────────────────────── -->
<h2>📈 Spending Trends</h2>

<div class="chart-card">
{fig_to_html(fig1)}
</div>

<div class="chart-grid">
  <div class="chart-card">{fig_to_html(fig2)}</div>
  <div class="chart-card">{fig_to_html(fig3)}</div>
</div>

<div class="chart-card">
{fig_to_html(fig4)}
</div>

<div class="chart-card">
{fig_to_html(fig10)}
</div>

<hr class="section-divider">

<!-- ── MERCHANT ANALYSIS ───────────────────────────────────── -->
<h2>🏪 Merchant Analysis</h2>

<div class="chart-card">
{fig_to_html(fig5)}
</div>

<div class="chart-grid">
  <div class="chart-card">{fig_to_html(fig6)}</div>
  <div class="chart-card">{fig_to_html(fig8)}</div>
</div>

<hr class="section-divider">

<!-- ── BEHAVIORAL PATTERNS ────────────────────────────────── -->
<h2>📅 Patterns & Recurring</h2>

<div class="chart-card">
{fig_to_html(fig9)}
</div>

<div class="chart-card">
{fig_to_html(fig7)}
</div>

<hr class="section-divider">

<!-- ── CATEGORY DEEP DIVES ────────────────────────────────── -->
<h2>🔍 Category Deep Dives</h2>

<div class="chart-grid">
  <div class="chart-card">{fig_to_html(fig11)}</div>
  <div class="chart-card">{fig_to_html(fig12)}</div>
</div>

<hr class="section-divider">

<!-- ── RECOMMENDATIONS ────────────────────────────────────── -->
<h2>💡 Recommendations</h2>
<p style="color:#888;font-size:13px;margin-bottom:20px">
  Based on your full-year 2025 transaction data. Prioritized by financial impact.
</p>

{rec_html}

<hr class="section-divider">
<p style="color:#444;font-size:12px;text-align:center">
  Generated by OpenClaw Financial Analyzer &nbsp;·&nbsp;
  Data: {total_transactions:,} transactions &nbsp;·&nbsp;
  {datetime.now().strftime("%Y-%m-%d %H:%M")}
</p>

</body>
</html>'''

with open(OUTPUT_PATH, 'w') as f:
    f.write(html)

print(f"✅ 2025 report generated: {OUTPUT_PATH}")
print(f"   Transactions: {total_transactions:,}")
print(f"   Categories: {expenses_df['CleanCategory'].nunique()}")
print(f"   Date range: {df['Date'].min().date()} → {df['Date'].max().date()}")
print(f"   Total expenses: ${total_exp:,.2f}")
print(f"   Avg monthly (excl. taxes): ${avg_monthly_exp:,.2f}")
print(f"   Tax payments: ${tax_total_display:,.2f}")
print(f"   Recommendations: {len(recommendations)}")
print("2025_DONE")
