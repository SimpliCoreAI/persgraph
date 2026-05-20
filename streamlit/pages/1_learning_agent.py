"""🎓 Learning Agent — RAG-powered Q&A over your knowledge base."""

import streamlit as st

st.set_page_config(page_title="Learning Agent", page_icon="🎓", layout="wide")
st.title("🎓 Learning Agent")
st.caption("Ask questions over your ingested docs, notes, and URLs.")
st.divider()

# ── Query ─────────────────────────────────────────────────────────────────────
query = st.text_area(
    "Ask your second brain",
    placeholder="e.g. How does Anthropic decouple the brain from the hands?",
    height=80,
)

col1, col2 = st.columns([1, 4])
with col1:
    top_k = st.slider("Sources to retrieve", min_value=1, max_value=10, value=5)
with col2:
    st.write("")  # spacer

ask = st.button("🔍 Ask", type="primary", disabled=not query.strip())

if ask and query.strip():
    with st.spinner("Searching knowledge base..."):
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

            from second_brain.query import retrieve, SYSTEM_PROMPT
            from second_brain.config import settings
            import httpx
            from ollama import Client

            chunks = retrieve(query, top_k=top_k)

            if not chunks:
                st.warning("No relevant content found. Try ingesting some documents first.")
            else:
                # Build prompt
                context_parts = []
                for i, chunk in enumerate(chunks, 1):
                    source = chunk["metadata"].get("filename", chunk["collection"])
                    context_parts.append(f"[{i}] ({source}):\n{chunk['text']}")
                context = "\n\n".join(context_parts)
                prompt = (
                    f"{SYSTEM_PROMPT}\n\n"
                    f"### CONTEXT DOCUMENTS:\n{context}\n\n"
                    f"### QUESTION:\n{query}\n\n"
                    f"### ANSWER (based only on the context above):"
                )

                # Stream answer
                st.markdown("### 🧠 Answer")
                answer_box = st.empty()
                client = Client(
                    host=settings.ollama_base_url,
                    timeout=httpx.Timeout(timeout=600.0, connect=10.0),
                )
                full = ""
                for chunk_resp in client.generate(
                    model=settings.llm_model, prompt=prompt, stream=True
                ):
                    full += chunk_resp["response"]
                    answer_box.markdown(full + "▌")
                answer_box.markdown(full)

                # Sources
                st.divider()
                st.markdown("### 📚 Sources")
                for i, chunk in enumerate(chunks, 1):
                    with st.expander(
                        f"[{i}] {chunk['metadata'].get('filename', chunk['collection'])} "
                        f"· relevance: {chunk['score']:.2f}"
                    ):
                        st.caption(f"Collection: `{chunk['collection']}`")
                        st.caption(f"Tags: {chunk['metadata'].get('tags', '—')}")
                        st.text(chunk["text"][:600] + ("..." if len(chunk["text"]) > 600 else ""))

        except Exception as e:
            st.error(f"Error: {e}")

# ── Ingest ────────────────────────────────────────────────────────────────────
st.divider()
st.markdown("### ➕ Add to Knowledge Base")

tab_pdf, tab_url = st.tabs(["📄 PDF", "🌐 URL"])

with tab_pdf:
    uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
    tags_pdf = st.text_input("Tags (comma-separated)", key="tags_pdf", placeholder="financial, 2025")
    if st.button("Ingest PDF", disabled=not uploaded):
        import tempfile, os, sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
        from second_brain.ingesters.pdf import PDFIngester
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            f.write(uploaded.read())
            tmp_path = f.name
        with st.spinner("Ingesting..."):
            result = PDFIngester().ingest(tmp_path, tags=[t.strip() for t in tags_pdf.split(",") if t.strip()])
        os.unlink(tmp_path)
        if result.success:
            st.success(f"✅ Ingested {result.chunks_new} new chunks from {uploaded.name}")
        else:
            st.error(f"❌ {result.errors}")

with tab_url:
    url_input = st.text_input("URL", placeholder="https://example.com/article")
    tags_url = st.text_input("Tags (comma-separated)", key="tags_url", placeholder="research, ai")
    if st.button("Ingest URL", disabled=not url_input.strip()):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
        from second_brain.ingesters.url import URLIngester
        with st.spinner("Fetching and ingesting..."):
            result = URLIngester().ingest(url_input.strip(), tags=[t.strip() for t in tags_url.split(",") if t.strip()])
        if result.success:
            st.success(f"✅ Ingested {result.chunks_new} new chunks from {url_input}")
        else:
            st.error(f"❌ {result.errors}")
