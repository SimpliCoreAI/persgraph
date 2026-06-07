"""
Application settings — loaded from .env via pydantic-settings.
Never hardcode secrets or IPs here.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),  # .env.local overrides .env (gitignored)
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    embed_model: str = "mxbai-embed-large"
    llm_model: str = "qwen2.5:72b"

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8000

    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 64

    # Obsidian vault (for /wiki-ingest note output)
    obsidian_vault_path: str = "~/AgenticHub/InsightsData"

    # Anthropic (for email classification + calendar extraction)
    anthropic_api_key: str = ""

    # Email ingestion (openclaw Gmail inbox)
    openclaw_email: str = ""  # Set via OPENCLAW_EMAIL in .env
    openclaw_email_password: str = ""  # Gmail App Password

    # gog account for Google Calendar
    gog_account: str = ""  # Set via GOG_ACCOUNT in .env

    # Langfuse tracing
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    langfuse_host: str = "https://us.cloud.langfuse.com"

    # Collection names
    collection_pdfs: str = "pdfs"
    collection_notes: str = "notes"
    collection_urls: str = "urls"
    collection_emails: str = "emails"
    collection_youtube: str = "youtube"

    @property
    def all_collections(self) -> list[str]:
        return [
            self.collection_pdfs,
            self.collection_notes,
            self.collection_urls,
            self.collection_emails,
            self.collection_youtube,
        ]


# Singleton — import this everywhere
settings = Settings()
