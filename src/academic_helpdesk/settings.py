"""Shared project paths and local model configuration."""

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data"
NORMALIZED_ROOT = DATA_ROOT / "processed" / "normalized"
METADATA_ROOT = DATA_ROOT / "metadata"
VECTOR_ROOT = DATA_ROOT / "vector_store" / "chroma"
UNKNOWN_LOG = DATA_ROOT / "logs" / "unanswered_questions.csv"

CHAT_MODEL = os.getenv("HELPDESK_CHAT_MODEL", "qwen3:8b")
MULTI_CHAT_MODEL = os.getenv("HELPDESK_MULTI_CHAT_MODEL", CHAT_MODEL)
EMBEDDING_MODEL = os.getenv("HELPDESK_EMBEDDING_MODEL", "qwen3-embedding:0.6b")
OLLAMA_HOST = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
CHROMA_COLLECTION = "iitj_academic_helpdesk"
RETRIEVAL_DISTANCE_LIMIT = float(os.getenv("HELPDESK_RETRIEVAL_DISTANCE_LIMIT", "0.65"))
