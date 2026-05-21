"""Ingesters package."""

from .pdf import PDFIngester
from .url import URLIngester
from .obsidian import ObsidianIngester

__all__ = ["PDFIngester", "URLIngester", "ObsidianIngester"]
