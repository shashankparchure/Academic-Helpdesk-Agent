"""Extract candidate faculty emails for manual verification before use."""

from __future__ import annotations

import csv
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXTRACTED_ROOT = PROJECT_ROOT / "data" / "processed" / "extracted_text"
REGISTER_PATH = PROJECT_ROOT / "data" / "metadata" / "source_register.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "normalized" / "faculty_contacts.csv"

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
ROLE_RE = re.compile(
    r"\b(Professor|Associate Professor|Assistant Professor|Visiting Professor|Dean|"
    r"Associate Dean|Head|Associate Head|Scientist|Lecturer|Registrar|Warden)\b",
    re.IGNORECASE,
)
GENERIC_LINES = {"faculty members", "people", "contact", "home", "profile"}


def normalize_email_text(text: str) -> str:
    text = re.sub(r"\s*\[(?:at)\]\s*|\s*\(at\)\s*", "@", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*\[(?:dot)\]\s*|\s*\(dot\)\s*", ".", text, flags=re.IGNORECASE)
    return text


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def extract_name_before_role(lines: list[str], index: int) -> str:
    candidate_index = index - 1
    while candidate_index >= 0 and not lines[candidate_index].strip():
        candidate_index -= 1
    if candidate_index < 0:
        return ""
    candidate = re.sub(r"\s+", " ", lines[candidate_index]).strip(" :-")
    if not candidate or len(candidate) > 80 or candidate.casefold() in GENERIC_LINES:
        return ""
    if "@" in candidate or "iit jodhpur" in candidate.casefold():
        return ""
    if not re.search(r"[A-Za-z]", candidate):
        return ""
    return candidate


def main() -> None:
    register = read_csv(REGISTER_PATH)
    citation_by_raw = {r.get("raw_path", ""): r.get("citation_id", "") for r in register}
    candidates: dict[tuple[str, str, str], dict[str, str]] = {}
    for path in EXTRACTED_ROOT.rglob("*.md"):
        relative = path.relative_to(EXTRACTED_ROOT).as_posix().casefold()
        if not any(term in relative for term in ("faculty", "people", "homepage", "amit_kumar", "mayank_vatsa", "pratik_mazumder", "richa_singh")):
            continue
        text = normalize_email_text(path.read_text(encoding="utf-8", errors="replace"))
        raw_match = re.search(r"^Raw path:\s*(.+)$", text, flags=re.MULTILINE)
        raw_path = raw_match.group(1).strip() if raw_match else ""
        # Directory CSVs are read row by row by the email tool; text pairing would mismatch them.
        if raw_path.casefold().endswith(".csv"):
            continue
        # Keep each page separate so names and email addresses are paired only locally.
        pages = re.split(r"(?=^## Page\s+\d+\s*$)", text, flags=re.MULTILINE)
        for page in pages:
            lines = [re.sub(r"\s+", " ", line).strip() for line in page.splitlines()]
            emails = list(dict.fromkeys(email.lower() for email in EMAIL_RE.findall(page)))
            names = list(dict.fromkeys(
                name for index, line in enumerate(lines) if ROLE_RE.search(line)
                for name in [extract_name_before_role(lines, index)] if name
            ))
            # Individual faculty pages often have a single contact but no role line
            # adjacent to the name; use the file title only for this unambiguous case.
            if len(emails) == 1 and not names:
                title = path.stem.replace("_", " ").strip()
                title = re.sub(r"\s+", " ", title)
                if title and not title.casefold().startswith("people "):
                    names = [title]
            method = "ordered_name_email_pair_needs_review"
            if len(emails) == 1 and len(names) == 1:
                method = "single_pair_needs_review"
            if len(names) == len(emails) and names:
                pairs = list(zip(names, emails))
            else:
                pairs = [("", email) for email in emails]
            for name, email in pairs:
                key = (name.casefold(), email, raw_path)
                candidates[key] = {
                    "name": name,
                    "email": email,
                    "source_path": raw_path,
                    "citation_id": citation_by_raw.get(raw_path, ""),
                    "match_method": method if name else "email_only_needs_manual_match",
                    "verification_status": "needs_review",
                }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    columns = ["name", "email", "source_path", "citation_id", "match_method", "verification_status"]
    try:
        with OUTPUT_PATH.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(candidates.values())
        output = OUTPUT_PATH
    except PermissionError:
        output = OUTPUT_PATH.with_name("faculty_contacts_updated.csv")
        with output.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(candidates.values())
        print(f"Output locked; wrote {output.name} instead.")
    print(f"Candidate contact rows: {len(candidates)}")
    print(f"All rows need manual verification before the email tool will use them.")
    print(output)


if __name__ == "__main__":
    main()
