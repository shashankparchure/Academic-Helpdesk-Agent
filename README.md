# IIT Jodhpur Academic Helpdesk Agent

A local academic helpdesk prototype for IIT Jodhpur. It uses Google ADK, an Ollama-hosted language model, ChromaDB, and source documents prepared by the user to answer academic questions with citations, look up timetable/course data, find verified instructor contacts, and draft (but never send) emails.

This repository currently contains a **single-agent baseline**. The assignment's specialist-agent version, evaluation prompt set, and findings report are future work.

## Current capabilities

- Extract text from supported PDFs, Word documents, and Excel workbooks. Excel sheets are converted separately so their source sheet can be cited.
- Use same-name `.txt` sidecars for scanned PDFs whose text was extracted with OCR.
- Normalize course offerings, classroom allocations, timetable slots, and a source register into CSV files.
- Build a local ChromaDB index with citation metadata using Ollama embeddings.
- Run an ADK helpdesk agent using the local Qwen model.
- Look up course information, schedules, and verified faculty email addresses; draft email text without sending it.
- Log questions that cannot be answered from the available evidence for human follow-up.

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

Review `data\processed\normalized\faculty_contacts.csv` against official sources. Email candidates are marked `needs_review`; only mark a row `verified` after checking it. The agent only uses verified contacts.

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

## Project layout

```text
Academic-Helpdesk-Agent/
├── assignment_description.txt
├── data/                         # Local input and generated data; ignored by Git
|   +-- raw/                      # User-provided source documents
|   +-- processed/                # Extracted and normalized files
|   +-- metadata/                 # Inventories and source register
|   +-- vector_store/chroma/      # Persistent local Chroma index
|   +-- logs/                     # Unanswered question log
+-- docs/                         # Project documentation
+-- eval/                         # Evaluation prompts and results (planned)
+-- reports/                      # Assignment findings report (planned)
+-- scripts/                      # Data processing and indexing scripts
+-- src/academic_helpdesk/        # ADK agent, retrieval, settings, and tools
```

## Privacy and repository contents

The `.gitignore` excludes local raw/processed documents, generated metadata, vector-store files, logs, virtual environments, and secrets. Add only documents you are permitted to redistribute, and replace personal data with dummy values as the assignment allows. Keep the assignment prompt and project code in version control; add the final evaluation questions and report when they are ready.

## Assignment status

The current code is the single-agent RAG/tool baseline. The assignment also asks for a multi-agent version, a set of 20 to 30 evaluation prompts, and a report covering accuracy, citation groundedness, out-of-scope refusals, and changes across repeated runs. Those deliverables should be added after implementation and evaluation.
