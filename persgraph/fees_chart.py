#!/usr/bin/env python3
"""
PersGraph — Hidden & Late Fees Chart
Generates fees_chart.html in the persgraph/ directory.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from db.queries import get_fees_df

# ── Data prep ─────────────────────────────────────────────────────────────────
fees = get_fees_df()
charged = fees[fees['amount'] < 0].copy()
waived  = fees[fees['amount'] > 0].copy()

charged['month'] = charged['date'].dt.to_period('M').astype(str)
charged['abs_amount'] = charged['amount'].abs()

# By fee type (net of waivers)
net_by_type = (
    fees.groupby('fee_type')['amount'].sum().abs()
    .sort_values(ascending=False)
    .reset_index()
)
net_by_type.columns = ['fee_type', 'net_total']

charged_by_type = (
    charged.groupby('fee_type')['abs_amount'].sum()
    .sort_values(ascending=False)
    .reset_index()
)
charged_by_type.columns = ['fee_type', 'charged']

waived_by_type = (
    waived.groupby('fee_type')['amount'].sum()
    .reset_index()
)
waived_by_type.columns = ['fee_type', 'waived']

by_type = charged_by_type.merge(waived_by_type, on='fee_type', how='left').fillna(0)
by_type['net'] = by_type['charged'] - by_type['waived']

# Monthly timeline
monthly = (
    charged.groupby('month')['abs_amount'].sum()
    .reset_index()
    .sort_values('month')
)
monthly.columns = ['month', 'total_charged']

# Monthly by fee type (stacked)
monthly_stacked = (
    charged.groupby(['month', 'fee_type'])['abs_amount'].sum()
    .reset_index()
    .sort_values('month')
)

# Summary stats
total_charged = charged['abs_amount'].sum()
total_waived  = waived['amount'].sum()
net_paid      = total_charged - total_waived

fee_colors = {
    'maintenance_fee':       '#f97316',
    'interest':              '#ef4444',
    'late_fee':              '#dc2626',
    'annual_fee':            '#a855f7',
    'plan_fee':              '#3b82f6',
    'foreign_transaction_fee':'#14b8a6',
    'cash_advance_fee':      '#f59e0b',
}
fee_labels = {
    'maintenance_fee':        'Maintenance',
    'interest':               'Interest',
    'late_fee':               'Late Fee',
    'annual_fee':             'Annual Fee',
    'plan_fee':               'Plan Fee',
    'foreign_transaction_fee':'Foreign Tx',
    'cash_advance_fee':       'Cash Advance',
}

BG    = '#0f1117'
CARD  = '#1a1d27'
TEXT  = '#e2e8f0'
MUTED = '#64748b'
GRID  = '#1e2330'

# ── Layout ─────────────────────────────────────────────────────────────────────
fig = make_subplots(
    rows=2, cols=2,
    subplot_titles=(
        'Monthly Fees Charged (Stacked by Type)',
        'Net Fees by Type (Charged - Waived)',
        'Charged vs Waived by Type',
        'Monthly Trend — Total Charged',
    ),
    specs=[[{"type": "bar"}, {"type": "bar"}],
           [{"type": "bar"}, {"type": "scatter"}]],
    vertical_spacing=0.18,
    horizontal_spacing=0.10,
)

all_months = sorted(monthly_stacked['month'].unique())
fee_types_present = monthly_stacked['fee_type'].unique()

# ── Chart 1: Monthly stacked bar ──────────────────────────────────────────────
for ft in fee_types_present:
    sub = monthly_stacked[monthly_stacked['fee_type'] == ft]
    month_map = dict(zip(sub['month'], sub['abs_amount']))
    y_vals = [month_map.get(m, 0) for m in all_months]
    fig.add_trace(go.Bar(
        x=all_months, y=y_vals,
        name=fee_labels.get(ft, ft),
        marker_color=fee_colors.get(ft, '#94a3b8'),
        legendgroup=ft,
    ), row=1, col=1)

# ── Chart 2: Net by type ───────────────────────────────────────────────────────
fig.add_trace(go.Bar(
    x=[fee_labels.get(r, r) for r in net_by_type['fee_type']],
    y=net_by_type['net_total'],
    marker_color=[fee_colors.get(r, '#94a3b8') for r in net_by_type['fee_type']],
    text=[f'${v:,.0f}' for v in net_by_type['net_total']],
    textposition='outside',
    textfont_color=TEXT,
    showlegend=False,
), row=1, col=2)

# ── Chart 3: Charged vs Waived ─────────────────────────────────────────────────
labels = [fee_labels.get(r, r) for r in by_type['fee_type']]
fig.add_trace(go.Bar(
    x=labels, y=by_type['charged'],
    name='Charged', marker_color='#ef4444',
    showlegend=True, legendgroup='charged',
    text=[f'${v:,.0f}' for v in by_type['charged']],
    textposition='outside', textfont_color=TEXT,
), row=2, col=1)
fig.add_trace(go.Bar(
    x=labels, y=by_type['waived'],
    name='Waived', marker_color='#22c55e',
    showlegend=True, legendgroup='waived',
    text=[f'${v:,.0f}' for v in by_type['waived']],
    textposition='outside', textfont_color=TEXT,
), row=2, col=1)

# ── Chart 4: Monthly trend line ────────────────────────────────────────────────
fig.add_trace(go.Scatter(
    x=monthly['month'], y=monthly['total_charged'],
    mode='lines+markers',
    line=dict(color='#f97316', width=2),
    marker=dict(size=7, color='#f97316'),
    fill='tozeroy',
    fillcolor='rgba(249,115,22,0.12)',
    showlegend=False,
), row=2, col=2)

# ── Layout ─────────────────────────────────────────────────────────────────────
fig.update_layout(
    title=dict(
        text=(
            f'<b>Hidden & Late Fees Dashboard</b><br>'
            f'<span style="font-size:13px;color:{MUTED};">'
            f'Total Charged: <b style="color:#ef4444;">${total_charged:,.2f}</b>  |  '
            f'Waived: <b style="color:#22c55e;">${total_waived:,.2f}</b>  |  '
            f'Net Paid: <b style="color:#f97316;">${net_paid:,.2f}</b>'
            f'</span>'
        ),
        font=dict(size=18, color=TEXT),
        x=0.02,
    ),
    barmode='stack',
    paper_bgcolor=BG,
    plot_bgcolor=CARD,
    font=dict(color=TEXT, family='Inter, system-ui, sans-serif'),
    legend=dict(
        bgcolor=CARD, bordercolor=GRID,
        font=dict(size=11), orientation='h',
        x=0, y=-0.12,
    ),
    height=760,
    margin=dict(t=110, b=80, l=60, r=40),
)

for i in range(1, 3):
    for j in range(1, 3):
        fig.update_xaxes(gridcolor=GRID, linecolor=GRID, tickfont_color=MUTED, row=i, col=j)
        fig.update_yaxes(gridcolor=GRID, linecolor=GRID, tickfont_color=MUTED,
                         tickprefix='$', row=i, col=j)

for ann in fig.layout.annotations:
    ann.font.color = TEXT
    ann.font.size = 13

# ── Export ─────────────────────────────────────────────────────────────────────
OUT = Path(__file__).parent / 'fees_chart.html'
fig.write_html(str(OUT), include_plotlyjs='cdn')
print(f'✅ Chart saved → {OUT}')
print(f'\n📊 Fee Summary')
print(f'   Total charged : ${total_charged:,.2f}')
print(f'   Total waived  : ${total_waived:,.2f}')
print(f'   Net paid      : ${net_paid:,.2f}')
print(f'\n   By type (net):')
for _, row in net_by_type.iterrows():
    print(f'   {fee_labels.get(row.fee_type, row.fee_type):20s} ${row.net_total:,.2f}')
