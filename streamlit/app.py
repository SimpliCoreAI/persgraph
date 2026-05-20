"""
Second Brain — Streamlit Dashboard
Run: streamlit run streamlit/app.py --server.address 100.x.x.x --server.port 8501
"""

import streamlit as st

st.set_page_config(
    page_title="Second Brain",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🧠 Second Brain")
    st.caption("Private · Local · Yours")
    st.divider()
    st.markdown("**System**")
    st.page_link("pages/1_learning_agent.py",  label="🎓 Learning Agent")
    st.page_link("pages/2_snippets.py",         label="📎 Snippets")
    st.page_link("pages/3_tasks_notes.py",      label="✅ Tasks & Notes")
    st.page_link("pages/4_portfolio.py",        label="💼 Portfolio")
    st.page_link("pages/5_credit_card.py",      label="💳 Credit Card Agent")
    st.page_link("pages/6_travel.py",           label="🗺️ Travel & POI")
    st.page_link("pages/7_weekly_briefing.py",  label="📋 Weekly Briefing")
    st.divider()
    st.caption("Connected to Windows via Tailscale")

# ── Home ─────────────────────────────────────────────────────────────────────
st.title("🧠 Second Brain")
st.subheader("Your private, local-first AI assistant")
st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.info("**🎓 Learning Agent**\nAsk questions over your ingested docs, notes, and URLs.")
    st.info("**📎 Snippets**\nSemantic search across your entire knowledge base.")

with col2:
    st.info("**✅ Tasks & Notes**\nCapture tasks, appointments, notes — semantically grouped.")
    st.info("**💼 Portfolio**\nFinancial analysis and charts from your documents.")

with col3:
    st.info("**💳 Credit Card Agent**\nStatement parsing and rewards optimization.")
    st.info("**🗺️ Travel & POI**\nPersonal place notes — restaurants, locations, hidden gems.")

st.divider()
st.success("**📋 Weekly Briefing** — Fires every Sunday at 8AM. Preview anytime from the sidebar.")
