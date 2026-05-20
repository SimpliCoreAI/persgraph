"""🗺️ Travel & POI — Personal place notes with auto-tagging and charts."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import streamlit as st
import plotly.express as px
import pandas as pd
from collections import Counter

from second_brain.places import (
    save, search, list_all, delete, count, cities, countries, CATEGORIES
)

st.set_page_config(page_title="Travel & POI", page_icon="🗺️", layout="wide")


# ── Render helper ─────────────────────────────────────────────────────────────
def _render_place(place: dict, show_score: bool = False) -> None:
    rating = place.get("rating", 0)
    stars = "⭐" * int(rating) if rating else ""
    tags = [t.strip() for t in place.get("tags", "").split(",") if t.strip()]
    score_str = f" · relevance: {place['score']:.2f}" if show_score and place.get("score") else ""
    country = place.get("country", "")
    location = f"{place.get('city', '')}, {country}" if country else place.get("city", "")

    label = f"📍 **{place.get('name', 'Unknown')}** · {location} · `{place.get('category', '')}` {stars}{score_str}"

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

# Load all places once
try:
    all_places = list_all(limit=500)
except Exception:
    all_places = []

all_cities = sorted(set(p.get("city", "").strip() for p in all_places if p.get("city")))
all_countries = sorted(set(p.get("country", "").strip() for p in all_places if p.get("country")))

# ── Stats ─────────────────────────────────────────────────────────────────────
col_s1, col_s2, col_s3 = st.columns(3)
col_s1.metric("Places saved", len(all_places))
col_s2.metric("Cities", len(all_cities))
col_s3.metric("Countries", len(all_countries))

st.divider()

# ── Charts ────────────────────────────────────────────────────────────────────
if all_places:
    st.markdown("### 📊 Overview")
    chart_col1, chart_col2 = st.columns(2)

    # Bar chart: Places by Country
    with chart_col1:
        country_counts = Counter(
            p.get("country", "Unknown").strip() or "Unknown"
            for p in all_places
        )
        df_country = pd.DataFrame(
            country_counts.most_common(),
            columns=["Country", "Places"]
        )
        fig1 = px.bar(
            df_country,
            x="Country", y="Places",
            title="Places by Country",
            color="Places",
            color_continuous_scale="Blues",
            text="Places",
        )
        fig1.update_traces(textposition="outside")
        fig1.update_layout(showlegend=False, coloraxis_showscale=False, height=350)
        st.plotly_chart(fig1, use_container_width=True)

    # Bar chart: Places by Category
    with chart_col2:
        cat_counts = Counter(p.get("category", "Other") for p in all_places)
        df_cat = pd.DataFrame(
            cat_counts.most_common(),
            columns=["Category", "Places"]
        )
        fig2 = px.bar(
            df_cat,
            x="Category", y="Places",
            title="Places by Category",
            color="Places",
            color_continuous_scale="Greens",
            text="Places",
        )
        fig2.update_traces(textposition="outside")
        fig2.update_layout(showlegend=False, coloraxis_showscale=False, height=350)
        st.plotly_chart(fig2, use_container_width=True)

    # Bar chart: Top cities
    city_counts = Counter(
        p.get("city", "Unknown").strip() or "Unknown"
        for p in all_places
    )
    if len(city_counts) > 1:
        df_city = pd.DataFrame(
            city_counts.most_common(15),
            columns=["City", "Places"]
        )
        fig3 = px.bar(
            df_city,
            x="City", y="Places",
            title="Top Cities",
            color="Places",
            color_continuous_scale="Oranges",
            text="Places",
        )
        fig3.update_traces(textposition="outside")
        fig3.update_layout(showlegend=False, coloraxis_showscale=False, height=350)
        st.plotly_chart(fig3, use_container_width=True)

    st.divider()

# ── Layout: Add | Search ──────────────────────────────────────────────────────
left, right = st.columns([1, 1], gap="large")

# ── ADD ───────────────────────────────────────────────────────────────────────
with left:
    st.markdown("### ➕ Add Place")

    with st.form("add_place"):
        name = st.text_input("Place name *", placeholder="e.g. Nagarjuna Restaurant")

        col_city, col_country = st.columns(2)
        with col_city:
            city = st.text_input("City *", placeholder="e.g. Bangalore")
        with col_country:
            country = st.text_input("Country *", placeholder="e.g. India")

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
                            country=country.strip(),
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
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        filter_city = st.selectbox("Filter by city", ["All cities"] + all_cities)
    with col_r2:
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

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    browse_country = st.selectbox("Country", ["All"] + all_countries, key="browse_country")
with col_f2:
    browse_city = st.selectbox("City", ["All"] + all_cities, key="browse_city")
with col_f3:
    browse_cat = st.selectbox("Category", ["All"] + CATEGORIES, key="browse_cat")

try:
    filtered = [
        p for p in all_places
        if (browse_country == "All" or p.get("country", "") == browse_country)
        and (browse_city == "All" or p.get("city", "") == browse_city)
        and (browse_cat == "All" or p.get("category", "") == browse_cat)
    ]
except Exception as e:
    st.error(f"Could not filter: {e}")
    filtered = []

if not filtered:
    st.info("No places found. Add your first one! 📍")
else:
    st.caption(f"{len(filtered)} places")
    for place in filtered:
        _render_place(place)
