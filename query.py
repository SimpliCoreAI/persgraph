#!/usr/bin/env python3
"""
Second Brain - Query
Usage: python query.py "What are my portfolio returns for 2025?"
"""

import argparse
import ollama
import chromadb

from config import (
    CHROMA_HOST, CHROMA_PORT,
    OLLAMA_BASE_URL, EMBED_MODEL, LLM_MODEL,
    COLLECTION_PDFS, COLLECTION_NOTES, COLLECTION_URLS,
    COLLECTION_EMAILS, COLLECTION_YOUTUBE
)

ALL_COLLECTIONS = [
    COLLECTION_PDFS, COLLECTION_NOTES,
    COLLECTION_URLS, COLLECTION_EMAILS, COLLECTION_YOUTUBE
]


def get_embedding(text: str) -> list[float]:
    client = ollama.Client(host=OLLAMA_BASE_URL)
    response = client.embeddings(model=EMBED_MODEL, prompt=text)
    return response["embedding"]


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """Retrieve top_k relevant chunks across all collections."""
    chroma = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    embedding = get_embedding(query)

    results = []
    for col_name in ALL_COLLECTIONS:
        try:
            col = chroma.get_collection(col_name)
            if col.count() == 0:
                continue
            res = col.query(
                query_embeddings=[embedding],
                n_results=min(top_k, col.count()),
                include=["documents", "metadatas", "distances"]
            )
            for doc, meta, dist in zip(
                res["documents"][0],
                res["metadatas"][0],
                res["distances"][0]
            ):
                results.append({
                    "collection": col_name,
                    "text": doc,
                    "metadata": meta,
                    "score": 1 - dist  # convert distance to similarity
                })
        except Exception:
            continue

    # Sort by similarity score
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def answer(query: str, top_k: int = 5):
    print(f"🔍 Searching second brain for: '{query}'\n")
    chunks = retrieve(query, top_k)

    if not chunks:
        print("❌ No relevant content found. Try ingesting some documents first.")
        return

    # Build context
    context = ""
    for i, chunk in enumerate(chunks):
        source = chunk["metadata"].get("filename", chunk["collection"])
        context += f"[{i+1}] ({source}):\n{chunk['text']}\n\n"

    prompt = f"""You are a personal second brain assistant. Use ONLY the context below to answer the question. 
If the answer isn't in the context, say so clearly. Be concise and precise.

Context:
{context}

Question: {query}

Answer:"""

    print("🧠 Thinking with Qwen2.5...\n")
    client = ollama.Client(host=OLLAMA_BASE_URL)
    response = client.generate(model=LLM_MODEL, prompt=prompt, stream=True)

    for chunk in response:
        print(chunk["response"], end="", flush=True)
    print("\n")

    print("📚 Sources used:")
    for i, chunk in enumerate(chunks):
        source = chunk["metadata"].get("filename", chunk["collection"])
        score = chunk["score"]
        print(f"  [{i+1}] {source} (relevance: {score:.2f})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query your Second Brain")
    parser.add_argument("query", help="Your question")
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve")
    args = parser.parse_args()

    answer(args.query, args.top_k)
