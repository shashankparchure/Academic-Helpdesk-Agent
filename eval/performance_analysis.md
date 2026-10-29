# Interim agent evaluation analysis

**Review date:** 2026-10-29  
**Purpose:** Preserve current results and findings for the final assignment report.  
**Status:** Interim review; not a blinded or independently double-scored evaluation.

## Files and comparability

- `Single_Agent_Answers_Saher.json` and `Multi_Agents_Answers_Saher.json` contain human review fields, answer references, and notes. Their seven questions are an **older prompt set** and do not match the current `prompts.json`.
- `Soham_Single_Agent_Runs.json` / `Soham_Multi_Agent_Runs.json` and `Sarthak_Single_Agent_Runs.json` / `Sarthak_Multi_Agent_Runs.json` are raw ADK session exports from the earlier prompt version, with follow-up turns in some sessions.
- The Shashank single/multi session exports contain revised, non-identical questions and repeated follow-ups. They are useful qualitative evidence but are excluded from matched-prompt accuracy rates.
- At the time of the scored pilot, `eval/prompts.json` contained **14 prompts** in two sets. It has since been updated to the complete 28-prompt set in `eval/evaluation_prompts.txt`. The evaluation script reads JSON.

Because several prompt wordings changed and only the Saher files include human grading labels, there is no defensible single accuracy percentage across every JSON file. Results below separate human-reviewed scores from the exploratory review of matched raw sessions.

## Scoring approach

- An in-scope answer counts as correct only if it answers the asked question with relevant evidence and citations. A cautious refusal to an answerable academic question is recorded as a **false abstention**, not a hallucination, but it is not a correct answer.
- An out-of-scope refusal counts as correct when the agent does not provide the requested out-of-scope advice. Logging is tracked separately because it is also an assignment requirement.
- “Fully correct” means the response covers the requested fields. A timetable answer that gives the slot but omits requested days/times is incomplete.

## Results

### Human-reviewed Saher prompt set (older wording)

| System | In-scope questions fully or mostly correct | Correct out-of-scope refusals | Out-of-scope questions logged | Unsupported claims |
|---|---:|---:|---:|---:|
| Single agent | 2/5 | 2/2 | 0/2 | 4/7 |
| Multi agent | 1/5 on the first response | 2/2 | 2/2 | 2/7 |

The correct multi-agent in-scope response was the LAL4070 schedule. The email response was incomplete on the first turn: it asked for the student's name although the draft tool supports a placeholder, then produced a draft after a follow-up. That draft still omitted the course-source citation. The two other errors included false retrieval abstentions: the SoLA level-4 course exists in the workbook, and the specialization/minors circular text was present in the index. The pre-registration response also introduced an incorrect contact attribution and omitted several source details. The human review notes and references are in the Saher JSON files.

### Earlier 14-prompt pilot sets (exploratory review of Soham and Sarthak sessions)

| Set | Multi-agent fully correct | Main findings |
|---|---:|---|
| Set 1: Soham | 2/5 | Correctly returned the Autonomous Systems slot and drafted the CSL7650 leave email using the faculty directory. It falsely abstained on attendance, Open Elective credits, and course overload information that was available in the corpus. |
| Set 2: Sarthak | 0/5 | It returned only the EEL7080 slot while the question requested weekday and time; failed to retrieve BS Chemistry and credit-revision content; speculated that the branch-change circular's year was a typo; and failed to use the faculty directory for EEL4350. |
| **Combined** | **2/10** | Exploratory manual review, not a second independent grading pass. |

The 2/10 result is a complete-answer score for these two matched sets, not a benchmark estimate. It points to a retrieval and routing problem more strongly than a lack of relevant source documents.

### Out-of-scope refusals

Across the four available multi-agent response groups (Soham, Sarthak, Shashank, and the manually reviewed Saher set), the multi-agent system correctly refused **7/8** out-of-scope requests on text review. The failure was the gaming-laptop question: the response said it was out of scope but then provided hardware specifications and product recommendations.

Only **4/8** out-of-scope requests were logged for human follow-up: both in Soham's run and both in the Saher review. Shashank's and Sarthak's responses either did not call the logging tool or claimed the orchestrator would log the request without actually doing so. Therefore, refusal behavior is better than logging behavior; both need separate rubric columns.

