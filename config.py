# Second Brain - Config
# All compute runs on Windows via Tailscale

WINDOWS_IP = "100.122.130.89"

# Ollama
OLLAMA_BASE_URL = f"http://{WINDOWS_IP}:11434"
EMBED_MODEL = "mxbai-embed-large"
LLM_MODEL = "qwen2.5:72b"

# ChromaDB
CHROMA_HOST = WINDOWS_IP
CHROMA_PORT = 8000

# Collections
COLLECTION_PDFS = "pdfs"
COLLECTION_NOTES = "notes"
COLLECTION_URLS = "urls"
COLLECTION_EMAILS = "emails"
COLLECTION_YOUTUBE = "youtube"

# Chunking
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64
