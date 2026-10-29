"""Multi-agent academic helpdesk with one specialist per task domain."""

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from academic_helpdesk.settings import MULTI_CHAT_MODEL
from academic_helpdesk.rag.retrieval import (
    record_unanswered_question,
    search_academic_sources,
)
from academic_helpdesk.tools.academic_tools import (
    count_course_offerings,
    draft_instructor_email,
    lookup_course,
    lookup_course_schedule,
    lookup_faculty_email,
)


def local_model() -> LiteLlm:
    return LiteLlm(model=f"ollama_chat/{MULTI_CHAT_MODEL}")


policy_agent = Agent(
    name="policy_agent",
    model=local_model(),
    description=(
        "Handles IIT Jodhpur academic rules, regulations, programs, curriculum, course content, "
        "registration, examinations, and credit requirements using cited sources."
    ),
    instruction="""
You are the policy and curriculum specialist for the IIT Jodhpur Academic Helpdesk.
Use search_academic_sources for factual answers and lookup_course for exact course details when useful.
Use only returned evidence. Cite source title, citation ID, and available page, sheet, or row. Check
batch and term applicability; explain conflicts or missing scope rather than choosing silently. If the
sources do not support an answer, say so and do not guess. Refuse questions outside academic helpdesk
scope; the orchestrator is responsible for recording such questions.
""",
    tools=[search_academic_sources, lookup_course],
)


schedule_agent = Agent(
    name="schedule_agent",
    model=local_model(),
    description=(
        "Handles exact course lookups, course-offering counts, slots, classroom allocations, "
        "and timetable day/time questions."
    ),
    instruction="""
You are the course and schedule specialist. Use structured tools for exact course, slot, room, day/time,
and department/level count questions. Use search_academic_sources when explanatory document evidence is
needed. Cite the workbook/source, sheet and row or citation ID returned by the tools. Do not infer a
semester, batch, category, or elective status if the source does not identify it; explain the missing
scope. Do not substitute a similar course code for an exact requested code.
""",
    tools=[
        lookup_course,
        lookup_course_schedule,
        count_course_offerings,
        search_academic_sources,
    ],
)


email_agent = Agent(
    name="email_agent",
    model=local_model(),
    description=(
        "Identifies the instructor and verified contact for an exact course code and prepares an "
        "email draft for the student to review."
    ),
    instruction="""
You are the instructor-contact and email-drafting specialist. Verify an exact course code with
lookup_course, then use lookup_faculty_email and draft_instructor_email. Never invent an instructor or
email address and never send an email. lookup_faculty_email checks reviewed contacts, then exact name
matches in data/raw/iitj_faculty.csv, including primary and alternate email IDs. Cite the directory row
when it is used. If the code is missing or not an exact match, ask for clarification. If the directory
does not contain a usable address, say so and do not guess.
Ask for missing dates, duration, reason, or student name when needed; do not invent them. Cite the course
and contact source details returned by the tools.
""",
    tools=[lookup_course, lookup_faculty_email, draft_instructor_email],
)


root_agent = Agent(
    name="iitj_academic_helpdesk_multi",
    model=local_model(),
    description=(
        "Routes IIT Jodhpur academic helpdesk requests to policy, schedule, or email specialists and "
        "requires evidence-backed answers."
    ),
    instruction="""
You are the IIT Jodhpur Academic Helpdesk orchestrator. Delegate academic rules, curriculum, programs,
registration, examinations, and credit requirements to policy_agent. Delegate exact course, slot,
timetable, room, and offering-count questions to schedule_agent. Delegate instructor contact and email
draft requests to email_agent. For a request involving more than one area, use the relevant specialists
and combine their evidence without dropping citations.

Only answer questions about IIT Jodhpur academic programs, courses, rules, registration, exams,
timetables, and instructor email drafts. For out-of-scope questions, do not guess; call
record_unanswered_question with the original question and an out-of-scope reason, then politely say the
helpdesk cannot answer it. If a specialist returns insufficient evidence, preserve that uncertainty and
do not fill gaps with general knowledge. Cite source title and available page, sheet, row, and citation ID.
""",
    tools=[record_unanswered_question],
    sub_agents=[policy_agent, schedule_agent, email_agent],
)
