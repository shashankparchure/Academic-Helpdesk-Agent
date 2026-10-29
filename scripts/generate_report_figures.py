"""Regenerate evaluation charts and their source table for reports/report.tex.

Uses only the Python standard library. Run from the project root with the
project environment active:
    python scripts/generate_report_figures.py
"""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"
FIGURES = ROOT / "reports"
MAIN_BASE = RESULTS / "all_prompts" / "multi_qwen3_8b_28q"
SUBSET_MODELS = {
    "Qwen3 8B": RESULTS / "multi_qwen3_8b",
    "Llama 3.1 8B": RESULTS / "multi_llama3_1_8b",
}
METRICS = ("accuracy", "citation", "refusal", "logging")
PARTICIPANTS = {"1": "Soham", "2": "Shashank", "3": "Saher", "4": "Sarthak"}
LABELS = {
    "accuracy": "Answer accuracy",
    "citation": "Citation correctness",
    "refusal": "Correct refusal",
    "logging": "Follow-up logging",
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def rate(rows: list[dict[str, str]], field: str, question_limit: int | None = None) -> tuple[int, int]:
    """Return (yes, scored denominator); exclude blank yes/no grades."""
    if question_limit is not None:
        rows = [row for row in rows if int(row["question"]) <= question_limit]
    graded = [row for row in rows if row.get(field, "").strip().lower() in {"yes", "no"}]
    yes = sum(row[field].strip().lower() == "yes" for row in graded)
    return yes, len(graded)


def run_metrics(rows: list[dict[str, str]]) -> dict[str, tuple[int, int]]:
    in_scope = [row for row in rows if int(row["question"]) <= 5]
    out_scope = [row for row in rows if int(row["question"]) > 5]
    return {
        "accuracy": rate(in_scope, "answer_correct"),
        "citation": rate(in_scope, "citation_correct"),
        "refusal": rate(out_scope, "refusal_correct"),
        "logging": rate(out_scope, "logged_for_followup"),
    }


def combine_metrics(paths: list[Path]) -> dict[str, tuple[int, int]]:
    rows = [row for path in paths for row in read_rows(path)]
    return run_metrics(rows)


def percent(score: tuple[int, int]) -> float:
    numerator, denominator = score
    return 100.0 * numerator / denominator if denominator else 0.0


def plot(title: str, caption: str, series: list[tuple[str, dict[str, tuple[int, int]]]]) -> str:
    body = [
        r"\begin{figure}[htbp]",
        r"\centering",
        r"\begin{tikzpicture}",
        r"\begin{axis}[",
        r"  ybar, bar width=10pt, width=\textwidth, height=7cm,",
        r"  ymin=0, ymax=105, ylabel={Percent},",
        r"  symbolic x coords={accuracy,citation,refusal,logging}, xtick=data,",
        r"  xticklabels={Answer accuracy,Citation correctness,Correct refusal,Follow-up logging},",
        r"  x tick label style={text width=2.4cm,align=center,font=\small},",
        r"  ymajorgrids=true, grid style={gray!20},",
        r"  nodes near coords, nodes near coords style={font=\scriptsize},",
        r"  enlarge x limits=0.18,",
        r"  legend style={at={(0.5,-0.24)},anchor=north,legend columns=2,font=\small},",
        r"]",
    ]
    for name, values in series:
        coordinates = " ".join(f"({metric},{percent(values[metric]):.1f})" for metric in METRICS)
        body.append(rf"\addplot coordinates {{{coordinates}}};")
        body.append(rf"\addlegendentry{{{name}}}")
    body.extend(
        [
            r"\end{axis}",
            r"\end{tikzpicture}",
            rf"\caption{{{caption}}}",
            r"\end{figure}",
            "",
        ]
    )
    return "\n".join(body)


def participant_accuracy(path: Path) -> dict[str, tuple[int, int]]:
    rows = read_rows(path)
    return {
        name: rate(
            [row for row in rows if row["set"] == set_number and int(row["question"]) <= 5],
            "answer_correct",
        )
        for set_number, name in PARTICIPANTS.items()
    }


def participant_plot(run1: Path, run2: Path) -> str:
    names = list(PARTICIPANTS.values())
    coords = ",".join(name.lower() for name in names)
    ticks = ",".join(names)
    body = [
        r"\begin{figure}[htbp]",
        r"\centering",
        r"\begin{tikzpicture}",
        r"\begin{axis}[",
        r"  ybar, bar width=10pt, width=\textwidth, height=6.5cm,",
        r"  ymin=0, ymax=108, ylabel={Correct answers (percent)},",
        rf"  symbolic x coords={{{coords}}}, xtick=data, xticklabels={{{ticks}}},",
        r"  ymajorgrids=true, grid style={gray!20},",
        r"  nodes near coords, nodes near coords style={font=\scriptsize},",
        r"  enlarge x limits=0.18,",
        r"  legend style={at={(0.5,-0.15)},anchor=north,legend columns=2,font=\small},",
        r"]",
    ]
    for label, path in (("Run 1", run1), ("Run 2", run2)):
        scores = participant_accuracy(path)
        points = " ".join(f"({name.lower()},{percent(scores[name]):.1f})" for name in names)
        body.extend([rf"\addplot coordinates {{{points}}};", rf"\addlegendentry{{{label}}}"])
    body.extend(
        [
            r"\end{axis}",
            r"\end{tikzpicture}",
            r"\caption{Correct-answer rate by participant group on the main Qwen3 prompt set. Each group has five in-scope questions.}",
            r"\label{fig:group-accuracy}",
            r"\end{figure}",
            "",
        ]
    )
    return "\n".join(body)


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    main_runs = {
        f"Qwen3 main run {run}": run_metrics(read_rows(MAIN_BASE / f"run{run}" / "summary.csv"))
        for run in (1, 2)
    }
    subset = {
        model: combine_metrics([folder / f"run{run}" / "summary.csv" for run in (1, 2)])
        for model, folder in SUBSET_MODELS.items()
    }

    lines = [
        r"% Generated by scripts/generate_report_figures.py; requires pgfplots.",
        plot(
            "Qwen3 28-prompt evaluation",
            "Qwen3 on the full 28-prompt set. Accuracy and citation rates use in-scope prompts; refusal and logging use out-of-scope prompts. Values use the grades entered in the summary CSV files.",
            list(main_runs.items()),
        ),
        plot(
            "LLM comparison on the 14-prompt subset",
            "Two runs per model on the matched subset. Percentages use nonblank yes/no grades; blank Llama grades are excluded from answer and citation denominators.",
            list(subset.items()),
        ),
        participant_plot(
            MAIN_BASE / "run1" / "summary.csv",
            MAIN_BASE / "run2" / "summary.csv",
        ),
    ]
    (FIGURES / "performance_figures.tex").write_text("\n".join(lines), encoding="utf-8")

    with (FIGURES / "metric_data.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["evaluation", "metric", "correct", "graded", "percent"])
        for evaluation, metrics in [*main_runs.items(), *subset.items()]:
            for metric in METRICS:
                yes, total = metrics[metric]
                writer.writerow([evaluation, LABELS[metric], yes, total, f"{percent((yes, total)):.1f}"])
        for run in (1, 2):
            scores = participant_accuracy(MAIN_BASE / f"run{run}" / "summary.csv")
            for participant, (yes, total) in scores.items():
                writer.writerow([
                    f"Qwen3 main run {run}",
                    f"Answer accuracy - {participant}",
                    yes,
                    total,
                    f"{percent((yes, total)):.1f}",
                ])

    print(f"Figures: {FIGURES / 'performance_figures.tex'}")
    print(f"Metric data: {FIGURES / 'metric_data.csv'}")


if __name__ == "__main__":
    main()
