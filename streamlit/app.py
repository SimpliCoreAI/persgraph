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

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🧠 Second Brain")
    st.caption("Private · Local · Yours")
    st.divider()
    st.page_link("app.py",                          label="🏠 Home")
    st.page_link("pages/1_learning_agent.py",       label="🎓 Learning Agent")
    st.page_link("pages/2_snippets.py",             label="📎 Snippets")
    st.page_link("pages/3_tasks_notes.py",          label="✅ Tasks & Notes")
    st.page_link("pages/4_portfolio.py",            label="💼 Portfolio")
    st.page_link("pages/5_credit_card.py",          label="💳 Credit Card Agent")
    st.page_link("pages/6_travel.py",               label="🗺️ Travel & POI")
    st.page_link("pages/7_weekly_briefing.py",      label="📋 Weekly Briefing")
    st.page_link("pages/8_recurring_events.py",    label="🔁 Recurring Events")
    st.divider()
    st.caption("🔒 Connected via Tailscale")

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding: 2rem 0 1rem 0;">
    <h1 style="font-size: 3rem;">🧠 Second Brain</h1>
    <p style="font-size: 1.1rem; color: #666;">Private · Local · Yours · Powered by Qwen2.5 + ChromaDB</p>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Feature cards ─────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3, gap="medium")

with col1:
    st.info("**🎓 Learning Agent**\n\nAsk questions over your ingested docs, notes, and URLs. Powered by local RAG.")
    st.info("**📎 Snippets**\n\nSemantic search across your entire knowledge base. Find anything, instantly.")

with col2:
    st.success("**✅ Tasks & Notes**\n\nCapture tasks, appointments, notes — semantically grouped and searchable.")
    st.success("**💼 Portfolio**\n\nUpload statements and exports. Financial analysis and charts, all local.")

with col3:
    st.warning("**💳 Credit Card Agent**\n\nParse statements, track spend, optimize rewards across all your cards.")
    st.warning("**🗺️ Travel & POI**\n\nPersonal place notes — restaurants, hidden gems, and locations by city.")

st.divider()

# ── Weekly briefing banner ────────────────────────────────────────────────────
st.success("📋 **Weekly Briefing** — Fires every Sunday at 8:00 AM · Delivered via Telegram + Email · Preview anytime from the sidebar.")

st.divider()

# ── System status ─────────────────────────────────────────────────────────────
st.markdown("#### 🖥️ System Status")
col_a, col_b, col_c = st.columns(3)

with col_a:
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(__file__) + "/..")
        from second_brain.config import settings
        import httpx
        from ollama import Client
        Client(host=settings.ollama_base_url, timeout=httpx.Timeout(5.0)).list()
        st.success("🟢 Ollama — connected")
    except Exception:
        st.error("🔴 Ollama — unreachable")

with col_b:
    try:
        import chromadb
        from second_brain.config import settings
        chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port).heartbeat()
        st.success("🟢 ChromaDB — connected")
    except Exception:
        st.error("🔴 ChromaDB — unreachable")

with col_c:
    try:
        from second_brain.notes import count
        st.info(f"📦 Notes stored: {count()}")
    except Exception:
        st.info("📦 Notes: —")
