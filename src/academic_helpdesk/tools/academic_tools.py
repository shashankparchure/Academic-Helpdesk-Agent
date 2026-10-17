"""CSV lookups and safe email drafting tools for the helpdesk agent."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from academic_helpdesk.rag.retrieval import log_unanswered
from academic_helpdesk.settings import METADATA_ROOT, NORMALIZED_ROOT


OFFERINGS = NORMALIZED_ROOT / "course_offerings.csv"
ALLOCATIONS = NORMALIZED_ROOT / "classroom_allocation.csv"
SLOT_TIMES = NORMALIZED_ROOT / "slot_times.csv"
CONTACTS = NORMALIZED_ROOT / "faculty_contacts.csv"
SOURCE_REGISTER = METADATA_ROOT / "source_register.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _code(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value).upper()


def _citation_id(source_file: str) -> str:
    key = source_file.replace("\\", "/")
    if key.startswith("data/raw/"):
        key = key[len("data/raw/"):]
    for row in _read_csv(SOURCE_REGISTER):
        if row.get("raw_path", "") == key:
            return row.get("citation_id", "")
    return ""


def lookup_course(course_code_or_name: str) -> str:
    """Look up an exact course code or matching course title in the normalized offering list."""
    query_code = _code(course_code_or_name)
    query_name = course_code_or_name.strip().casefold()
    rows = _read_csv(OFFERINGS)
    found = [
        row for row in rows
        if (query_code and _code(row.get("course_code", "")) == query_code)
        or (query_name and query_name in row.get("course_name", "").casefold())
    ]
    if not found:
        log_unanswered(course_code_or_name, "No exact course code or title match in normalized course offerings.")
        return f"NO_EXACT_COURSE_MATCH: {course_code_or_name!r} was not found in the current course-offering file. Do not infer a different code."
    unique: dict[tuple[str, ...], dict[str, str]] = {}
    for row in found:
        key = tuple(row.get(k, "") for k in ("course_code", "course_name", "department_sheet", "program_or_batch", "slot", "instructor", "credits"))
        unique[key] = row
    output = []
    for row in unique.values():
        output.append(
            f"{row.get('course_code')} | {row.get('course_name')} | department/tab: {row.get('department_sheet')}"
            f" | program/batch: {row.get('program_or_batch')} | slot: {row.get('slot')} | instructor: {row.get('instructor')}"
            f" | credits: {row.get('credits')} | source: {row.get('source_file')}#{row.get('source_sheet')} rows {row.get('source_rows') or row.get('source_row')}"
            f" | citation ID: {_citation_id(row.get('source_file', ''))}"
        )
    return "\n".join(output)


def lookup_course_schedule(course_code: str) -> str:
    """Look up an exact course code, its classroom allocation, and weekday/time for its slot."""
    query = _code(course_code)
    allocations = [row for row in _read_csv(ALLOCATIONS) if _code(row.get("course_code", "")) == query]
    if not allocations:
        course = lookup_course(course_code)
        if course.startswith("NO_EXACT_COURSE_MATCH"):
            return course
    times = _read_csv(SLOT_TIMES)
    output = []
    for row in allocations:
        slot = row.get("slot", "").strip()
        slot_times = [f"{item.get('day')} {item.get('time')}" for item in times if item.get("slot", "").upper() == slot.upper()]
        output.append(
            f"{row.get('course_code')} | {row.get('course_name')} | slot {slot}"
            f" | day/time: {', '.join(slot_times) if slot_times else 'not found in slot map'}"
            f" | instructor: {row.get('instructor')} | room: {row.get('classroom')}"
            f" | source: {row.get('source_file')}#{row.get('source_sheet')} row {row.get('source_rows') or row.get('source_row')}"
            f" | citation ID: {_citation_id(row.get('source_file', ''))}"
        )
    if not output:
        return f"Course {course_code} is listed, but no classroom allocation was found. Cite the course-offering row and state the limit."
    return "\n".join(output)


def lookup_faculty_email(instructor_name: str) -> str:
    """Look up an instructor's email in the reviewed faculty contacts CSV; never invent an address."""
    query = re.sub(r"\s+", " ", instructor_name).strip().casefold()
    rows = _read_csv(CONTACTS)
    matches = [
        row for row in rows
        if query
        and query == row.get("name", "").strip().casefold()
        and row.get("verification_status", "").strip().casefold() == "verified"
    ]
    if not matches:
        return f"NO_VERIFIED_EMAIL: No exact contact match for {instructor_name!r}. Do not guess an email address."
    return "\n".join(f"{r.get('name')} | {r.get('email')} | source: {r.get('source_path')}" for r in matches)


def draft_instructor_email(course_code: str, reason: str, duration: str = "", student_name: str = "") -> str:
    """Draft an email for the student to review. This tool never sends messages."""
    code = _code(course_code)
    rows = [row for row in _read_csv(OFFERINGS) if _code(row.get("course_code", "")) == code]
    if not rows:
        log_unanswered(course_code, "Email draft requested for an unknown course code.")
        return f"NO_EXACT_COURSE_MATCH: Cannot identify the instructor for {course_code!r}; ask the student to confirm the code. No email was drafted."
    row = rows[0]
    instructor = row.get("instructor", "").strip()
    contact = lookup_faculty_email(instructor) if instructor else "NO_VERIFIED_EMAIL"
    email_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", contact)
    recipient = email_match.group(0) if email_match else "[verified instructor email not found]"
    course_name = row.get("course_name", "")
    greeting = instructor if instructor else "Course Instructor"
    duration_text = f" for {duration}" if duration else ""
    student = student_name or "[Your name]"
    body = (
        f"To: {recipient}\n"
        f"Subject: Request regarding {course_code} - {course_name}\n\n"
        f"Dear {greeting},\n\n"
        f"I am writing to request {reason}{duration_text} for {course_code} ({course_name}). "
        "Please let me know if any additional information or documentation is required.\n\n"
        f"Thank you for your consideration.\n\n{student}\n"
    )
    contact_note = "Instructor email verified from the faculty contact file." if email_match else "Instructor name came from the course list, but no verified email was found; fill in the recipient after checking an official contact source."
    return body + "\n" + contact_note + " This is a draft only; it has not been sent."
