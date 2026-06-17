"""
PersGraph Learning Layer — Streamlit UI Template (Phase 1)

Lightweight dashboard for viewing learning data.
Intended as a reference for how the learning DB should be read/displayed.

This is a TEMPLATE/PROPOSAL only — not deployed yet.
Shows where a future Streamlit UI would read from and display.

Run with: streamlit run learning_streamlit_template.py
(Requires: pip install streamlit pandas)
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any
import logging

# Setup path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import streamlit as st
    import pandas as pd
    from learning_db import (
        get_event_summary,
        get_outcome_summary,
        get_skill_summary,
        get_preferences,
        count_events_by_type,
        count_outcomes_by_type,
        debug_summary,
    )
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False
    st = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------

def configure_page():
    """Streamlit page configuration."""
    if not STREAMLIT_AVAILABLE:
        return
    
    st.set_page_config(
        page_title="PersGraph Learning",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.markdown("""
    <style>
    .metric-card {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Dashboard Sections
# ---------------------------------------------------------------------------

def render_header():
    """Render dashboard title and description."""
    if not STREAMLIT_AVAILABLE:
        return
    
    st.title("🧠 PersGraph Learning Dashboard")
    st.markdown("""
    Monitor learning data from Explore Mode: events, outcomes, preferences, and discovered skills.
    
    **Data Source:** `data/learning.db` (SQLite)
    """)


def render_overview():
    """Render top-level metrics."""
    if not STREAMLIT_AVAILABLE:
        return
    
    st.header("Overview")
    
    try:
        # Get counts
        event_counts = count_events_by_type()
        outcome_counts = count_outcomes_by_type()
        summary = debug_summary()
        
        # Display metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Total Events", summary.get("events", 0))
        with col2:
            st.metric("Total Outcomes", summary.get("outcomes", 0))
        with col3:
            st.metric("Learned Skills", summary.get("skills", 0))
        with col4:
            st.metric("Preferences", summary.get("preferences", 0))
        with col5:
            st.metric("Audit Logs", summary.get("audit", 0))
        
        # Event breakdown
        if event_counts:
            st.subheader("Events by Type")
            df_events = pd.DataFrame(
                list(event_counts.items()),
                columns=["Event Type", "Count"]
            )
            st.bar_chart(df_events.set_index("Event Type"))
        
        # Outcome breakdown
        if outcome_counts:
            st.subheader("Outcomes by Type")
            df_outcomes = pd.DataFrame(
                list(outcome_counts.items()),
                columns=["Outcome Type", "Count"]
            )
            st.pie_chart(df_outcomes.set_index("Outcome Type"))
    
    except Exception as e:
        st.error(f"Failed to load overview: {e}")


def render_events_tab():
    """Render recent events."""
    if not STREAMLIT_AVAILABLE:
        return
    
    st.header("Recent Events")
    st.markdown("Suggestions offered, skips, and other learning events.")
    
    try:
        limit = st.slider("Load last N events", 10, 500, 100)
        events = get_event_summary(limit=limit)
        
        if not events:
            st.info("No events recorded yet.")
            return
        
        # Convert to dataframe
        df = pd.DataFrame(events)
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"])
        df = df.sort_values("timestamp_utc", ascending=False)
        
        # Display table
        st.dataframe(
            df[[
                "timestamp_utc", "event_type", "session_id"
            ]],
            use_container_width=True,
            height=400
        )
        
        # Show raw metadata for selected event (if needed)
        if st.checkbox("Show raw event data"):
            selected_idx = st.selectbox(
                "Select event",
                range(len(events)),
                format_func=lambda i: f"{events[i]['timestamp_utc']} - {events[i]['event_type']}"
            )
            st.json(events[selected_idx])
    
    except Exception as e:
        st.error(f"Failed to load events: {e}")


def render_outcomes_tab():
    """Render user interaction outcomes."""
    if not STREAMLIT_AVAILABLE:
        return
    
    st.header("Outcomes (User Interactions)")
    st.markdown("Track how users react to suggestions: accept, skip, click, bookmark.")
    
    try:
        limit = st.slider("Load last N outcomes", 10, 500, 100)
        outcomes = get_outcome_summary(limit=limit)
        
        if not outcomes:
            st.info("No outcomes recorded yet.")
            return
        
        # Convert to dataframe
        df = pd.DataFrame(outcomes)
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"])
        df = df.sort_values("timestamp_utc", ascending=False)
        
        # Key columns
        st.dataframe(
            df[[
                "timestamp_utc", "outcome_type", "suggestion_title",
                "suggestion_category", "engagement_seconds"
            ]],
            use_container_width=True,
            height=400
        )
        
        # Engagement time stats
        st.subheader("Engagement Time Stats")
        engagement_times = df[df["engagement_seconds"].notna()]["engagement_seconds"]
        if len(engagement_times) > 0:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Avg Engagement (sec)", f"{engagement_times.mean():.1f}")
            with col2:
                st.metric("Median Engagement (sec)", f"{engagement_times.median():.1f}")
            with col3:
                st.metric("Max Engagement (sec)", f"{engagement_times.max():.0f}")
    
    except Exception as e:
        st.error(f"Failed to load outcomes: {e}")


def render_skills_tab():
    """Render learned skills and preferences."""
    if not STREAMLIT_AVAILABLE:
        return
    
    st.header("Learned Skills & Preferences")
    st.markdown("Patterns discovered from user interactions (Phase 2).")
    
    try:
        # Get skills
        skills = get_skill_summary(limit=50)
        prefs = get_preferences()
        
        # Skills section
        if skills:
            st.subheader("Discovered Skills")
            df_skills = pd.DataFrame(skills)
            st.dataframe(
                df_skills[[
                    "skill_name", "category", "confidence", "signal_strength"
                ]],
                use_container_width=True
            )
        else:
            st.info("No skills discovered yet (Phase 2 feature).")
        
        # Preferences section
        if prefs:
            st.subheader("User Preferences")
            df_prefs = pd.DataFrame(
                [{"key": k, "value": str(v)} for k, v in prefs.items()],
                columns=["Key", "Value"]
            )
            st.dataframe(df_prefs, use_container_width=True)
        else:
            st.info("No preferences recorded yet.")
    
    except Exception as e:
        st.error(f"Failed to load skills: {e}")


def render_sidebar():
    """Render sidebar navigation and settings."""
    if not STREAMLIT_AVAILABLE:
        return
    
    with st.sidebar:
        st.title("Navigation")
        
        page = st.radio(
            "Select view",
            [
                "📊 Overview",
                "📝 Events",
                "👥 Outcomes",
                "🎯 Skills & Prefs",
                "🛠 Debug",
            ],
            label_visibility="collapsed"
        )
        
        st.divider()
        
        st.markdown("### About")
        st.info("""
        **Learning Layer** captures Explore Mode interactions.
        
        - Phase 1: Event & outcome recording ✅
        - Phase 2: Skill discovery (future)
        - Phase 3: Personalized ranking (future)
        """)
        
        st.divider()
        
        st.markdown("### Data Source")
        st.code("data/learning.db", language="text")
        
        st.divider()
        
        return page


def render_debug_tab():
    """Debug section for development."""
    if not STREAMLIT_AVAILABLE:
        return
    
    st.header("🛠 Debug")
    
    try:
        summary = debug_summary()
        st.json(summary)
        
        if st.button("Clear all data (WARNING)"):
            st.warning("Not implemented for safety. Delete data/learning.db manually if needed.")
    
    except Exception as e:
        st.error(f"Debug failed: {e}")


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

def main():
    """Main Streamlit app."""
    if not STREAMLIT_AVAILABLE:
        print("❌ Streamlit not installed.")
        print("   Install with: pip install streamlit pandas")
        print("\nThis file is a TEMPLATE showing where a Streamlit UI would read from.")
        print("It documents the learning_db.py API that any UI should use.")
        return
    
    configure_page()
    render_header()
    
    # Sidebar navigation
    page = render_sidebar()
    
    # Route to page
    if page == "📊 Overview":
        render_overview()
    elif page == "📝 Events":
        render_events_tab()
    elif page == "👥 Outcomes":
        render_outcomes_tab()
    elif page == "🎯 Skills & Prefs":
        render_skills_tab()
    elif page == "🛠 Debug":
        render_debug_tab()


# ---------------------------------------------------------------------------
# API Documentation
# ---------------------------------------------------------------------------

"""
STREAMLIT UI — READ API REFERENCE

When building the actual Streamlit UI, import from learning_db.py:

1. **Overview Metrics**
   from learning_db import:
   - count_events_by_type() -> dict[str, int]
   - count_outcomes_by_type() -> dict[str, int]
   - debug_summary() -> dict[str, int]

2. **Events Table**
   from learning_db import:
   - get_event_summary(limit: int = 100) -> list[dict]
   
   Returns: {id, timestamp_utc, event_type, session_id, metadata}

3. **Outcomes Table**
   from learning_db import:
   - get_outcome_summary(limit: int = 100) -> list[dict]
   
   Returns: {id, timestamp_utc, outcome_type, suggestion_title, 
             suggestion_category, engagement_seconds, feedback}

4. **Skills & Preferences**
   from learning_db import:
   - get_skill_summary(limit: int = 50) -> list[dict]
   - get_preferences(source: str | None = None) -> dict
   
   skill_summary returns: {id, skill_name, category, confidence, signal_strength}
   get_preferences returns: {pref_key: value}

5. **Time-Series Analysis**
   - Query events/outcomes tables with timestamp_utc for trends
   - Group by outcome_type to see user behavior patterns
   - Filter by session_id for session-level analysis

6. **Data Files**
   - DB: data/learning.db (SQLite with WAL mode)
   - No CSV exports yet; could add via learning_db functions
   - Retention: unlimited (Phase 2: add auto-cleanup)

7. **Update Frequency**
   - Real-time: events written as they happen
   - Queries: any time, no locking issues (WAL mode safe)
   - Reload interval suggested: 5-30 seconds for live dashboard

8. **Permissions**
   - Read-only for UI (no INSERT/UPDATE from Streamlit)
   - All writes via learning_db.py functions (event/outcome/skill recording)
   - No admin functions exposed to UI

9. **Future Phases**
   - Phase 2: Add skill inference from outcomes
   - Phase 3: Add skill usage in ranking/filtering
   - Phase 4: Add auto-export to CSV or data warehouse
   - Phase 5: Add annotations & manual corrections
"""


if __name__ == "__main__":
    main()
