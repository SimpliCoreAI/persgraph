"""✅ Tasks & Notes — Capture and search tasks, appointments, and notes."""

import streamlit as st
from datetime import datetime

st.set_page_config(page_title="Tasks & Notes", page_icon="✅", layout="wide")
st.title("✅ Tasks & Notes")
st.caption("Quick capture — tasks, appointments, notes. Semantically searchable.")
st.divider()

# ── Add ───────────────────────────────────────────────────────────────────────
st.markdown("### ➕ Quick Capture")

col1, col2 = st.columns([1, 2])
with col1:
    item_type = st.selectbox("Type", ["Task", "Appointment", "Note"])
with col2:
    title = st.text_input("Title", placeholder="e.g. Dentist appointment, Review Q1 portfolio")

body = st.text_area("Details (optional)", height=80)

col3, col4 = st.columns(2)
with col3:
    date = st.date_input("Date (optional)", value=None)
with col4:
    tags = st.text_input("Tags (optional)", placeholder="health, finance, travel")

if st.button("💾 Save", type="primary", disabled=not title.strip()):
    # TODO: wire to ChromaDB notes collection
    st.success(f"✅ Saved: [{item_type}] {title}")
    st.info("⚙️ ChromaDB notes collection — coming soon")

st.divider()

# ── Search ────────────────────────────────────────────────────────────────────
st.markdown("### 🔍 Search")
search = st.text_input("Search notes", placeholder="what do I have next week? / notes about investing")

if st.button("Search", disabled=not search.strip()):
    # TODO: wire to RAG query on notes collection
    st.info("⚙️ Semantic search over notes — coming soon")

st.divider()

# ── Placeholder list ──────────────────────────────────────────────────────────
st.markdown("### 📋 Recent")
st.info("Your tasks and notes will appear here once the notes collection is wired up.")
