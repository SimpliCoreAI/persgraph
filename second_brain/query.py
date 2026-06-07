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
    from .tracing import trace_event
    
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
