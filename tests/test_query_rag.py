"""Tests for the RAG/query path.

These tests are offline-safe: embeddings and Chroma are mocked so they can run
when Ollama or the vector backend is unavailable.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch


class TestQueryRAG(unittest.TestCase):
    def test_retrieve_uses_embedding_and_vectorstore(self):
        import second_brain.query as query
        with patch.object(query, "embedder") as mock_embedder, patch.object(query, "vectorstore") as mock_vectorstore:
            mock_embedder.embed.return_value = [0.1, 0.2, 0.3]
            mock_vectorstore.query_all.return_value = [
                {"text": "chunk 1", "metadata": {"filename": "doc.md"}, "collection": "notes"}
            ]

            results = query.retrieve("what is rag?", top_k=3)

            mock_embedder.embed.assert_called_once_with("what is rag?")
            mock_vectorstore.query_all.assert_called_once_with([0.1, 0.2, 0.3], top_k=3)
            self.assertEqual(results[0]["text"], "chunk 1")

    def test_build_context_returns_context_and_chunks(self):
        import second_brain.query as query
        with patch.object(query, "embedder") as mock_embedder, patch.object(query, "vectorstore") as mock_vectorstore:
            mock_embedder.embed.return_value = [0.1]
            mock_vectorstore.query_all.return_value = [
                {"text": "First chunk about RAG.", "metadata": {"filename": "rag-notes.md"}, "collection": "notes"},
                {"text": "Second chunk about context packing.", "metadata": {"filename": "context.md"}, "collection": "notes"},
            ]

            context, chunks = query.build_context("how should context be packed?", top_k=2)

            self.assertIn("[1] (rag-notes.md):", context)
            self.assertIn("First chunk about RAG.", context)
            self.assertIn("[2] (context.md):", context)
            self.assertEqual(len(chunks), 2)

    def test_answer_builds_context_from_retrieved_chunks(self):
        import second_brain.query as query
        with patch.object(query, "embedder") as mock_embedder, patch.object(query, "vectorstore") as mock_vectorstore, patch.object(query, "complete_stream") as mock_stream:
            mock_embedder.embed.return_value = [0.1, 0.2, 0.3]
            mock_vectorstore.query_all.return_value = [
                {
                    "text": "First chunk about RAG.",
                    "metadata": {"filename": "rag-notes.md"},
                    "collection": "notes",
                },
                {
                    "text": "Second chunk about context packing.",
                    "metadata": {"filename": "context.md"},
                    "collection": "notes",
                },
            ]
            mock_stream.return_value = iter(["answer from llm"])

            response, chunks = query.answer("how should context be packed?", top_k=2)

            self.assertEqual(response, "answer from llm")
            self.assertEqual(len(chunks), 2)
            self.assertTrue(mock_stream.called)
            prompt = mock_stream.call_args.args[0]
            self.assertIn("### CONTEXT DOCUMENTS:", prompt)
            self.assertIn("[1] (rag-notes.md):", prompt)
            self.assertIn("First chunk about RAG.", prompt)
            self.assertIn("[2] (context.md):", prompt)
            self.assertIn("Second chunk about context packing.", prompt)

    def test_answer_handles_empty_retrieval(self):
        import second_brain.query as query
        with patch.object(query, "embedder") as mock_embedder, patch.object(query, "vectorstore") as mock_vectorstore, patch.object(query, "complete_stream") as mock_stream:
            mock_embedder.embed.return_value = [0.1]
            mock_vectorstore.query_all.return_value = []
            mock_stream.return_value = iter(["should not be used"])

            response, chunks = query.answer("unknown topic")

            self.assertEqual(response, "No relevant content found. Try ingesting some documents first.")
            self.assertEqual(chunks, [])
            mock_stream.assert_not_called()

    def test_build_context_surfaces_embedding_failure(self):
        import second_brain.query as query
        with patch.object(query, "embedder") as mock_embedder, patch.object(query, "vectorstore") as mock_vectorstore:
            mock_embedder.embed.side_effect = RuntimeError("Ollama unavailable")

            with self.assertRaises(query.ContextBrokerError) as ctx:
                query.build_context("rag context")
            self.assertIn("Ollama unavailable", str(ctx.exception))
            mock_vectorstore.query_all.assert_not_called()


if __name__ == "__main__":
    unittest.main()
