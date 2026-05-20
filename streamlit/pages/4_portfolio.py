"""💼 Portfolio — Financial document analysis and charts."""

import streamlit as st

st.set_page_config(page_title="Portfolio", page_icon="💼", layout="wide")
st.title("💼 Portfolio")
st.caption("Upload statements and portfolio exports for analysis.")
st.divider()

# ── Upload ────────────────────────────────────────────────────────────────────
st.markdown("### ➕ Upload Document")
uploaded = st.file_uploader("Upload portfolio export or statement (PDF/CSV)", type=["pdf", "csv"])
tags = st.text_input("Tags", placeholder="portfolio, 2025, Q1")

if st.button("📥 Ingest", type="primary", disabled=not uploaded):
    st.info("⚙️ Portfolio ingestion — coming soon")

st.divider()

# ── Query ─────────────────────────────────────────────────────────────────────
st.markdown("### 🔍 Analyze")
query = st.text_input("Ask about your portfolio", placeholder="What are my returns for 2025? / Summarize my holdings")

if st.button("Analyze", disabled=not query.strip()):
    st.info("⚙️ Portfolio RAG query — coming soon")

st.divider()

# ── Charts placeholder ────────────────────────────────────────────────────────
st.markdown("### 📊 Charts")
col1, col2 = st.columns(2)
with col1:
    st.info("📈 Returns chart — coming soon")
with col2:
    st.info("🥧 Holdings breakdown — coming soon")
