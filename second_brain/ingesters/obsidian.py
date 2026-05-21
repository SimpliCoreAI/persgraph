"""
Obsidian vault ingester — reads markdown notes and ingests into ChromaDB.
Supports incremental ingestion (only changed files).
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..config import settings
from ..embeddings import embedder
from ..vectorstore import vectorstore
from .base import BaseIngester, IngestResult

COLLECTION = "obsidian"
STATE_FILE = Path(__file__).parent.parent.parent / "data" / "obsidian_state.json"

# Default ignore folders
DEFAULT_IGNORE = {".obsidian", ".trash", "templates", "Templates", ".git"}


class ObsidianIngester(BaseIngester):
    """Ingest Obsidian vault markdown notes into ChromaDB."""

    def __init__(
        self,
        vault_path: Optional[str] = None,
        ignore_folders: Optional[list[str]] = None,
    ) -> None:
        # Read from config.yaml if not provided
        if vault_path is None:
            try:
                from ..app_config import app_config
                vault_path = str(app_config._get("obsidian", "vault_path", default="~/AgenticHub/InsightsData"))
            except Exception:
                vault_path = "~/AgenticHub/InsightsData"

        self.vault = Path(os.path.expanduser(vault_path))
        self.ignore = DEFAULT_IGNORE | set(ignore_folders or [])

    def ingest(self, source: str = "", tags: Optional[list[str]] = None) -> IngestResult:
        """
        Ingest all markdown files in the vault.
        source is ignored — uses vault_path from config.
        Only ingests new or changed files (incremental).
        """
        tags = tags or ["obsidian"]

        if not self.vault.exists():
            return IngestResult(
                source=str(self.vault),
                chunks_total=0,
                chunks_new=0,
                collection=COLLECTION,
                tags=tags,
                errors=[f"Vault not found: {self.vault}"],
            )

        md_files = self._find_notes()
        state = self._load_state()

        total_chunks = 0
        new_chunks = 0
        errors = []

        for md_path in md_files:
            try:
                file_hash = self._hash_file(md_path)
                rel_path = str(md_path.relative_to(self.vault))

                # Skip unchanged files
                if state.get(rel_path) == file_hash:
                    continue

                text = md_path.read_text(encoding="utf-8", errors="replace")
                title = md_path.stem
                notebook = md_path.parent.name if md_path.parent != self.vault else ""

                # Extract frontmatter tags if present
                note_tags = list(tags)
                fm_tags = self._extract_frontmatter_tags(text)
                note_tags += fm_tags
                if notebook:
                    note_tags.append(notebook.lower().replace(" ", "-"))

                # Clean text — remove frontmatter
                clean_text = self._strip_frontmatter(text)
                if not clean_text.strip():
                    continue

                chunks = self._chunk_text(clean_text, settings.chunk_size, settings.chunk_overlap)
                total_chunks += len(chunks)

                file_id = hashlib.md5(rel_path.encode()).hexdigest()
                collection = vectorstore.get_or_create(COLLECTION)
                existing_ids = set(collection.get()["ids"])

                ids, embeddings, documents, metadatas = [], [], [], []
                for i, chunk in enumerate(chunks):
                    doc_id = f"{file_id}_{i}"
                    if doc_id in existing_ids:
                        continue
                    ids.append(doc_id)
                    embeddings.append(embedder.embed(chunk))
                    documents.append(chunk)
                    metadatas.append({
                        "source": str(md_path),
                        "filename": md_path.name,
                        "title": title,
                        "notebook": notebook,
                        "rel_path": rel_path,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "tags": ",".join(note_tags),
                        "ingested_at": datetime.now(timezone.utc).isoformat(),
                    })

                if ids:
                    vectorstore.upsert(
                        collection_name=COLLECTION,
                        ids=ids,
                        embeddings=embeddings,
                        documents=documents,
                        metadatas=metadatas,
                    )
                    new_chunks += len(ids)

                # Update state
                state[rel_path] = file_hash

            except Exception as e:
                errors.append(f"{md_path.name}: {e}")

        self._save_state(state)

        return IngestResult(
            source=str(self.vault),
            chunks_total=total_chunks,
            chunks_new=new_chunks,
            collection=COLLECTION,
            tags=tags,
            errors=errors,
        )

    def ingest_file(self, file_path: str, tags: Optional[list[str]] = None) -> IngestResult:
        """Ingest a single markdown file."""
        path = Path(file_path)
        if not path.exists():
            return IngestResult(
                source=file_path, chunks_total=0, chunks_new=0,
                collection=COLLECTION, errors=[f"File not found: {path}"]
            )
        # Temporarily set vault to parent so relative path works
        old_vault = self.vault
        self.vault = path.parent
        result = self.ingest(tags=tags or ["obsidian"])
        self.vault = old_vault
        return result

    def _find_notes(self) -> list[Path]:
        """Find all markdown files, skipping ignored folders."""
        notes = []
        for root, dirs, files in os.walk(self.vault):
            dirs[:] = [d for d in dirs if d not in self.ignore]
            for f in files:
                if f.endswith(".md") or f.endswith(".txt"):
                    notes.append(Path(root) / f)
        return notes

    def _hash_file(self, path: Path) -> str:
        return hashlib.md5(path.read_bytes()).hexdigest()

    def _extract_frontmatter_tags(self, text: str) -> list[str]:
        """Extract tags from YAML frontmatter."""
        match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if not match:
            return []
        fm = match.group(1)
        tag_match = re.search(r"tags:\s*\[([^\]]+)\]", fm)
        if tag_match:
            return [t.strip().strip('"\'') for t in tag_match.group(1).split(",")]
        tag_match = re.search(r"tags:\s*\n((?:\s+-\s+.+\n?)+)", fm)
        if tag_match:
            return re.findall(r"-\s+(.+)", tag_match.group(1))
        return []

    def _strip_frontmatter(self, text: str) -> str:
        """Remove YAML frontmatter from markdown."""
        return re.sub(r"^---\n.*?\n---\n?", "", text, flags=re.DOTALL)

    def _load_state(self) -> dict:
        import json
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                return json.load(f)
        return {}

    def _save_state(self, state: dict) -> None:
        import json
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
