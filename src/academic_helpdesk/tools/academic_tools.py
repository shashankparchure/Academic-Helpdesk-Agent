"""CSV lookups and safe email drafting tools for the helpdesk agent."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from academic_helpdesk.rag.retrieval import log_unanswered
from academic_helpdesk.settings import DATA_ROOT, METADATA_ROOT, NORMALIZED_ROOT


OFFERINGS = NORMALIZED_ROOT / "course_offerings.csv"
ALLOCATIONS = NORMALIZED_ROOT / "classroom_allocation.csv"
SLOT_TIMES = NORMALIZED_ROOT / "slot_times.csv"
CONTACTS = NORMALIZED_ROOT / "faculty_contacts.csv"
FACULTY_DIRECTORY = DATA_ROOT / "raw" / "iitj_faculty.csv"
SOURCE_REGISTER = METADATA_ROOT / "source_register.csv"
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _code(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value).upper()


def _person_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _header_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _directory_value(row: dict[str, str], *aliases: str) -> str:
    columns = {_header_key(key): value for key, value in row.items() if key}
    for alias in aliases:
        value = columns.get(_header_key(alias), "")
        if value and value.strip():
            return value.strip()
    return ""


def _faculty_directory_matches(instructor_name: str) -> list[dict[str, str]]:
    if not FACULTY_DIRECTORY.is_file():
        return []
    query = _person_key(instructor_name)
    if not query:
        return []

    matches: list[dict[str, str]] = []
    with FACULTY_DIRECTORY.open(encoding="utf-8-sig", newline="") as stream:
        for row_number, row in enumerate(csv.DictReader(stream), start=2):
            name = _directory_value(row, "Faculty Name", "Name", "Faculty")
            if _person_key(name) != query:
                continue
            primary_text = _directory_value(row, "Email ID", "Primary Email", "Email", "Email Address")
            alternate_text = _directory_value(
                row, "Other Email IDs", "Alternate Email IDs", "Alternate Email ID", "Alternate Email"
            )
            primary = next(iter(EMAIL_RE.findall(primary_text)), "")
            alternates = list(dict.fromkeys(email for email in EMAIL_RE.findall(alternate_text) if email != primary))
            matches.append({
                "name": name,
                "primary_email": primary,
                "alternate_emails": "; ".join(alternates),
                "designation": _directory_value(row, "Designation", "Position", "Title"),
                "department": _directory_value(row, "Department", "School", "Unit"),
                "source_path": "data/raw/iitj_faculty.csv",
                "source_row": str(row_number),
            })
    return matches


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


def count_course_offerings(department_sheet: str, course_level_digit: str) -> str:
    """Count distinct courses at a level in an exact department sheet and expose category/scope evidence.

    The normalized workbook may not identify whether every course is an elective or which term it
    applies to. Return those limitations with the count instead of silently treating all courses as
    electives or as belonging to the current semester.
    """
    department = re.sub(r"\s+", " ", department_sheet).strip().casefold()
    level = str(course_level_digit).strip()
    if not department or not re.fullmatch(r"[1-9]", level):
        return "INVALID_FILTER: Provide an exact department sheet name and one course-level digit."

    rows = _read_csv(OFFERINGS)
    sheets = sorted({row.get("department_sheet", "").strip() for row in rows if row.get("department_sheet", "").strip()})
    selected = [
        row for row in rows
        if row.get("department_sheet", "").strip().casefold() == department
        and row.get("course_level_digit", "").strip() == level
    ]
    if not selected:
        return (
            f"NO_MATCH: No normalized courses found for department sheet {department_sheet!r} at level {level}. "
            f"Available department sheets: {', '.join(sheets)}. Do not map a department name to a sheet without evidence."
        )

    by_code: dict[str, dict[str, str]] = {}
    for row in selected:
        by_code.setdefault(_code(row.get("course_code", "")), row)
    courses = list(by_code.values())
    explicitly_labeled_electives = [
        row for row in courses
        if "elective" in f"{row.get('category', '')} {row.get('remarks', '')}".casefold()
    ]
    all_classified = all(row.get("category", "").strip() or row.get("remarks", "").strip() for row in courses)
    details = []
    for row in courses:
        details.append(
            f"{row.get('course_code')} | {row.get('course_name')} | category: {row.get('category') or 'not recorded'}"
            f" | source: {row.get('source_file')}#{row.get('source_sheet')} rows {row.get('source_rows') or row.get('source_row')}"
            f" | citation ID: {_citation_id(row.get('source_file', ''))}"
        )
    scope_note = (
        "Category/remarks are populated for all returned courses; only explicitly labeled electives are classified as electives."
        if all_classified else
        "The source does not classify every returned course as an elective; do not report the total course count as an elective count."
    )
    return (
        f"Distinct level-{level} courses in department sheet {department_sheet!r}: {len(courses)}. "
        f"Explicitly labeled elective courses: {len(explicitly_labeled_electives)}. "
        f"Term applicability is not encoded in this normalized table. {scope_note}\n" + "\n".join(details)
    )


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
    """Look up an exact instructor contact in the reviewed contact file or raw IITJ directory.

    The raw directory is read-only at runtime. Results cite its filename and row number so a student
    can check the address against the supplied faculty listing.
    """
    query = _person_key(instructor_name)
    rows = _read_csv(CONTACTS)
    matches = [
        row for row in rows
        if query and query == _person_key(row.get("name", ""))
        and row.get("verification_status", "").strip().casefold() == "verified"
    ]
    if matches:
        emails = {row.get("email", "").strip().casefold() for row in matches if row.get("email", "").strip()}
        if len(emails) > 1:
            return f"AMBIGUOUS_CONTACT: Multiple verified email matches for {instructor_name!r}; ask which contact is intended. No email draft should be made."
        row = matches[0]
        return (
            f"CONTACT_FOUND | {row.get('name')} | email for contact: {row.get('email')}"
            f" | source: {row.get('source_path')} row {row.get('source_row', '')}"
            f" | citation ID: {row.get('citation_id', '')}"
        )

    directory_matches = _faculty_directory_matches(instructor_name)
    if not directory_matches:
        return (
            f"NO_VERIFIED_EMAIL: No exact contact match for {instructor_name!r} in the reviewed contacts "
            "or data/raw/iitj_faculty.csv. Do not guess an email address."
        )
    unique = {
        (row["primary_email"].casefold(), row["alternate_emails"].casefold()): row
        for row in directory_matches
        if row["primary_email"] or row["alternate_emails"]
    }
    if not unique:
        return f"NO_DIRECTORY_EMAIL: {instructor_name!r} matched the faculty directory, but that row has no usable email address."
    candidate_emails = {
        row["primary_email"].casefold()
        or row["alternate_emails"].split("; ", 1)[0].casefold()
        for row in unique.values()
    }
    if len(candidate_emails) > 1:
        candidates = "; ".join(
            f"{row['name']} ({row['designation'] or 'designation not listed'}, {row['department'] or 'department not listed'})"
            for row in unique.values()
        )
        return f"AMBIGUOUS_CONTACT: Multiple directory records match {instructor_name!r}: {candidates}. Ask for clarification; do not draft an email."

    row = next(iter(unique.values()))
    primary = row["primary_email"]
    alternate = row["alternate_emails"]
    selected_email = primary or (alternate.split("; ", 1)[0] if alternate else "")
    citation_id = _citation_id(row["source_path"])
    citation_suffix = f" | citation ID: {citation_id}" if citation_id else ""
    return (
        f"CONTACT_FOUND | {row['name']} | email for contact: {selected_email}"
        f" | primary email: {primary or 'not listed'} | alternate email IDs: {alternate or 'not listed'}"
        f" | designation: {row['designation'] or 'not listed'} | department: {row['department'] or 'not listed'}"
        f" | source: {row['source_path']} row {row['source_row']}"
        f"{citation_suffix}"
    )


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
    if contact.startswith("AMBIGUOUS_CONTACT"):
        return f"{contact} No email was drafted."
    email_match = EMAIL_RE.search(contact)
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
    contact_source = next((line.strip() for line in contact.splitlines() if "| source:" in line), "")
    contact_citation = next((line.split("| citation ID:", 1)[-1].strip() for line in contact.splitlines() if "| citation ID:" in line), "")
    contact_note = (
        f"Instructor contact source: {contact_source}"
        + (f"; citation ID: {contact_citation}" if contact_citation else "")
        if email_match else
        "Instructor name came from the course list, but no usable email was found; check an official contact source."
    )
    return body + "\n" + contact_note + " This is a draft only; it has not been sent."
