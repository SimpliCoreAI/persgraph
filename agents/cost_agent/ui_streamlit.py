"""
Cost Agent Phase 4 — Lightweight Streamlit Dashboard

A minimal, useful UI for cost summaries and drill-down with event_id links.

Features:
  - Summary views by command, worker, layer, model, date
  - Date range filtering
  - Event ID association for feedback/learning
  - Multi-format export (CSV, JSON, Markdown)
  - Anomaly alerts from Phase 3
  - No vanity visualizations; focus on actionable data

Usage:
    cd /root/AgenticHub/Persgraph
    PYTHONPATH=. streamlit run agents/cost_agent/ui_streamlit.py

Requirements:
    streamlit>=1.28.0
    pandas>=2.0.0
    (Both already in .venv)

Status: NEW (Phase 4 UI, restore-or-build task)
Author: Subagent (cost_agent phase 4)
Version: 0.4.0
Date: 2026-06-20
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

# Setup path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import cost agent APIs (Phase 3)
try:
    from agents.cost_agent import (
        get_cost_summary,
        export_summary,
        check_budget_increase_alert,
    )
    COST_AGENT_AVAILABLE = True
except ImportError as e:
    COST_AGENT_AVAILABLE = False
    print(f"⚠️  Cost Agent not available: {e}")

try:
    import streamlit as st
    import pandas as pd
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False
    print("⚠️  Streamlit/pandas not available. Install: pip install streamlit pandas")


# ==================================================================================
# PAGE CONFIGURATION
# ==================================================================================

if STREAMLIT_AVAILABLE:
    st.set_page_config(
        page_title="Cost Agent Dashboard",
        page_icon="💰",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.markdown("""
    <style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 0.75rem;
        margin: 0.5rem 0;
        color: white;
    }
    .alert-card {
        background: #fff3cd;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #ffc107;
        margin: 0.5rem 0;
    }
    </style>
    """, unsafe_allow_html=True)


# ==================================================================================
# HELPER FUNCTIONS
# ==================================================================================

def safe_get_summary(group_by, start_date=None, end_date=None):
    """Safely fetch cost summary with error handling."""
    if not COST_AGENT_AVAILABLE:
        st.error("❌ Cost Agent not available")
        return {}
    
    try:
        return get_cost_summary(
            group_by=group_by,
            start_date=start_date,
            end_date=end_date,
            include_event_ids=True,
        )
    except Exception as e:
        st.error(f"⚠️  Failed to load summary: {e}")
        return {}


def safe_get_alerts(alert_type="summary", lookback_days=7):
    """Safely fetch alerts with error handling."""
    if not COST_AGENT_AVAILABLE:
        return {"status": "unavailable"}
    
    try:
        return check_budget_increase_alert(
            alert_type=alert_type,
            lookback_days=lookback_days,
        )
    except Exception as e:
        st.error(f"⚠️  Failed to load alerts: {e}")
        return {}


def summary_to_dataframe(summary):
    """Convert summary dict to pandas DataFrame for display."""
    if not summary:
        return pd.DataFrame()
    
    rows = []
    for key, group in summary.items():
        rows.append({
            "Group": key,
            "Total Cost": f"${group.get('total_cost', 0):.2f}",
            "Count": group.get("count", 0),
            "Avg Cost": f"${group.get('avg_cost', 0):.4f}",
            "Tokens": f"{group.get('total_tokens', 0):,}",
            "Event IDs": len(group.get("event_ids", [])),
        })
    
    return pd.DataFrame(rows)


def render_header():
    """Render dashboard title and description."""
    st.title("💰 Cost Agent Dashboard")
    st.markdown("""
    Monitor API costs across commands, users, models, and providers.  
    **Phase 4 Lightweight UI** — Summaries + drill-down + event ID tracking.
    
    Data source: Cost Agent (Phase 3 reporting APIs)
    """)


def render_overview():
    """Render top-level metrics and today's summary."""
    st.header("📊 Overview")
    
    try:
        # Today's summary by command
        today = datetime.utcnow().date().isoformat()
        summary = safe_get_summary("command", start_date=today, end_date=today)
        
        if summary:
            total_cost = sum(g.get("total_cost", 0) for g in summary.values())
            total_count = sum(g.get("count", 0) for g in summary.values())
            total_tokens = sum(g.get("total_tokens", 0) for g in summary.values())
            
            # Metrics row
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Today's Cost", f"${total_cost:.2f}")
            with col2:
                st.metric("Operations", total_count)
            with col3:
                st.metric("Total Tokens", f"{total_tokens:,}")
            with col4:
                top_cmd = max(summary.items(), key=lambda x: x[1].get("total_cost", 0), default=("—", {}))
                st.metric("Top Command", top_cmd[0], f"${top_cmd[1].get('total_cost', 0):.2f}")
        else:
            st.info("📭 No cost data available for today")
    
    except Exception as e:
        st.error(f"Failed to render overview: {e}")


