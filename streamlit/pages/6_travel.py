"""🗺️ Travel & POI — Personal place notes with auto-tagging."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import streamlit as st
from second_brain.places import (
    save, search, list_all, delete, count, cities, auto_tag, CATEGORIES
)

st.set_page_config(page_title="Travel & POI", page_icon="🗺️", layout="wide")


# ── Render helper ─────────────────────────────────────────────────────────────
def _render_place(place: dict, show_score: bool = False) -> None:
    rating = place.get("rating", 0)
    stars = "⭐" * int(rating) if rating else ""
    tags = [t.strip() for t in place.get("tags", "").split(",") if t.strip()]
    score_str = f" · relevance: {place['score']:.2f}" if show_score and place.get("score") else ""

    label = f"📍 **{place.get('name', 'Unknown')}** · {place.get('city', '')} · `{place.get('category', '')}` {stars}{score_str}"

    with st.expander(label):
        col1, col2 = st.columns([4, 1])
        with col1:
            if place.get("notes"):
                st.write(place["notes"])
            if tags:
                st.markdown(" ".join(f"`{t}`" for t in tags))
            st.caption(f"Added: {place.get('created_at', '')[:10]}")
        with col2:
            place_id = place.get("id", "")
            if place_id and st.button("🗑️ Delete", key=f"del_{place_id}"):
                try:
                    delete(place_id)
                    st.success("Deleted")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))


# ── Page ──────────────────────────────────────────────────────────────────────
st.title("🗺️ Travel & POI")
st.caption("Personal place notes — restaurants, hidden gems, locations. Auto-tagged.")
st.divider()

# Stats
total = count()
all_cities = cities()
col_s1, col_s2 = st.columns(2)
col_s1.metric("Places saved", total)
col_s2.metric("Cities", len(all_cities))

st.divider()

# ── Layout ────────────────────────────────────────────────────────────────────
left, right = st.columns([1, 1], gap="large")

# ── ADD ───────────────────────────────────────────────────────────────────────
with left:
    st.markdown("### ➕ Add Place")

    with st.form("add_place"):
        name = st.text_input("Place name *", placeholder="e.g. Nagarjuna Restaurant")
        city = st.text_input("City *", placeholder="e.g. Bangalore, India")

        col_cat, col_rat = st.columns(2)
        with col_cat:
            category = st.selectbox("Category", CATEGORIES)
        with col_rat:
            rating = st.slider("Rating", 0, 5, 0)

        notes = st.text_area(
            "Notes",
            placeholder="Amazing Andhra biryani. Go before 1pm — gets crowded. Try the thali.",
            height=100,
        )
        extra_tags = st.text_input(
            "Extra tags (optional)",
            placeholder="must-visit, date-night — AI will auto-generate the rest",
        )

        submitted = st.form_submit_button("✨ Auto-tag & Save", type="primary")

        if submitted:
            if not name.strip() or not city.strip():
                st.error("Name and City are required.")
            else:
                extra = [t.strip() for t in extra_tags.split(",") if t.strip()]
                with st.spinner("Generating tags with AI..."):
                    try:
                        result = save(
                            name=name.strip(),
                            city=city.strip(),
                            category=category,
                            notes=notes.strip(),
                            rating=rating if rating > 0 else None,
                            extra_tags=extra,
                        )
                        tag_list = result.get("tags_list", [])
                        st.success(f"✅ Saved **{name}**!")
                        st.info(f"🏷️ Auto-tags: {', '.join(tag_list)}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

# ── SEARCH ────────────────────────────────────────────────────────────────────
with right:
    st.markdown("### 🔍 Search Places")

    query = st.text_input(
        "Search",
        placeholder="best biryani in Bangalore / coffee shops with wifi / hidden gems Tokyo",
    )
    filter_city = st.selectbox("Filter by city", ["All cities"] + all_cities)
    top_k = st.slider("Results", 1, 20, 8, key="search_topk")

    if st.button("🔍 Search", type="primary", disabled=not query.strip()):
        with st.spinner("Searching..."):
            try:
                city_filter = None if filter_city == "All cities" else filter_city
                results = search(query.strip(), top_k=top_k, city=city_filter)
                if not results:
                    st.info("No results found.")
                else:
                    st.success(f"{len(results)} results")
                    for r in results:
                        _render_place(r, show_score=True)
            except Exception as e:
                st.error(f"Search error: {e}")

st.divider()

# ── BROWSE ────────────────────────────────────────────────────────────────────
st.markdown("### 🗂️ Browse All Places")

col_f1, col_f2 = st.columns(2)
with col_f1:
    browse_city = st.selectbox("City", ["All"] + all_cities, key="browse_city")
with col_f2:
    browse_cat = st.selectbox("Category", ["All"] + CATEGORIES, key="browse_cat")

try:
    places = list_all(
        city=None if browse_city == "All" else browse_city,
        category=None if browse_cat == "All" else browse_cat,
    )
except Exception as e:
    st.error(f"Could not load places: {e}")
    places = []

if not places:
    st.info("No places saved yet. Add your first one! 📍")
else:
    st.caption(f"{len(places)} places")
    for place in places:
        _render_place(place)
