# RAG pipeline options and robustness plan

This note distinguishes the RAG pipeline implemented in the baseline from possible improvements. The multi-agent version reuses the baseline retrieval function and vector collection so the comparison focuses on agent orchestration rather than changing the knowledge base at the same time.

## Pipeline options

| Pipeline | How it works | Strengths | Tradeoffs | Status |
|---|---|---|---|---|
| Dense vector search | Embed each chunk and query, then retrieve by cosine distance. | Good semantic matching; simple local deployment. | Can miss exact course codes, names, dates, and rare terms; score thresholds need calibration. | Implemented with ChromaDB and Ollama embeddings. |
| Metadata-filtered dense search | Dense search plus filters for document type, topic, term, batch, authority, or effective dates. | Reduces stale or out-of-scope evidence and improves source applicability. | Depends on accurate metadata and a reliable way to resolve a user's batch/term. | Metadata fields exist in the source register but are not fully populated or applied at retrieval time. |
| Hybrid lexical + dense search | Combine BM25/keyword retrieval with vector retrieval, commonly with reciprocal-rank fusion. | Finds exact codes, names, dates, and policy phrases while retaining semantic recall. | More indexing and ranking logic; lexical tokenization needs care for course codes and Hindi text. | Recommended next retrieval upgrade. |
| Hybrid search plus reranking | Retrieve a broader candidate set, then rank candidates with a cross-encoder or local reranker. | Often improves top-k precision and reduces irrelevant context. | Adds latency, memory use, model management, and possibly another local model. | Later upgrade; measure whether hybrid retrieval alone is insufficient first. |
| Query rewriting or multi-query retrieval | Turn a question into focused variants, retrieve for each, then merge results. | Helps vague wording and multi-part questions. | More model calls; can add false-positive evidence unless merged and filtered carefully. | Use selectively for complex questions, not every request. |
| Parent-child or section-aware retrieval | Index small chunks for matching but return their larger section or parent context. | Better context continuity and fewer fragments. | Requires preserving parent/section relationships during extraction and indexing. | Good follow-up if current chunks split rules or tables badly. |
| Structured data tools | Query normalized CSV/table data directly for exact course, schedule, and counts. | Reliable for exact fields and aggregations; citations can point to workbook sheet and row. | Only answers fields that were correctly extracted and normalized. | Implemented for courses/schedules; count tool reports category and term limitations. |

## Current retrieval flow

1. Extracted source documents and normalized table rows are chunked/represented in a persistent Chroma collection.
2. The user's question is embedded with `qwen3-embedding:0.6b` through Ollama.
3. Chroma returns the nearest chunks using cosine distance.
4. Results beyond `HELPDESK_RETRIEVAL_DISTANCE_LIMIT` (default `0.65`) are discarded.
5. Surviving snippets and citation metadata are passed to the agent. If none survive, the question is logged and the agent is instructed not to guess.

The current threshold is a heuristic, not a probability of correctness. Tune it on a labeled set of in-scope answerable, unanswerable, and ambiguous questions. Do not lower the threshold solely to make more queries return evidence.

## Recommended robust pipeline

For the next retrieval iteration, use:

1. **Source control and metadata:** preserve citation ID, source file, page/sheet/row, authority, publication/effective dates, term, batch, and supersession relationships. Mark uncertain values as unknown rather than guessing.
2. **Question scope resolution:** detect whether the request needs policy evidence, an exact course/schedule lookup, an email draft, or multiple domains. Ask for the user's batch/term when it changes the answer and cannot be inferred from source metadata.
3. **Hybrid retrieval:** combine dense and lexical candidates with reciprocal-rank fusion. Keep structured table tools as the source of truth for exact code, slot, and count queries.
4. **Optional reranking:** rerank only the top candidate set if evaluation shows poor precision; prefer a local model compatible with the laptop's memory budget.
5. **Evidence checks:** require at least one cited source for factual claims, preserve conflicts, check source applicability, and abstain when evidence is missing or does not identify the requested category/term.
6. **Answer generation:** pass a small set of deduplicated excerpts with citation metadata. Keep the email tool draft-only.
7. **Evaluation:** maintain a fixed 20–30 prompt set with expected answer facts, required citations, refusal labels, and ambiguity labels. Compare single-agent and multi-agent runs with the same corpus, model, and prompts; record latency, retrieval evidence, and answer changes over repeated runs.

## Current safeguards and known gaps

- Exact course-code tools avoid silently substituting a similar code.
- Faculty email lookup requires a manually verified contact row; email drafts are never sent.
- Unsupported and out-of-scope questions can be logged for human follow-up.
- Course-offering counts return category and term limitations rather than treating every course as an elective or current-semester offering.
- Dense retrieval does not yet use source-register metadata filters, lexical search, a reranker, or query rewriting.
- Current extraction and chunking may lose table layout or section relationships. Review high-impact answers against the original document.
- The single-agent and multi-agent versions currently share the same index and tools. This keeps evaluation controlled; retrieval changes should be evaluated as a separate experiment.