def render_summaries_tab():
    """Render flexible cost summaries by dimension."""
    st.header("📈 Cost Summaries")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        group_by = st.selectbox(
            "Group by:",
            ["command", "worker", "layer", "model", "date", "trigger"],
            help="Choose summary dimension"
        )
    
    with col2:
        start_date = st.date_input(
            "Start date:",
            value=datetime.utcnow().date() - timedelta(days=7),
        )
    
    with col3:
        end_date = st.date_input(
            "End date:",
            value=datetime.utcnow().date(),
        )
    
    with col4:
        # Refresh button (semantic)
        st.write("")  # Align button vertically
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    # Fetch summary
    summary = safe_get_summary(
        group_by,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )
    
    if summary:
        # Summary table
        df = summary_to_dataframe(summary)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Statistics
        st.subheader("Statistics")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            costs = [g.get("total_cost", 0) for g in summary.values()]
            if costs:
                st.metric("Total Cost", f"${sum(costs):.2f}")
        
        with col2:
            counts = [g.get("count", 0) for g in summary.values()]
            if counts:
                st.metric("Total Operations", sum(counts))
        
        with col3:
            if costs:
                avg = sum(costs) / len(costs)
                st.metric("Avg per Group", f"${avg:.2f}")
        
        # Export options
        st.subheader("Export")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📥 Download CSV", use_container_width=True):
                csv_data = export_summary(summary, format="csv")
                st.download_button(
                    label="CSV File",
                    data=csv_data,
                    file_name=f"cost_summary_{group_by}_{end_date}.csv",
                    mime="text/csv",
                )
        
        with col2:
            if st.button("📥 Download JSON", use_container_width=True):
                json_data = export_summary(summary, format="json")
                st.download_button(
                    label="JSON File",
                    data=json_data,
                    file_name=f"cost_summary_{group_by}_{end_date}.json",
                    mime="application/json",
                )
        
        with col3:
            if st.button("📥 Download Markdown", use_container_width=True):
                md_data = export_summary(summary, format="markdown")
                st.download_button(
                    label="Markdown File",
                    data=md_data,
                    file_name=f"cost_summary_{group_by}_{end_date}.md",
                    mime="text/markdown",
                )
    
    else:
        st.info("📭 No data available for the selected date range")


def render_event_details_tab():
    """Render event ID association details for drill-down."""
    st.header("🔍 Event Details & Drill-Down")
    
    col1, col2 = st.columns(2)
    
    with col1:
        group_by = st.selectbox(
            "Group by (for drill-down):",
            ["command", "worker", "layer", "model"],
            key="event_group_by"
        )
    
    with col2:
        lookback_days = st.slider("Days of history:", 1, 30, 7)
    
    # Fetch summary
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=lookback_days)
    
    summary = safe_get_summary(
        group_by,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )
    
    if summary:
        st.subheader(f"Event IDs by {group_by}")
        
        for key, group in summary.items():
            event_ids = group.get("event_ids", [])
            cost = group.get("total_cost", 0)
            count = group.get("count", 0)
            
            with st.expander(f"📌 {key} — ${cost:.2f} ({count} ops, {len(event_ids)} events)"):
                if event_ids:
                    # Event IDs table
                    event_df = pd.DataFrame({"Event ID": event_ids[:100]})
                    st.dataframe(event_df, use_container_width=True, hide_index=True)
                    
                    # Context
                    st.markdown("""
                    **How to use Event IDs:**
                    - Link to Langfuse traces for detailed debugging
                    - Use for feedback loops and continuous learning
                    - Track cost drivers per event
                    - Export for analysis in external tools
                    """)
                    
                    # Copy-paste option
                    event_ids_str = ", ".join(event_ids[:20])
                    st.code(event_ids_str, language="text")
                else:
                    st.warning("⚠️  No event IDs available (may indicate aggregated data)")
    else:
        st.info("📭 No data available")


