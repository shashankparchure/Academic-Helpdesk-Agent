"""Local Chroma and Ollama embedding retrieval."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb
import ollama

from academic_helpdesk.settings import (
    CHROMA_COLLECTION,
    EMBEDDING_MODEL,
    OLLAMA_HOST,
    RETRIEVAL_DISTANCE_LIMIT,
    UNKNOWN_LOG,
    VECTOR_ROOT,
)


_client: chromadb.PersistentClient | None = None
_collection: Any = None
_ollama = ollama.Client(host=OLLAMA_HOST)


def get_collection() -> Any:
    global _client, _collection
    if _collection is not None:
        return _collection
    if not VECTOR_ROOT.exists():
        raise RuntimeError("The local vector index is missing. Run scripts/build_vector_index.py first.")
    _client = chromadb.PersistentClient(path=str(VECTOR_ROOT))
    try:
        _collection = _client.get_collection(CHROMA_COLLECTION, embedding_function=None)
    except Exception as exc:
        raise RuntimeError("The local vector index is not built. Run scripts/build_vector_index.py first.") from exc
    return _collection


def embed_query(query: str) -> list[float]:
    result = _ollama.embed(model=EMBEDDING_MODEL, input=query)
    return result.embeddings[0]


def log_unanswered(question: str, reason: str) -> None:
    UNKNOWN_LOG.parent.mkdir(parents=True, exist_ok=True)
    exists = UNKNOWN_LOG.exists()
    try:
        with UNKNOWN_LOG.open("a", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=["timestamp_utc", "question", "reason"])
            if not exists:
                writer.writeheader()
            writer.writerow({
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "question": question,
                "reason": reason,
            })
    except PermissionError:
        # Keep the agent responsive if someone has opened the log in a spreadsheet app.
        fallback = UNKNOWN_LOG.with_name("unanswered_questions_pending.csv")
        fallback_exists = fallback.exists()
        with fallback.open("a", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=["timestamp_utc", "question", "reason"])
            if not fallback_exists:
                writer.writeheader()
            writer.writerow({
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "question": question,
                "reason": reason,
            })


def record_unanswered_question(question: str, reason: str = "The available sources did not support an answer.") -> str:
    """Record an unsupported or out-of-scope question for human follow-up."""
    log_unanswered(question, reason)
    return "The question has been recorded for human follow-up."


def search_sources(query: str, limit: int = 5) -> list[dict[str, Any]]:
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return []
    n_results = max(1, min(int(limit), count))
    result = collection.query(
        query_embeddings=[embed_query(query)],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    matches: list[dict[str, Any]] = []
    for document, metadata, distance in zip(documents, metadatas, distances):
        if float(distance) > RETRIEVAL_DISTANCE_LIMIT:
            continue
        matches.append({"text": document, "metadata": metadata or {}, "distance": float(distance)})
    return matches


def format_matches(matches: list[dict[str, Any]]) -> str:
    return json.dumps([
        {
            "citation_id": match["metadata"].get("citation_id", ""),
            "title": match["metadata"].get("source_title", ""),
            "raw_path": match["metadata"].get("raw_path", ""),
            "page": match["metadata"].get("page", ""),
            "sheet": match["metadata"].get("source_sheet", ""),
            "source_row": match["metadata"].get("source_rows", match["metadata"].get("source_row", "")),
            "excerpt": match["text"],
        }
        for match in matches
    ], ensure_ascii=False, indent=2)


def search_academic_sources(query: str, limit: int = 5) -> str:
    """Search official IIT Jodhpur academic sources and return evidence with citations.

    Use this for policy, curriculum, course content, and academic-office questions.
    If no relevant evidence is returned, say the answer is not available and do not guess.
    """
    try:
        matches = search_sources(query, limit)
    except Exception as exc:
        log_unanswered(query, f"Source search unavailable: {type(exc).__name__}: {exc}")
        return f"SOURCE_SEARCH_UNAVAILABLE: {exc}"
    if not matches:
        log_unanswered(query, "No retrieved source met the relevance threshold.")
        return "NO_SUPPORTED_SOURCES: No relevant source evidence was found. Do not guess; tell the student the helpdesk does not know and that the question was logged for human follow-up."
    return format_matches(matches)
