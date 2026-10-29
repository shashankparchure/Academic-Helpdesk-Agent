# IIT Jodhpur Academic Helpdesk Agent

A local academic helpdesk prototype for IIT Jodhpur. It uses Google ADK, an Ollama-hosted language model, ChromaDB, and source documents prepared by the user to answer academic questions with citations, look up timetable/course data, find verified instructor contacts, and draft (but never send) emails.

This repository contains both a **single-agent baseline** and a separate **multi-agent version** for comparison. The evaluation prompt set and findings report are still future work.

## Current capabilities

- Extract text from supported PDFs, Word documents, and Excel workbooks. Excel sheets are converted separately so their source sheet can be cited.
- Use same-name `.txt` sidecars for scanned PDFs whose text was extracted with OCR.
- Normalize course offerings, classroom allocations, timetable slots, and a source register into CSV files.
- Build a local ChromaDB index with citation metadata using Ollama embeddings.
- Run an ADK helpdesk agent using the local Qwen model.
- Look up course information, schedules, and verified faculty email addresses; draft email text without sending it.
- Log questions that cannot be answered from the available evidence for human follow-up.
- Route requests in the multi-agent version to policy, schedule, and email specialists.

Answers depend on the documents and structured data you provide. Review source dates, applicability, and contact details before relying on them.

## Requirements

- Windows, Python 3.10 or newer, and an activated virtual environment. The project was developed with Python 3.12.
- [Ollama for Windows](https://ollama.com/download) running locally.
- The models used by default:

  ```bat
  ollama pull qwen3:8b
  ollama pull qwen3-embedding:0.6b
  ```

- Python packages (run inside your activated environment):

  ```bat
  python -m pip install google-adk litellm chromadb ollama pypdf pandas python-docx openpyxl
  ```

## Prepare local data

Place source files under `data\raw\` in appropriate subfolders, for example `data\raw\office_orders\` and `data\raw\timetables\`. Keep each OCR text sidecar beside its matching PDF with the same base filename, such as `order.pdf` and `order.txt`.

Run these commands from the repository root, with the environment activated:

```bat
python scripts\process_raw_data.py
python scripts\normalize_academic_data.py
python scripts\build_faculty_contacts.py
```

Review `data\metadata\source_register.csv` and select **20 to 30 source documents** by setting `include_in_rag` to `yes` for the selected documents and `no` for the rest. This document selection is part of the assignment requirements. Keep OCR sidecar text rows set to `no`; the matching PDF row represents that source. The normalizer currently marks eligible sources `yes` by default, so curate the register after each normalization run.

Review `data\processed\normalized\faculty_contacts.csv` against official sources. Email candidates are marked `needs_review`; only rows marked `verified` from that file are used.

The email lookup also reads the supplied faculty directory directly from `data\raw\iitj_faculty.csv`. It matches the instructor name exactly and uses the primary email ID, with an alternate ID as fallback. It cites the raw CSV row. No extraction or vector-index rebuild is needed after replacing this CSV; restart the ADK app to load a changed file.

## Build the vector index

Ensure Ollama is running and the two models above are available. From the repository root:

```bat
set OLLAMA_API_BASE=http://localhost:11434
python scripts\build_vector_index.py
```

The script rebuilds the Chroma collection at `data\vector_store\chroma` each time. Its completion output includes the number of indexed chunks. The current script accepts up to 75 selected sources; use 20 to 30 for the assignment corpus.

## Run the ADK agent

In the same activated Command Prompt, from the repository root:

```bat
cd src
adk web --port 8000
```

Keep the server terminal open and visit <http://localhost:8000>. Select `academic_helpdesk` in the ADK interface. If you open a new terminal, activate the environment and set `OLLAMA_API_BASE` again before launching ADK.

## Compare the single-agent and multi-agent versions

Start each server in a separate activated Command Prompt. Both use the same vector index and Ollama models, but each has its own ADK app/session directory.

Single-agent baseline (port 8000):

```bat
cd src
set OLLAMA_API_BASE=http://localhost:11434
adk web --port 8000 academic_helpdesk
```

Multi-agent version (port 8001, in a second terminal):

```bat
cd src
set OLLAMA_API_BASE=http://localhost:11434
adk web --port 8001 academic_helpdesk_multi
```

Open <http://localhost:8000> for the single-agent baseline and <http://localhost:8001> for the multi-agent version. Keep both server terminals open. ADK's web command accepts an agent directory and a configurable port; these commands point each server at one app so the comparisons remain separate.

## Project layout

```text
Academic-Helpdesk-Agent/
|-- assignment_description.txt
|-- data/                         # Local input and generated data; ignored by Git
|   |-- raw/                      # User-provided source documents
|   |-- processed/                # Extracted and normalized files
|   |-- metadata/                 # Inventories and source register
|   |-- vector_store/chroma/      # Persistent local Chroma index
|   |-- logs/                     # Unanswered question log
|-- docs/                         # Project documentation
|-- eval/                         # Evaluation prompts and results (planned)
|-- reports/                      # Assignment findings report (planned)
|-- scripts/                      # Data processing and indexing scripts
|-- src/academic_helpdesk/        # Single-agent baseline and shared tools
|-- src/academic_helpdesk_multi/  # Orchestrator and specialist agents
```

## Privacy and repository contents

The `.gitignore` excludes local raw/processed documents, generated metadata, vector-store files, logs, virtual environments, and secrets. Add only documents you are permitted to redistribute, and replace personal data with dummy values as the assignment allows. Keep the assignment prompt, project code, and evaluation prompts in version control; add the findings report when it is ready.

## Assignment status

The single-agent baseline, multi-agent implementation, and 28 evaluation prompts are present. The findings report remains to be completed; it should cover accuracy, citation groundedness, out-of-scope refusals, and answer changes across repeated runs. See [`eval/evaluation_prompts.txt`](eval/evaluation_prompts.txt) for the prompt assignments and [`docs/rag_pipeline_analysis.md`](docs/rag_pipeline_analysis.md) for retrieval alternatives and robustness recommendations.
