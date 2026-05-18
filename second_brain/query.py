"""Query engine — retrieves context and answers via LLM."""

from typing import Any

from ollama import Client

from .config import settings
from .embeddings import embedder
from .vectorstore import vectorstore


SYSTEM_PROMPT = """You are a private second brain assistant.
Answer questions using ONLY the provided context.
If the answer is not in the context, say so clearly.
Be concise, precise, and cite your sources by number."""


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

Context:
{context}

Question: {query}

Answer:"""

    client = Client(host=settings.ollama_base_url)
    response = client.generate(model=settings.llm_model, prompt=prompt)
    return response["response"].strip(), chunks
