"""✅ Tasks & Notes — Capture and search tasks, appointments, and notes."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import streamlit as st
from datetime import date

from second_brain.notes import save, search, list_all, delete, count, TYPES

st.set_page_config(page_title="Tasks & Notes", page_icon="✅", layout="wide")


# ── Render helper (defined first) ────────────────────────────────────────────
def _render_item(item: dict, show_score: bool = False) -> None:
    """Render a single note/task/appointment card."""
    icon = {"Task": "☑️", "Appointment": "📅", "Note": "📝"}.get(item.get("type", "Note"), "📝")
    title = item.get("title", "Untitled")
    item_type = item.get("type", "Note")
    item_date = item.get("date", "")
    tags = item.get("tags", "")
    body = item.get("body", "")
    item_id = item.get("id", "")
    created = item.get("created_at", "")[:10]
    score = item.get("score")

    label = f"{icon} **{title}**"
    if item_date:
        label += f" · 📆 {item_date}"
    if show_score and score is not None:
        label += f" · relevance: {score:.2f}"

    with st.expander(label):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption(f"`{item_type}` · added {created} · tags: {tags or '—'}")
            if body:
                st.write(body)
        with col2:
            if item_id and st.button("🗑️ Delete", key=f"del_{item_id}"):
                try:
                    delete(item_id)
                    st.success("Deleted")
                    st.rerun()
                except Exception as e:
                    st.error(f"Delete failed: {e}")


# ── Page ──────────────────────────────────────────────────────────────────────
st.title("✅ Tasks & Notes")
st.caption("Quick capture — semantically searchable via ChromaDB.")
st.divider()

# Stats bar
try:
    total = count()
    tasks = len(list_all("Task"))
    appts = len(list_all("Appointment"))
    notes = len(list_all("Note"))
except Exception:
    total = tasks = appts = notes = 0

col_s1, col_s2, col_s3, col_s4 = st.columns(4)
col_s1.metric("Total items", total)
col_s2.metric("Tasks", tasks)
col_s3.metric("Appointments", appts)
col_s4.metric("Notes", notes)

st.divider()

# ── Layout: Add (left) | Search (right) ──────────────────────────────────────
left, right = st.columns([1, 1], gap="large")

# ── ADD ───────────────────────────────────────────────────────────────────────
with left:
    st.markdown("### ➕ Quick Capture")

    with st.form("add_item", clear_on_submit=True):
        item_type = st.selectbox("Type", TYPES)
        title = st.text_input("Title *", placeholder="e.g. Dentist at 2pm, Review Q1 portfolio")
        body = st.text_area("Details (optional)", height=80)

        col_d, col_t = st.columns(2)
        with col_d:
            item_date = st.date_input("Date (optional)", value=None)
        with col_t:
            tags_raw = st.text_input("Tags", placeholder="health, finance, travel")

        submitted = st.form_submit_button("💾 Save", type="primary")

        if submitted:
            if not title.strip():
                st.error("Title is required.")
            else:
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                date_str = item_date.isoformat() if item_date else ""
                try:
                    save(
                        title=title.strip(),
                        item_type=item_type,
                        body=body.strip(),
                        date=date_str,
                        tags=tags,
                    )
                    st.success(f"✅ Saved [{item_type}]: {title}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving: {e}")

# ── SEARCH ────────────────────────────────────────────────────────────────────
with right:
    st.markdown("### 🔍 Semantic Search")

    search_query = st.text_input(
        "Search notes",
        placeholder="what do I have next week? / notes about investing",
    )

    col_r1, col_r2 = st.columns([2, 1])
    with col_r1:
        search_btn = st.button("🔍 Search", type="primary", disabled=not search_query.strip())
    with col_r2:
        top_k = st.number_input("Results", min_value=1, max_value=20, value=5)

    if search_btn and search_query.strip():
        with st.spinner("Searching..."):
            try:
                results = search(search_query.strip(), top_k=int(top_k))
                if not results:
                    st.info("No results found.")
                else:
                    st.success(f"{len(results)} results")
                    for r in results:
                        _render_item(r, show_score=True)
            except Exception as e:
                st.error(f"Search error: {e}")

st.divider()

# ── BROWSE ────────────────────────────────────────────────────────────────────
st.markdown("### 📋 All Items")

filter_type = st.radio("Filter", ["All"] + TYPES, horizontal=True)

try:
    items = list_all(item_type=None if filter_type == "All" else filter_type, limit=100)
except Exception as e:
    st.error(f"Could not load items: {e}")
    items = []

if not items:
    st.info("No items yet. Add your first one above! 👆")
else:
    for item in items:
        _render_item(item)
