"""Ask every evaluation prompt to the single- and multi-agent helpdesks through a running ADK server.

Start the server first, from src/ (it also serves the web UI):
    adk web --port 8000

Then, from the project root:
    python eval/run_eval.py --runs 2

Outputs go to eval/results/run<N>/:
  sessions/<agent>_set<S>_q<Q>.json   one exported ADK session per prompt
  <Single|Multi> agent answers - set <S>.json
                                      the set's sessions combined in the ADK session-export layout
  summary.csv                         one row per prompt and agent, with blank columns for manual grading

Each prompt gets a fresh session by default. In one shared session, ADK keeps routing later
messages to the last specialist that answered, so the multi-agent orchestrator would only see the
first prompt. Use --shared-session to reproduce that one-session-per-set behaviour anyway.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import urllib.error
import urllib.request
from pathlib import Path


EVAL_DIR = Path(__file__).resolve().parent
AGENTS = {
    "single": ("academic_helpdesk", "Single agent"),
    "multi": ("academic_helpdesk_multi", "Multi agent"),
}
LOGGING_MARKERS = ("NO_SUPPORTED_SOURCES", "NO_EXACT_COURSE_MATCH", "SOURCE_SEARCH_UNAVAILABLE")
MANUAL_COLUMNS = ["answer_correct", "citation_correct", "refusal_correct", "unsupported_claims", "notes"]


def call(base_url: str, method: str, path: str, body: dict | None = None, timeout: float = 900) -> object:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        base_url.rstrip("/") + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read() or b"null")


def ask(base_url: str, app: str, user: str, session_id: str, prompt: str) -> str:
    try:
        call(base_url, "POST", "/run", {
            "appName": app,
            "userId": user,
            "sessionId": session_id,
            "newMessage": {"role": "user", "parts": [{"text": prompt}]},
        })
        return ""
    except urllib.error.HTTPError as exc:
        return f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:500]}"
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def new_session(base_url: str, app: str, user: str) -> str:
    return call(base_url, "POST", f"/apps/{app}/users/{user}/sessions", {})["id"]


def get_session(base_url: str, app: str, user: str, session_id: str) -> dict:
    return call(base_url, "GET", f"/apps/{app}/users/{user}/sessions/{session_id}")


def turns(events: list[dict]) -> list[tuple[str, list[dict]]]:
    """Split session events into (user prompt, agent events) pairs."""
    result: list[tuple[str, list[dict]]] = []
    for event in events:
        parts = (event.get("content") or {}).get("parts") or []
        if event.get("author") == "user":
            result.append((" ".join(p.get("text", "") for p in parts if p.get("text")), []))
        elif result:
            result[-1][1].append(event)
    return result


def summarize(agent_events: list[dict]) -> dict[str, str]:
    final_answer = ""
    tools: list[str] = []
    agents: list[str] = []
    logged = False
    for event in agent_events:
        if event.get("author") not in agents:
            agents.append(event.get("author", ""))
        parts = (event.get("content") or {}).get("parts") or []
        texts = [p["text"] for p in parts if p.get("text") and not p.get("thought")]
        if texts:
            final_answer = "\n".join(texts).strip()
        for part in parts:
            if "functionCall" in part:
                name = part["functionCall"].get("name", "")
                tools.append(name)
                logged |= name == "record_unanswered_question"
            if "functionResponse" in part:
                logged |= any(marker in json.dumps(part["functionResponse"]) for marker in LOGGING_MARKERS)
    return {
        "final_answer": final_answer,
        "cited_doc_ids": "; ".join(sorted(set(re.findall(r"DOC\d{4}", final_answer)))),
        "tools_called": "; ".join(tools),
        "agents_involved": "; ".join(agents),
        "logged_for_followup": "yes" if logged else "no",
    }


def combined_export(sessions: list[dict]) -> dict:
    """Merge per-prompt sessions into one object with the ADK session-export keys."""
    first = sessions[0]
    return {
        "id": first.get("id"),
        "appName": first.get("appName"),
        "userId": first.get("userId"),
        "state": first.get("state", {}),
        "events": [event for session in sessions for event in session.get("events", [])],
        "lastUpdateTime": max(session.get("lastUpdateTime", 0) for session in sessions),
        "sessionIds": [session.get("id") for session in sessions],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--user", default="user")
    parser.add_argument("--prompts", type=Path, default=EVAL_DIR / "prompts.json")
    parser.add_argument("--out", type=Path, default=EVAL_DIR / "results")
    parser.add_argument("--agents", nargs="+", choices=sorted(AGENTS), default=["single", "multi"])
    parser.add_argument("--sets", nargs="+", type=int, help="Only run these prompt sets (default: all).")
    parser.add_argument("--questions", nargs="+", type=int, help="Only ask these question numbers within each set.")
    parser.add_argument("--runs", type=int, default=1, help="Repeat the full evaluation to see which answers change.")
    parser.add_argument("--first-run", type=int, default=1, help="Number of the first run folder to write.")
    parser.add_argument("--shared-session", action="store_true", help="Ask a whole set in one session.")
    args = parser.parse_args()

    prompt_sets = json.loads(args.prompts.read_text(encoding="utf-8"))["sets"]
    if args.sets:
        prompt_sets = [s for s in prompt_sets if s["set"] in args.sets]

    for run in range(args.first_run, args.first_run + args.runs):
        run_dir = args.out / f"run{run}"
        (run_dir / "sessions").mkdir(parents=True, exist_ok=True)
        rows = []
        for prompt_set in prompt_sets:
            set_no = prompt_set["set"]
            for agent in args.agents:
                app, label = AGENTS[agent]
                sessions: list[dict] = []
                errors: dict[int, str] = {}
                shared_id = new_session(args.base_url, app, args.user) if args.shared_session else ""
                asked = [(q, p) for q, p in enumerate(prompt_set["prompts"], start=1) if not args.questions or q in args.questions]
                for q_no, prompt in asked:
                    print(f"[run {run}] set {set_no} q{q_no} {agent}: {prompt[:70]}", flush=True)
                    session_id = shared_id or new_session(args.base_url, app, args.user)
                    errors[q_no] = ask(args.base_url, app, args.user, session_id, prompt)
                    if errors[q_no]:
                        print(f"    ERROR {errors[q_no]}", flush=True)
                    if not args.shared_session:
                        session = get_session(args.base_url, app, args.user, session_id)
                        (run_dir / "sessions" / f"{agent}_set{set_no}_q{q_no}.json").write_text(
                            json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")
                        sessions.append(session)
                if args.shared_session:
                    sessions = [get_session(args.base_url, app, args.user, shared_id)]
                export = sessions[0] if args.shared_session else combined_export(sessions)
                (run_dir / f"{label} answers - set {set_no}.json").write_text(
                    json.dumps(export, indent=2, ensure_ascii=False), encoding="utf-8")

                for (q_no, _), (prompt, agent_events) in zip(asked, turns(export["events"])):
                    rows.append({
                        "run": run, "set": set_no, "question": q_no, "agent": agent, "prompt": prompt,
                        **summarize(agent_events), "error": errors.get(q_no, ""),
                        **{column: "" for column in MANUAL_COLUMNS},
                    })

        if not rows:
            print(f"Run {run}: no answers were recorded; check the ADK server and the errors above.")
            continue
        with (run_dir / "summary.csv").open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"Run {run} written to {run_dir}")


if __name__ == "__main__":
    main()
