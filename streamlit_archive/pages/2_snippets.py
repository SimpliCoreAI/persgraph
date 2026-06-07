"""📎 Snippets — Semantic search across your entire knowledge base."""

import streamlit as st

st.set_page_config(page_title="Snippets", page_icon="📎", layout="wide")
st.title("📎 Snippets")
st.caption("Semantic search across your entire knowledge base.")
st.divider()

query = st.text_input("Search", placeholder="e.g. context window, portfolio returns, dental")
top_k = st.slider("Results", 1, 20, 10)

if st.button("🔍 Search", type="primary", disabled=not query.strip()):
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
    from second_brain.query import retrieve

    with st.spinner("Searching..."):
        results = retrieve(query, top_k=top_k)

    if not results:
        st.warning("No results found.")
    else:
        st.success(f"{len(results)} results")
        for i, r in enumerate(results, 1):
            source = r["metadata"].get("filename") or r["metadata"].get("source", "—")
            with st.expander(f"[{i}] {source} · score: {r['score']:.2f} · `{r['collection']}`"):
                st.caption(f"Tags: {r['metadata'].get('tags', '—')} | Ingested: {r['metadata'].get('ingested_at', '—')[:10]}")
                st.write(r["text"])
