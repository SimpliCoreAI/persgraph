"""💸 Fees & Charges — powered by PersGraph SQLite."""

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from db.queries import get_fees_df, get_connection

st.set_page_config(page_title="Fees & Charges", page_icon="💸", layout="wide")
st.title("💸 Fees & Charges")
st.caption("Interest · Late fees · Annual fees · Maintenance — all accounts")
st.divider()

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_fees():
    df = get_fees_df()
    df['date'] = pd.to_datetime(df['date'])
    return df

fees = load_fees()
charged = fees[fees['amount'] < 0].copy()
waived  = fees[fees['amount'] > 0].copy()
charged['abs_amount'] = charged['amount'].abs()
charged['month'] = charged['date'].dt.to_period('M').astype(str)

total_charged = charged['abs_amount'].sum()
total_waived  = waived['amount'].sum()
net_paid      = total_charged - total_waived

fee_labels = {
    'maintenance_fee': 'Maintenance', 'interest': 'Interest',
    'late_fee': 'Late Fee', 'annual_fee': 'Annual Fee',
    'plan_fee': 'Plan Fee', 'foreign_transaction_fee': 'Foreign Tx',
    'cash_advance_fee': 'Cash Advance',
}
fee_colors = {
    'maintenance_fee': '#f97316', 'interest': '#ef4444',
    'late_fee': '#dc2626', 'annual_fee': '#a855f7',
    'plan_fee': '#3b82f6', 'foreign_transaction_fee': '#14b8a6',
    'cash_advance_fee': '#f59e0b',
}

# ── KPI row ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Charged", f"${total_charged:,.2f}")
k2.metric("Total Waived", f"${total_waived:,.2f}", delta=f"+${total_waived:,.2f}", delta_color="normal")
k3.metric("Net Paid", f"${net_paid:,.2f}", delta=f"-${total_waived:,.2f} saved", delta_color="normal")
k4.metric("Fee Events", f"{len(charged):,} charges")

st.divider()

# ── Filters ───────────────────────────────────────────────────────────────────
col_f1, col_f2 = st.columns(2)
with col_f1:
    years = sorted(charged['year'].unique().tolist())
    sel_year = st.selectbox("Year", ["All"] + [str(y) for y in years])
with col_f2:
    fee_types = sorted(charged['fee_type'].unique().tolist())
    sel_type = st.multiselect("Fee Type", fee_types, default=fee_types,
                               format_func=lambda x: fee_labels.get(x, x))

# Apply filters
view = charged.copy()
if sel_year != "All":
    view = view[view['year'] == int(sel_year)]
if sel_type:
    view = view[view['fee_type'].isin(sel_type)]

# ── Charts ────────────────────────────────────────────────────────────────────
BG, CARD, GRID, TEXT, MUTED = '#0f1117', '#1a1d27', '#1e2330', '#e2e8f0', '#64748b'

tab_charts, tab_table = st.tabs(["📊 Charts", "📋 Transactions"])

with tab_charts:
    c1, c2 = st.columns(2)

    # Monthly trend
    monthly = view.groupby('month')['abs_amount'].sum().reset_index().sort_values('month')
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(
        x=monthly['month'], y=monthly['abs_amount'],
        marker_color='#ef4444', name='Monthly Fees',
    ))
    fig1.update_layout(
        title='Monthly Fees Charged', paper_bgcolor=BG, plot_bgcolor=CARD,
        font=dict(color=TEXT), xaxis=dict(gridcolor=GRID), yaxis=dict(gridcolor=GRID, tickprefix='$'),
        height=320, margin=dict(t=40, b=30, l=50, r=20),
    )
    c1.plotly_chart(fig1, use_container_width=True)

    # By fee type
    by_type = view.groupby('fee_type')['abs_amount'].sum().sort_values(ascending=False).reset_index()
    fig2 = go.Figure(go.Bar(
        x=[fee_labels.get(r, r) for r in by_type['fee_type']],
        y=by_type['abs_amount'],
        marker_color=[fee_colors.get(r, '#94a3b8') for r in by_type['fee_type']],
        text=[f'${v:,.0f}' for v in by_type['abs_amount']],
        textposition='outside', textfont_color=TEXT,
    ))
    fig2.update_layout(
        title='By Fee Type', paper_bgcolor=BG, plot_bgcolor=CARD,
        font=dict(color=TEXT), xaxis=dict(gridcolor=GRID), yaxis=dict(gridcolor=GRID, tickprefix='$'),
        height=320, margin=dict(t=40, b=30, l=50, r=20),
    )
    c2.plotly_chart(fig2, use_container_width=True)

    # By account
    by_acct = view.groupby('account')['abs_amount'].sum().sort_values(ascending=False).reset_index()
    by_acct['short'] = by_acct['account'].str.replace(r'.*Ending in ', '···', regex=True)
    fig3 = go.Figure(go.Bar(
        x=by_acct['abs_amount'], y=by_acct['short'],
        orientation='h', marker_color='#6c8ef5',
        text=[f'${v:,.0f}' for v in by_acct['abs_amount']],
        textposition='outside', textfont_color=TEXT,
    ))
    fig3.update_layout(
        title='By Account', paper_bgcolor=BG, plot_bgcolor=CARD,
        font=dict(color=TEXT), xaxis=dict(gridcolor=GRID, tickprefix='$'),
        yaxis=dict(gridcolor=GRID), height=350,
        margin=dict(t=40, b=30, l=160, r=60),
    )
    st.plotly_chart(fig3, use_container_width=True)

with tab_table:
    display = view[['date', 'account', 'description', 'fee_type', 'abs_amount']].copy()
    display.columns = ['Date', 'Account', 'Description', 'Fee Type', 'Amount']
    display['Fee Type'] = display['Fee Type'].map(lambda x: fee_labels.get(x, x))
    display['Amount'] = display['Amount'].map(lambda x: f'${x:,.2f}')
    display['Account'] = display['Account'].str.replace(r'.*(Ending in \d+).*', r'···\1', regex=True)
    display = display.sort_values('Date', ascending=False)

    st.dataframe(display, use_container_width=True, hide_index=True,
                 column_config={"Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD")})

    total_shown = view['abs_amount'].sum()
    st.caption(f"Showing {len(view):,} transactions · Total: ${total_shown:,.2f}")
