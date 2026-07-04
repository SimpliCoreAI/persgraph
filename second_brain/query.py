"""Query engine — retrieves context and answers via LLM."""

from typing import Any

from .embeddings import embedder
from .llm import complete_stream
from .vectorstore import vectorstore


SYSTEM_PROMPT = """You are a private second brain assistant. You have been given context documents below.

STRICT RULES:
- Answer using ONLY the information in the context provided.
- Do NOT greet the user or ask how to assist.
- Do NOT say "how can I help you" or similar phrases.
- If the answer is not in the context, say: "I don't have information about this in my knowledge base."
- Be concise, factual, and cite sources by number [1], [2], etc."""


class ContextBrokerError(RuntimeError):
    """Raised when semantic retrieval is unavailable but fallback context is still needed."""


def _build_context_block(chunks: list[dict[str, Any]]) -> str:
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata") or {}
        source = metadata.get("filename", chunk.get("collection", "unknown"))
        context_parts.append(f"[{i}] ({source}):\n{chunk['text']}")
    return "\n\n".join(context_parts)


def build_context(query: str, top_k: int = 5) -> tuple[str, list[dict[str, Any]]]:
    """Retrieve context chunks and return a formatted context block.

    This is the semantic retrieval leg of the broker. If embeddings or vector
    lookup fail, callers can fall back to other context sources or answer
    without RAG content.
    """
    try:
        embedding = embedder.embed(query)
        chunks = vectorstore.query_all(embedding, top_k=top_k)
    except Exception as exc:
        raise ContextBrokerError(str(exc)) from exc

    return _build_context_block(chunks), chunks


def retrieve(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Retrieve the most relevant chunks for a query."""
    _, chunks = build_context(query, top_k=top_k)
    return chunks


def answer(query: str, top_k: int = 5) -> tuple[str, list[dict[str, Any]]]:
    """
    Retrieve context and generate an answer.

    Returns:
        Tuple of (answer_text, source_chunks)
    """
    from .tracing import trace_event

    try:
        context, chunks = build_context(query, top_k=top_k)
    except ContextBrokerError:
        context = ""
        chunks = []

    if not chunks:
        return "No relevant content found. Try ingesting some documents first.", []

    prompt = f"""{SYSTEM_PROMPT}

### CONTEXT DOCUMENTS:
{context}

### QUESTION:
{query}

### ANSWER (based only on the context above):"""

    trace_event(
        name="query_answer",
        input=f"query: {query[:100]}",
        tags=["query", "llm", "litellm"]
    )

    # Stream via LiteLLM smart tier (Ollama fallback automatic)
    full_response = ""
    for token in complete_stream(prompt, tier="smart"):
        full_response += token

    trace_event(
        name="query_answer_result",
        output=f"response_len: {len(full_response)}",
        tags=["query", "llm", "litellm"]
    )
    return full_response.strip(), chunks