## Error patterns and evidence

1. **Retrieval often returned only a document header.** Session traces show the model explicitly calling `search_academic_sources` with `limit: 1` for queries about attendance, Open Elective credits, course overload, the BS Chemistry curriculum, and the 28-credit revision. The agent then treated the metadata-only result as evidence that the document lacked content. This created false abstentions and, in one response, speculation about “priority rules.”
2. **The orchestrator sometimes chose the wrong specialist.** The EEL7080 timetable request went to the policy specialist and called `lookup_course`, which can return the slot but not the full day/time/room schedule. The EEL4350 email-directory request also went to policy and did not call the email or contact tools.
3. **The count tool contract did not match the model's arguments.** A session called `count_course_offerings` with `department_sheet="School of Liberal Arts"` and `course_level_digit="400"`; the function rejected the request because it expected the literal sheet name and a single digit. The current implementation now canonicalizes “School of Liberal Arts” to `SoLA` and accepts a level such as `400` as level digit `4`. Re-run this prompt after the code change.
4. **Some academic answers used unrelated evidence.** The Engineering Science response mixed minor-credit rules, dual-degree criteria, course offerings, and an unrelated circular citation into a speculative programme guide. This is an unsupported answer, not a safe abstention.
5. **Some citations are incomplete or stale.** The LAL4070 schedule responses cite the classroom-allocation row for the room but do not cite the slot-system rows used for weekday/time. Also, current `source_register.csv` maps the finalized course list to DOC0064 and the 28-credit revision to DOC0022, while older session outputs cite DOC0065 and DOC0023 for those sources. Rebuild the vector index after finalizing the source register and verify that each returned citation ID still maps to the cited title.
6. **Email drafting can be unnecessarily delayed.** The email tool accepts a placeholder student name, but the agent asked for a name before producing a draft. The evaluation prompt should distinguish information needed to address the email from optional personalization, and the agent should use placeholders when the tool supports them.

## What the results suggest doing next

### Before comparing a different LLM

1. Freeze the prompt JSON, source register, and vector index. The instructor has clarified there is no 20–30 document cap; use all relevant processed sources. Regenerate the source register and rebuild the index so eligible processed and OCR-processed PDF records are indexed, while sidecars, duplicates, excluded files, and unprocessed records are skipped.
2. Re-run the current Qwen3 multi-agent system after the count-tool fix to create a fresh baseline. Keep the single-agent app/model unchanged.
3. Compare Qwen3 and the alternate model using only the multi-agent app, the same prompt JSON, the same index, and the same run count. Grade answer accuracy, citation correctness, correct refusal, follow-up logging, unsupported claims, and response time separately.
4. Use `eval/run_eval.py` with `--agents multi` and separate `--out` directories for each model. The results below are the old 14-prompt pilot. `eval/prompts.json` now has all 28 prompts from `evaluation_prompts.txt`; use new output directories for the expanded evaluation to preserve pilot results.

### RAG and orchestration improvements to evaluate afterward

- Make the retrieval candidate count a fixed application setting (for example, retrieve five to eight chunks) instead of letting the model lower `limit` to one. Consider returning chunks from multiple relevant documents and sections.
- Add lexical/BM25 retrieval and reciprocal-rank fusion alongside dense search. This should help exact course codes, policy names, dates, and terminology. Keep structured timetable/course tools as the source of truth for exact values.
- Populate and apply metadata for term, batch, document type, authority, and effective dates; ask for the user's batch or term when it changes the answer.
- Add a small local reranker only if fixed top-k/hybrid retrieval still returns irrelevant chunks. Measure latency and answer quality on the same prompt set before adopting it.
- Tighten orchestrator routing: course/schedule/count questions should reach `schedule_agent`, instructor/email requests should reach `email_agent`, and clearly out-of-scope questions should be logged by the root agent without passing to a specialist.
- Check citations against the source register before finalizing answers, and include both the course-allocation row and the slot-time source for schedule responses.

## Current next-stage conclusion

