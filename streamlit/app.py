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

# Sidebar branding only — page nav handled automatically by Streamlit
with st.sidebar:
    st.title("🧠 Second Brain")
    st.caption("Private · Local · Yours")
    st.divider()
    st.caption("🔒 Connected to Windows via Tailscale")

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding: 2rem 0 1rem 0;">
    <h1 style="font-size: 3rem;">🧠 Second Brain</h1>
    <p style="font-size: 1.2rem; color: grey;">Private · Local · Yours · Powered by Qwen2.5 + ChromaDB</p>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Feature cards ─────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3, gap="medium")

with col1:
    st.markdown("""
    <div style="background:#1e3a5f; border-radius:12px; padding:1.5rem; margin-bottom:1rem; min-height:140px">
        <div style="font-size:2rem">🎓</div>
        <h3 style="margin:0.5rem 0 0.3rem 0">Learning Agent</h3>
        <p style="color:#aac4e0; margin:0">Ask questions over your ingested docs, notes, and URLs. Powered by local RAG.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="background:#1e3a5f; border-radius:12px; padding:1.5rem; min-height:140px">
        <div style="font-size:2rem">📎</div>
        <h3 style="margin:0.5rem 0 0.3rem 0">Snippets</h3>
        <p style="color:#aac4e0; margin:0">Semantic search across your entire knowledge base. Find anything, instantly.</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div style="background:#1a3d2b; border-radius:12px; padding:1.5rem; margin-bottom:1rem; min-height:140px">
        <div style="font-size:2rem">✅</div>
        <h3 style="margin:0.5rem 0 0.3rem 0">Tasks & Notes</h3>
        <p style="color:#a0c8b0; margin:0">Capture tasks, appointments, notes — semantically grouped and searchable.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="background:#1a3d2b; border-radius:12px; padding:1.5rem; min-height:140px">
        <div style="font-size:2rem">💼</div>
        <h3 style="margin:0.5rem 0 0.3rem 0">Portfolio</h3>
        <p style="color:#a0c8b0; margin:0">Upload statements and exports. Financial analysis and charts, all local.</p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div style="background:#3d1a1a; border-radius:12px; padding:1.5rem; margin-bottom:1rem; min-height:140px">
        <div style="font-size:2rem">💳</div>
        <h3 style="margin:0.5rem 0 0.3rem 0">Credit Card Agent</h3>
        <p style="color:#c8a0a0; margin:0">Parse statements, track spend, optimize rewards across all your cards.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="background:#3d1a1a; border-radius:12px; padding:1.5rem; min-height:140px">
        <div style="font-size:2rem">🗺️</div>
        <h3 style="margin:0.5rem 0 0.3rem 0">Travel & POI</h3>
        <p style="color:#c8a0a0; margin:0">Personal place notes — restaurants, hidden gems, and locations by city.</p>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ── Weekly briefing banner ────────────────────────────────────────────────────
st.markdown("""
<div style="background:#2d2047; border-radius:12px; padding:1.2rem 1.5rem; display:flex; align-items:center; gap:1rem">
    <span style="font-size:2rem">📋</span>
    <div>
        <strong style="font-size:1.1rem">Weekly Briefing</strong>
        <p style="margin:0.2rem 0 0 0; color:#b0a0d0">Fires every Sunday at 8:00 AM — delivered to Telegram + Email. Preview or trigger manually from the sidebar.</p>
    </div>
</div>
""", unsafe_allow_html=True)

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
