"""
Second Brain — Streamlit Dashboard
Run: streamlit run streamlit/app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Second Brain",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar branding only — page nav is handled automatically by Streamlit
with st.sidebar:
    st.title("🧠 Second Brain")
    st.caption("Private · Local · Yours")
    st.divider()
    st.caption("Connected to Windows via Tailscale")

# ── Home ──────────────────────────────────────────────────────────────────────
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