The multi-agent system demonstrates useful specialist calls and good refusal behavior in most observed out-of-scope cases, but its current in-scope accuracy is not yet reliable. The main blockers are short/metadata-only retrieval, inconsistent specialist routing, source-ID drift, and occasional unsupported expansion. Compare LLMs only after recording a fresh Qwen3 baseline with the corrected count tool and a rebuilt, citation-consistent index; keep RAG unchanged during that comparison so the model is the only experimental variable.

## Fresh Qwen3 vs Llama 3.1 pilot (2026-10-29)

The pilot outputs include two runs each for `qwen3:8b` and `llama3.1:8b`, under `eval/results/multi_qwen3_8b/` and `eval/results/multi_llama3_1_8b/`. Each run used the then-current 14-prompt file (10 in-scope and 4 out-of-scope). All four runs completed 14/14 prompts with no recorded runtime errors. Each run logged all four out-of-scope questions for follow-up. The initial review preceded manual grading; the scored results are summarized below.

### Qualitative comparison

- **Qwen3** was steadier at refusing out-of-scope questions and gave complete EEL7080 schedule details in run 2. It varied substantially between runs on in-scope prompts: run 1 often abstained when retrieval returned inadequate excerpts, while run 2 answered the Open Elective and 28-credit-revision questions and drafted the CSL7650 email. It still abstained on answerable attendance, overload, and branch-change questions in at least one run. Some answers had no citation IDs even when they used a structured tool.
- **Llama 3.1** produced some useful direct answers (including the branch-change answer in run 2 and an overload answer in run 1), but also showed more obvious response-quality failures in the reviewed excerpts: it confused Major and Minor attendance rules, returned citation/JSON-like material instead of an answer on curriculum questions, and exposed a tool-call representation rather than completing the EEL4350 email lookup in run 2. Its phrasing and quality changed noticeably between runs.
- Both models refused and logged all four out-of-scope prompts in both observed runs. That is a promising result for this small set, but still needs the rubric check: a refusal must not include the disallowed recommendation, and the follow-up tool must actually be recorded.
- The CSV citation-ID count differs between runs, but that is not a citation-accuracy score. Some answers state a source in prose without a citation ID, and some IDs may not support the claim. Each citation must be checked against the source register and relevant excerpt.

These observations were preliminary text review. The updated CSV grades now provide pilot metrics, with some rubric fields still incomplete as described below.

### Next steps before reporting a model comparison

1. Grade each of the 56 responses (14 prompts × 2 runs × 2 models) in the existing CSV files. Fill `answer_correct`, `citation_correct`, `refusal_correct`, `unsupported_claims`, and `notes` using the same rubric for both models. For out-of-scope items, assess refusal and actual logging separately. For in-scope items, mark an unsupported refusal as incorrect/abstention rather than hallucination.
2. Compare per-question results across both runs, not only overall averages. Report answer correctness, citation correctness, correct refusals, follow-up logging, unsupported claims, and runtime failures separately. Keep response latency as another measure if the evaluation output records it.
3. The scored pilot covers 14 prompts. The full 28-prompt set from `evaluation_prompts.txt` is now in `prompts.json`, grouped into four participant sets. Run both models against this same expanded prompt file, code, source register, and index for the next comparison.
4. Record the exact code/index revision and model tag for each run. The folder names identify the intended models, but the evaluation CSV does not record a model/version field itself.
5. Fix the observed retrieval, routing, and answer-format issues after the model-only comparison. Do not change RAG settings between the two model runs; otherwise the LLM comparison is confounded.

## Human-scored pilot results (summary sheets updated)

The four `summary.csv` files now contain answer, citation, refusal, and logging grades. The totals below use the evaluator's entered `yes`/`no` values; blank values are not counted as correct.

| Model | Answer correct | Citation correct | Correct out-of-scope refusals | Out-of-scope questions logged |
|---|---:|---:|---:|---:|
| Qwen3 8B | 12/20 (60%) | 16/20 (80%) | 8/8 (100%) | 8/8 (100%) |
| Llama 3.1 8B | 8/19 scored (42%); 1 answer ungraded | 15/18 scored (83%); 2 citation grades blank | 8/8 (100%) | 8/8 (100%) |

