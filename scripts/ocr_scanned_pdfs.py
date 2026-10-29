"""Create OCR text sidecars for raw PDFs that have scanned (image-only) pages.

Run from the project directory before process_raw_data.py:
    python scripts/ocr_scanned_pdfs.py [--force] [--lang eng] [--dpi 400] [--psm 6]

Requires the poppler-utils (pdftoppm) and tesseract-ocr command-line tools, plus
the tesseract language packs named by --lang. For every PDF with at least one
page without extractable text, this writes ``<same name>.txt`` beside the PDF.
Pages that already have text keep the pypdf extraction; only empty pages are
OCRed. Each page is written under a ``## Page N`` heading so page citations
survive chunking. Existing sidecars are left alone unless --force is given.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = PROJECT_ROOT / "data" / "raw"


def ocr_page(pdf: Path, page_number: int, args: argparse.Namespace, workdir: Path) -> str:
    prefix = workdir / f"page{page_number}"
    subprocess.run(
        ["pdftoppm", "-r", str(args.dpi), "-png", "-singlefile", "-f", str(page_number), "-l", str(page_number), str(pdf), str(prefix)],
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["tesseract", str(prefix.with_suffix(".png")), "stdout", "-l", args.lang, "--psm", str(args.psm)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="Rebuild sidecars that already exist.")
    # Adding "hin" garbles digits in the English tables (31 -> 3l); the Hindi letterhead is not needed.
    parser.add_argument("--lang", default="eng", help="Tesseract language(s).")
    parser.add_argument("--dpi", type=int, default=400, help="Render resolution for OCR.")
    parser.add_argument("--psm", type=int, default=6, help="Tesseract page segmentation mode; 6 keeps table rows on one line.")
    args = parser.parse_args()

    missing = [tool for tool in ("pdftoppm", "tesseract") if not shutil.which(tool)]
    if missing:
        raise SystemExit(f"Missing OCR tools: {', '.join(missing)}. Install poppler-utils and tesseract-ocr.")

    written = skipped = 0
    for pdf in sorted(RAW_ROOT.rglob("*.pdf")):
        sidecar = pdf.with_suffix(".txt")
        if sidecar.exists() and not args.force:
            continue
        try:
            pages = [(page.extract_text() or "").strip() for page in PdfReader(str(pdf)).pages]
        except Exception as exc:
            print(f"Skipped unreadable PDF {pdf.relative_to(RAW_ROOT)}: {type(exc).__name__}: {exc}")
            skipped += 1
            continue
        empty = [number for number, text in enumerate(pages, start=1) if not text]
        if not empty:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            for number in empty:
                pages[number - 1] = ocr_page(pdf, number, args, Path(tmp))
        sidecar.write_text(
            "\n\n".join(f"## Page {number}\n\n{text}" for number, text in enumerate(pages, start=1)) + "\n",
            encoding="utf-8",
        )
        written += 1
        print(f"OCR {len(empty)}/{len(pages)} page(s): {pdf.relative_to(RAW_ROOT)}")
    print(f"Sidecars written: {written}; unreadable PDFs skipped: {skipped}")


if __name__ == "__main__":
    main()
