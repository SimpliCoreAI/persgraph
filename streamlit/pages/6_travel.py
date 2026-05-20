"""🗺️ Travel & POI — Personal place notes and hidden gems."""

import streamlit as st

st.set_page_config(page_title="Travel & POI", page_icon="🗺️", layout="wide")
st.title("🗺️ Travel & POI")
st.caption("Your personal place notes — restaurants, locations, hidden gems.")
st.divider()

# ── Add ───────────────────────────────────────────────────────────────────────
st.markdown("### ➕ Add Place")

col1, col2, col3 = st.columns(3)
with col1:
    name = st.text_input("Place name", placeholder="e.g. Nagarjuna Restaurant")
with col2:
    city = st.text_input("City", placeholder="e.g. Bangalore")
with col3:
    category = st.selectbox("Category", ["Restaurant", "Cafe", "Market", "Landmark", "Hotel", "Bar", "Other"])

notes = st.text_area("Notes", placeholder="Amazing biryani, try the Andhra thali. Go before 1pm — gets crowded.", height=80)
tags = st.text_input("Tags", placeholder="indian, biryani, must-visit")

if st.button("📍 Save Place", type="primary", disabled=not name.strip()):
    st.info("⚙️ Travel ChromaDB collection — coming soon")

st.divider()

# ── Search ────────────────────────────────────────────────────────────────────
st.markdown("### 🔍 Search Places")

col4, col5 = st.columns([3, 1])
with col4:
    search = st.text_input("Search", placeholder="what did I save about Bangalore food? / hidden gems in Tokyo")
with col5:
    filter_city = st.text_input("Filter by city", placeholder="optional")

if st.button("Search", disabled=not search.strip()):
    st.info("⚙️ Travel semantic search — coming soon")

st.divider()

# ── Browse ────────────────────────────────────────────────────────────────────
st.markdown("### 🗂️ Browse")
view = st.radio("View by", ["City", "Category"], horizontal=True)
st.info(f"⚙️ Browse by {view} — coming soon")
