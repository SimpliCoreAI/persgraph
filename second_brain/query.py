"""Query engine — retrieves context and answers via LLM."""

from typing import Any

import httpx
from ollama import Client

from .config import settings
from .embeddings import embedder
from .vectorstore import vectorstore


SYSTEM_PROMPT = """You are a private second brain assistant. You have been given context documents below.

STRICT RULES:
- Answer using ONLY the information in the context provided.
- Do NOT greet the user or ask how to assist.
- Do NOT say "how can I help you" or similar phrases.
- If the answer is not in the context, say: "I don't have information about this in my knowledge base."
- Be concise, factual, and cite sources by number [1], [2], etc."""

# Qwen2.5:72b is large — give it plenty of time
OLLAMA_TIMEOUT = httpx.Timeout(timeout=600.0, connect=10.0)


def retrieve(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Retrieve the most relevant chunks for a query."""
    embedding = embedder.embed(query)
    return vectorstore.query_all(embedding, top_k=top_k)


def answer(query: str, top_k: int = 5) -> tuple[str, list[dict[str, Any]]]:
    """
    Retrieve context and generate an answer.

    Returns:
        Tuple of (answer_text, source_chunks)
    """
    chunks = retrieve(query, top_k)

    if not chunks:
        return "No relevant content found. Try ingesting some documents first.", []

    # Build context block
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk["metadata"].get("filename", chunk["collection"])
        context_parts.append(f"[{i}] ({source}):\n{chunk['text']}")

    context = "\n\n".join(context_parts)

    prompt = f"""{SYSTEM_PROMPT}

### CONTEXT DOCUMENTS:
{context}

### QUESTION:
{query}

### ANSWER (based only on the context above):"""

    client = Client(host=settings.ollama_base_url, timeout=OLLAMA_TIMEOUT)

    # Stream response — avoids timeout waiting for full 72B output
    full_response = ""
    for chunk_resp in client.generate(model=settings.llm_model, prompt=prompt, stream=True):
        full_response += chunk_resp["response"]

    return full_response.strip(), chunks
