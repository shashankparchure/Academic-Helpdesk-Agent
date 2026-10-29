"""Build the local Chroma index from extracted documents and normalized tables."""

from __future__ import annotations

import csv
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

import chromadb
import ollama

# Scripts are launched from the project root, while the application package is
# maintained under src/. Make it importable without installing this project.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from academic_helpdesk.settings import (
    CHROMA_COLLECTION,
    EMBEDDING_MODEL,
    OLLAMA_HOST,
    METADATA_ROOT,
    NORMALIZED_ROOT,
    VECTOR_ROOT,
)


EXTRACTED_ROOT = PROJECT_ROOT / "data" / "processed" / "extracted_text"
REGISTER_PATH = METADATA_ROOT / "source_register.csv"
BATCH_SIZE = 16
MAX_CHUNK_CHARS = 1800
CHUNK_OVERLAP = 220
NORMALIZED_TABLES = ("course_offerings.csv", "classroom_allocation.csv", "slot_times.csv")


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def normalized_source_key(source_file: str) -> str:
    key = source_file.replace("\\", "/")
    return key[len("data/raw/"):] if key.startswith("data/raw/") else key


def stable_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def split_text(text: str) -> list[tuple[str, str, str]]:
    """Return (chunk, page, section) tuples while retaining page/sheet headings."""
    sections = re.split(r"(?=^## .+$)", text, flags=re.MULTILINE)
    output: list[tuple[str, str, str]] = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        heading_match = re.match(r"^## (.+)$", section, flags=re.MULTILINE)
        heading = heading_match.group(1).strip() if heading_match else ""
        page_match = re.match(r"Page\s+(\d+)", heading, flags=re.IGNORECASE)
        page = page_match.group(1) if page_match else ""
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", section) if p.strip()]
        current = ""
        for paragraph in paragraphs:
            if len(paragraph) > MAX_CHUNK_CHARS:
                if current:
                    output.append((current, page, heading))
                    current = ""
                start = 0
                while start < len(paragraph):
                    end = min(start + MAX_CHUNK_CHARS, len(paragraph))
                    output.append((paragraph[start:end], page, heading))
                    if end == len(paragraph):
                        break
                    start = max(0, end - CHUNK_OVERLAP)
                continue
            if current and len(current) + len(paragraph) + 2 > MAX_CHUNK_CHARS:
                output.append((current, page, heading))
                tail = current[-CHUNK_OVERLAP:] if CHUNK_OVERLAP else ""
                current = f"{tail}\n\n{paragraph}" if tail else paragraph
            else:
                current = f"{current}\n\n{paragraph}" if current else paragraph
        if current:
            output.append((current, page, heading))
    return output


def source_metadata(row: dict[str, str], page: str = "", sheet: str = "", source_row: str = "") -> dict[str, Any]:
    return {
        "citation_id": row.get("citation_id", ""),
        "source_title": row.get("title", ""),
        "raw_path": row.get("raw_path", ""),
        "page": page,
        "source_sheet": sheet,
        "source_row": source_row,
        "source_category": row.get("source_category", ""),
    }


def collect_documents() -> tuple[list[str], list[str], list[dict[str, Any]]]:
    register = read_csv(REGISTER_PATH)
    if not register:
        raise SystemExit("Source register is missing or empty. Run scripts/normalize_academic_data.py first.")
    source_by_raw = {row.get("raw_path", ""): row for row in register if row.get("raw_path")}
    selected_sources = {
        row.get("citation_id", "") for row in register
        if row.get("include_in_rag", "").casefold() == "yes"
        and row.get("processing_status") in {"processed", "processed_ocr_text"}
    }
    selected_sources.discard("")
    if not selected_sources:
        raise SystemExit(
            f"No eligible sources are selected in {REGISTER_PATH.name}. "
            "Set include_in_rag=yes for processed source documents."
        )
    documents: list[str] = []
    ids: list[str] = []
    metadatas: list[dict[str, Any]] = []

    # Sheets indexed row-by-row from the normalized tables below; skip their
    # sheet text so the same rows are not indexed twice.
    normalized_sheets = {
        (normalized_source_key(row.get("source_file", "")), row.get("source_sheet", "").strip())
        for filename in NORMALIZED_TABLES
        for row in read_csv(NORMALIZED_ROOT / filename)
    }

    for row in register:
        if (
            row.get("include_in_rag", "").casefold() != "yes"
            or row.get("processing_status") not in {"processed", "processed_ocr_text"}
        ):
            continue
        processed_path = row.get("processed_path", "")
        if not processed_path:
            continue
        path = PROJECT_ROOT / Path(processed_path)
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for index, (chunk, page, section) in enumerate(split_text(text)):
            if section.startswith("Sheet:") and (row.get("raw_path", ""), section[len("Sheet:"):].strip()) in normalized_sheets:
                continue
            documents.append(chunk)
            ids.append(stable_id(f"{row.get('citation_id')}|md|{index}|{chunk[:100]}"))
            metadatas.append(source_metadata(row, page=page, sheet=section if section.startswith("Sheet:") else ""))

    # Add one retrievable record per normalized row. Each record points back to the
    # workbook and the sheet/row shown in its metadata.
    for filename in NORMALIZED_TABLES:
        for row in read_csv(NORMALIZED_ROOT / filename):
            source = source_by_raw.get(normalized_source_key(row.get("source_file", "")))
            if (
                not source
                or source.get("include_in_rag", "").casefold() != "yes"
                or source.get("processing_status") not in {"processed", "processed_ocr_text"}
            ):
                continue
            keys = [key for key in row if key not in {"source_file"} and row.get(key)]
            text = " | ".join(f"{key.replace('_', ' ')}: {row[key]}" for key in keys)
            if not text:
                continue
            sheet = row.get("source_sheet", "")
            refs = row.get("source_rows") or row.get("source_row", "")
            documents.append(text)
            ids.append(stable_id(f"{source.get('citation_id')}|{filename}|{sheet}|{refs}|{text}"))
            metadatas.append(source_metadata(source, sheet=sheet, source_row=refs))

    return documents, ids, metadatas


def main() -> None:
    documents, ids, metadatas = collect_documents()
    if not documents:
        raise SystemExit("No eligible source text found. Check include_in_rag in data/metadata/source_register.csv.")

    VECTOR_ROOT.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(VECTOR_ROOT))
    try:
        client.delete_collection(CHROMA_COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine", "embedding_model": EMBEDDING_MODEL},
        embedding_function=None,
    )
    ollama_client = ollama.Client(host=OLLAMA_HOST)
    for start in range(0, len(documents), BATCH_SIZE):
        stop = min(start + BATCH_SIZE, len(documents))
        embedded = ollama_client.embed(model=EMBEDDING_MODEL, input=documents[start:stop]).embeddings
        collection.upsert(
            ids=ids[start:stop],
            documents=documents[start:stop],
            metadatas=metadatas[start:stop],
            embeddings=embedded,
        )
        print(f"Indexed {stop}/{len(documents)} chunks")
    print(f"Collection: {CHROMA_COLLECTION}")
    print(f"Documents/chunks: {collection.count()}")
    print(f"Persistent store: {VECTOR_ROOT}")


if __name__ == "__main__":
    main()