def render_alerts_tab():
    """Render anomaly alerts and budget warnings."""
    st.header("⚠️ Anomaly Alerts & Budget Warnings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        alert_type = st.selectbox(
            "Alert type:",
            ["anomaly", "new_ops", "summary"],
            help="anomaly: Cost spikes | new_ops: New operations | summary: Spending overview"
        )
    
    with col2:
        lookback_days = st.slider("Baseline window (days):", 3, 30, 7)
    
    # Fetch alerts
    alerts = safe_get_alerts(alert_type=alert_type, lookback_days=lookback_days)
    
    if alert_type == "anomaly":
        st.subheader("Cost Anomalies (>2σ above baseline)")
        
        anomalies = alerts.get("anomalies", [])
        if anomalies:
            for anom in anomalies:
                severity = anom.get("severity", "low").upper()
                user_id = anom.get("user_id", "unknown")
                operation = anom.get("operation", "unknown")
                today_cost = anom.get("today_cost", 0)
                baseline = anom.get("baseline_mean", 0)
                reason = anom.get("reason", "")
                
                st.markdown(f"""
                <div class='alert-card'>
                **{severity}** | {user_id} / {operation}  
                Today: ${today_cost:.2f} | Baseline: ${baseline:.2f}  
                {reason}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ No anomalies detected")
    
    elif alert_type == "new_ops":
        st.subheader("New Operations Detected")
        
        new_ops = alerts.get("new_operations", [])
        if new_ops:
            for op in new_ops:
                st.info(f"🆕 {op.get('operation', 'unknown')} (user: {op.get('user_id', 'unknown')})")
        else:
            st.success("✅ No new operations")
    
    else:  # summary
        st.subheader("Spending Summary")
        
        by_user = alerts.get("by_user", {})
        if by_user:
            st.write("**By User:**")
            user_df = pd.DataFrame([
                {"User": k, "Cost": f"${v:.2f}"}
                for k, v in by_user.items()
            ])
            st.dataframe(user_df, use_container_width=True, hide_index=True)
        
        by_op = alerts.get("by_operation", {})
        if by_op:
            st.write("**By Operation:**")
            op_df = pd.DataFrame([
                {"Operation": k, "Cost": f"${v:.2f}"}
                for k, v in by_op.items()
            ])
            st.dataframe(op_df, use_container_width=True, hide_index=True)


def render_sidebar():
    """Render sidebar with navigation and settings."""
    with st.sidebar:
        st.title("Navigation")
        
        page = st.radio(
            "Select view:",
            [
                "📊 Overview",
                "📈 Summaries",
                "🔍 Event Details",
                "⚠️ Alerts",
                "ℹ️ Help",
            ],
            label_visibility="collapsed"
        )
        
        st.divider()
        
        st.markdown("### About This Dashboard")
        st.info("""
        **Cost Agent Phase 4 UI**
        
        Lightweight dashboard for cost summaries and event tracking.
        
        - Flexible summaries (command, worker, layer, model, date)
        - Event ID drill-down for feedback loops
        - Anomaly-based alerts (no threshold tuning)
        - Multi-format export (CSV, JSON, Markdown)
        
        **Status:** Phase 4 (NEW UI)  
        **Version:** 0.4.0  
        **Data:** Phase 3 Reporting APIs
        """)
        
        st.divider()
        
        st.markdown("### Data Source")
        st.code("""
Path: agents/cost_agent/
APIs: Phase 3 (Phase 3_QUICK_START.md)
        """, language="text")
        
        st.divider()
        
        st.markdown("### Links")
        st.markdown("""
- [Phase 3 Quick Start](https://github.com/localhost/cost_agent/PHASE_3_QUICK_START.md)
- [Phase Roadmap](https://github.com/localhost/cost_agent/PHASE_ROADMAP.md)
- [Implementation Docs](https://github.com/localhost/cost_agent/IMPLEMENTATION_PLAN.md)
        """)
        
        return page


def render_help_tab():
    """Render help and documentation."""
    st.header("ℹ️ Help & Documentation")
    
    st.markdown("""
    ## Cost Agent Dashboard — Phase 4
    
    ### What is this dashboard?
    
    A lightweight Streamlit UI for monitoring API costs tracked by the Cost Agent.
    It provides **summaries**, **event tracking**, and **anomaly alerts** without vanity visualizations.
    
    ### Key Features
    
    1. **Flexible Summaries** — Group costs by:
       - Command (operation type: ask, ingest, query, etc.)
       - Worker (user_id)
       - Layer (provider: anthropic, openai, ollama)
       - Model (specific model name)
       - Date (daily breakdown)
       - Trigger (source: command, scheduled, webhook)
    
    2. **Event ID Tracking** — Every cost record includes:
       - Event IDs for linking back to Langfuse traces
       - Feedback loop integration for continuous learning
       - Audit trail for cost drivers
    
    3. **Anomaly Alerts** — Detect cost spikes:
       - Automatic detection (>2σ above 7-day baseline)
       - No threshold tuning required
       - New operation detection
       - Severity classification (low, medium, high)
    
    4. **Multi-Format Export**:
       - CSV for spreadsheets
       - JSON for APIs
       - Markdown for reports/emails
    
    ### Common Tasks
    
    **View today's costs by operation:**
    1. Go to "Summaries" tab
    2. Select "command" in dropdown
    3. Set date range to today only
    4. Review table
    
    **Export weekly cost report:**
    1. Go to "Summaries" tab
    2. Select "command" (or any dimension)
    3. Set start_date to 7 days ago, end_date to today
    4. Click "Download Markdown" to get report
    
    **Find events for cost anomalies:**
    1. Go to "Alerts" tab
    2. Select "anomaly" alert type
    3. Review detected spikes
    4. Go to "Event Details" tab to inspect event IDs
    5. Use event IDs in Langfuse for trace debugging
    
    **Check budget health:**
    1. Go to "Alerts" tab
    2. Select "summary" alert type
    3. Review by-user and by-operation breakdowns
    
    ### Data Freshness
    
    Cost data updates automatically as Langfuse observations are polled.
    Dashboard reflects latest data (typically <5 minutes behind).
    
    ### Backward Compatibility
    
    ✅ All Phase 1-3 functions still work  
    ✅ No breaking changes  
    ✅ UI is purely additive
    
    ### Need Help?
    
    - **Phase 3 API Reference:** See `PHASE_3_QUICK_START.md`
    - **Detailed Implementation:** See `PHASE_3_IMPLEMENTATION.md`
    - **Roadmap & Architecture:** See `PHASE_ROADMAP.md`
    """)


# ==================================================================================
# MAIN APP
# ==================================================================================

def main():
    """Main Streamlit app."""
    
    if not STREAMLIT_AVAILABLE:
        print("❌ Streamlit not installed.")
        print("   Install with: pip install streamlit pandas")
        print("\nThis file provides a Phase 4 UI for the Cost Agent.")
        return
    
    if not COST_AGENT_AVAILABLE:
        st.error("❌ Cost Agent not available. Check PYTHONPATH and imports.")
        st.stop()
    
    # Render sidebar and get page
    page = render_sidebar()
    
    # Render header
    render_header()
    
    # Route to page
    if page == "📊 Overview":
        render_overview()
    
    elif page == "📈 Summaries":
        render_summaries_tab()
    
    elif page == "🔍 Event Details":
        render_event_details_tab()
    
    elif page == "⚠️ Alerts":
        render_alerts_tab()
    
    elif page == "ℹ️ Help":
        render_help_tab()


if __name__ == "__main__":
    if STREAMLIT_AVAILABLE and COST_AGENT_AVAILABLE:
        main()
    else:
        st.error("Missing dependencies. See message above.")
        st.stop()
