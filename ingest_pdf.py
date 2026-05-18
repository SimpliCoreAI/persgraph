#!/usr/bin/env python3
"""
Second Brain - PDF Ingestion
Usage: python ingest_pdf.py /path/to/file.pdf [--tag financial] [--tag portfolio]
"""

import argparse
import hashlib
import sys
import os
from pathlib import Path
from datetime import datetime

import chromadb
import ollama
import pypdf

from config import (
    CHROMA_HOST, CHROMA_PORT,
    OLLAMA_BASE_URL, EMBED_MODEL,
    COLLECTION_PDFS, CHUNK_SIZE, CHUNK_OVERLAP
)


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + size])
        chunks.append(chunk)
        i += size - overlap
    return [c for c in chunks if c.strip()]


def get_embedding(text: str) -> list[float]:
    """Get embedding from Ollama on Windows."""
    client = ollama.Client(host=OLLAMA_BASE_URL)
    response = client.embeddings(model=EMBED_MODEL, prompt=text)
    return response["embedding"]


def ingest_pdf(pdf_path: str, tags: list[str] = None):
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.exists():
        print(f"❌ File not found: {pdf_path}")
        sys.exit(1)

    print(f"📄 Reading: {pdf_path.name}")

    # Extract text
    reader = pypdf.PdfReader(str(pdf_path))
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() or ""

    if not full_text.strip():
        print("❌ No text extracted — may be a scanned PDF (OCR needed)")
        sys.exit(1)

    print(f"✅ Extracted {len(full_text)} chars from {len(reader.pages)} pages")

    # Chunk
    chunks = chunk_text(full_text)
    print(f"✂️  Split into {len(chunks)} chunks")

    # Connect to ChromaDB
    chroma = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    collection = chroma.get_or_create_collection(COLLECTION_PDFS)

    # Embed + store
    file_hash = hashlib.md5(pdf_path.read_bytes()).hexdigest()
    ingested = 0

    for i, chunk in enumerate(chunks):
        doc_id = f"{file_hash}_{i}"

        # Skip if already ingested
        existing = collection.get(ids=[doc_id])
        if existing["ids"]:
            continue

        print(f"  🔢 Embedding chunk {i+1}/{len(chunks)}...", end="\r")
        embedding = get_embedding(chunk)

        metadata = {
            "source": str(pdf_path),
            "filename": pdf_path.name,
            "chunk": i,
            "total_chunks": len(chunks),
            "ingested_at": datetime.utcnow().isoformat(),
            "tags": ",".join(tags or []),
        }

        collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[chunk],
            metadatas=[metadata],
        )
        ingested += 1

    print(f"\n✅ Done! Ingested {ingested} new chunks from '{pdf_path.name}'")
    print(f"📦 Collection '{COLLECTION_PDFS}' now has {collection.count()} total chunks")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a PDF into Second Brain")
    parser.add_argument("pdf", help="Path to PDF file")
    parser.add_argument("--tag", action="append", dest="tags", default=[], help="Tag (repeatable)")
    args = parser.parse_args()

    ingest_pdf(args.pdf, args.tags)