Each model had 10 in-scope and 4 out-of-scope prompts per run, over two runs. The Llama percentages use only nonblank grades; counting its ungraded answer as incorrect would give 8/20 (40%). The Qwen pilot leads on the entered answer-correctness grades by about 18 percentage points (or 20 points if the Llama blank is treated as incorrect). Citation correctness is close and slightly favors Llama among its scored rows, but it has two ungraded citation cells. These are small-sample pilot results, not a statistically reliable model ranking.

### What the scores and notes show

- Qwen's correct answers rose from 5/10 in run 1 to 7/10 in run 2. It was correct on both runs for the Autonomous Systems slot and EEL7080 timetable; it missed the overload question in both runs. Several other answers changed from incorrect to correct or the reverse, so one run would give a misleading impression.
- Llama scored 3/10 in run 1 and 5/10 among the 9 graded answers in run 2. It was correct on both runs for EEL7080, but failed both runs on Open Elective credits and the EEL4350 email IDs. Its responses also showed answer-format/tool completion problems in the earlier raw review.
- Both models received `yes` for refusal correctness and follow-up logging on all eight out-of-scope responses. This is a strong result on this prompt set, though it does not prove broader refusal reliability.
- The evaluator confirms there are no unsupported claims in any of the 56 responses in this pilot (0/56). The `unsupported_claims` cells in the CSVs were still blank when last inspected; record `no` in those cells to keep the row-level scoring complete. Llama run 2, Set 2 Question 1 also has blank answer and citation grades; its answer is present, so score it or explain why it was omitted. Llama run 2 Set 1 Question 4 has a blank citation grade.
- Citation correctness is independent of answer correctness: a response can cite a relevant document but fail to answer, or answer correctly without a traceable supporting citation. Keep both measures in the report.

### Recommended next step

Finish rubric cleanup before changing the system: record `unsupported_claims=no` for all 56 responses, fill the three blank Llama grades, and add short notes for any edge cases. Then treat Qwen3 as the current multi-agent candidate based on answer correctness, while reporting both models' 8/8 refusal and logging results. Do not claim a final winner from this 14-prompt pilot.

For the next technical iteration, focus on the errors identified in the notes: retrieve the exact Major-exam attendance circular instead of Minor-exam guidance; retrieve the B.Tech. curriculum's Open Elective credit table and all-year BS Chemistry requirements; route overload questions to authoritative UG academic regulations; and ensure the email workflow returns the finished email and both requested IDs. Use all relevant, processed documents available; the instructor removed the former 20–30 document constraint. Keep the prompt set, corpus, index, and code fixed while evaluating any one change. After fixes, rerun both models on the same frozen 28-prompt set if you still want a model comparison; otherwise use Qwen3 as the fixed model for the RAG/router iteration.

## Update: document selection and full evaluation prompt set

The instructor has clarified that there is no 20–30 document limit for the RAG corpus. Use all relevant documents that have been successfully processed. The earlier recommendation to curate the corpus down to 20–30 documents is superseded. Regenerate `source_register.csv` and rebuild the vector index so the index includes processed and OCR-processed PDF records, while skipping their `.txt` sidecars, duplicates, excluded files, and unprocessed files. `scripts/build_vector_index.py` and the README have been updated to allow any number of eligible sources and enforce those processing-status rules.

`eval/prompts.json` now contains all 28 prompts from `eval/evaluation_prompts.txt`, arranged as four seven-question sets in the same participant order: Soham, Shashank, Saher, and Sarthak. The previous scored runs still cover only the old 14-prompt file. Keep those results as the pilot; use fresh output directories for runs on the expanded 28-prompt set. Run both systems with the same 28 prompts, corpus, index, and settings for the next comparison.

For scoring, mark `unsupported_claims=yes` when an answer includes a material factual assertion that is not supported by the retrieved/cited source or a structured tool, including invented policy details or a wrong claim about what a source says. Mark `no` when factual claims are grounded, and when a refusal contains no extra unsupported assertions. A correct but uncited statement may still be unsupported for the purpose of source-grounded evaluation; score citation correctness separately.

Evaluator correction: after reviewing the model responses, the user reports that none of these 56 responses made unsupported claims. The pilot result is therefore 0/56 responses with unsupported claims; the row-level CSV field should be `no` throughout.
