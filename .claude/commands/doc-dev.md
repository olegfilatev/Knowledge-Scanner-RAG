Generate comprehensive developer documentation for this project and write it to `docs/dev/$ARGUMENTS-dev.md`.

**Project name:** $ARGUMENTS (if empty, use "KnowlegeScannerRAG")

## Steps

1. Read and analyze ALL of the following source files in full before writing anything:
   - `CLAUDE.md`
   - `run.py`
   - `backend/config.py`
   - `backend/embedder.py`
   - `backend/vector_store.py`
   - `backend/scraper.py`
   - `backend/rag.py`
   - `backend/main.py`
   - `frontend/index.html`
   - `frontend/app.js`
   - `frontend/style.css`
   - `requirements.txt` (if it exists)
   - `.env.example` (if it exists)

2. Create the directory `docs/dev/` if it does not exist.

3. Write the file `docs/dev/$ARGUMENTS-dev.md` (use "KnowlegeScannerRAG" if no argument was given) with the following structure. Be precise — derive every detail from actual code, not assumptions.

---

## Output file structure

```markdown
# $ARGUMENTS — Developer Documentation

> Cross-reference: [User Guide](../../user/$ARGUMENTS-user.md)

## Table of Contents
(auto-generate with links to each section below)

## 1. Architecture Overview
- Two-sentence summary of what the system does
- ASCII data-flow diagram showing: Browser → Playwright → Confluence → BeautifulSoup → embedder → ChromaDB → rag_search_stream → Claude → SSE → EventSource
- Mermaid sequence diagram covering the Gather flow and the Search flow as two separate sequences

## 2. Tech Stack
Table with columns: Layer | Technology | Version/Notes | Purpose
Cover: Python runtime, FastAPI, Playwright, BeautifulSoup, sentence-transformers model name, ChromaDB, Anthropic SDK, Claude model IDs used, Vanilla JS frontend

## 3. Repository Layout
Annotated directory tree (2 levels deep) with one-line description per file

## 4. Configuration
- All env vars read by `config.py` — name, required/optional, description, example value
- ChromaDB persistence path and how it is set
- Any hardcoded constants that are architecturally significant (HTML truncation limit, collection name constraints, etc.)

## 5. Backend Module Reference
For each module (`config`, `embedder`, `vector_store`, `scraper`, `rag`, `main`):
- **Purpose** — one sentence
- **Public API** — table: function/class | signature | what it does | side effects / exceptions
- **Key implementation notes** — non-obvious decisions (e.g., why run_in_executor, why ProactorEventLoop on Windows, why headed browser)

## 6. API Reference
For every endpoint in `main.py`:
- Method + path
- Description
- Request body schema (Pydantic model fields with types and defaults) OR query parameters
- Response schema (JSON shape with field types)
- Error responses (HTTP status + detail string)
- Example `curl` invocation

## 7. Data Models
- `GatherRequest` Pydantic model — all fields, types, defaults, validation
- In-memory `tasks` dict structure — full shape of a task record at each status transition
- ChromaDB document schema — what metadata fields are stored per paragraph
- SSE event shapes — every `type` value and its `content` structure

## 8. Gather Flow (step-by-step)
Numbered sequence from POST /api/gather through background task completion, noting concurrency model (threading.Event, run_in_executor, ProactorEventLoop thread)

## 9. Search / RAG Flow (step-by-step)
Numbered sequence from GET /api/search/stream through SSE [DONE], noting prompt caching usage (cache_control: ephemeral)

## 10. ChromaDB Collection Name Constraints
- The sanitization rule (regex/logic from `_sanitize_name`)
- Min/max length, allowed characters
- Consequence for the UI (stored name may differ from input)

## 11. Frontend Architecture
- Tab structure and which JS functions handle each tab
- How SSE streaming is consumed (EventSource, event types handled)
- Why GET is used for search (EventSource limitation)
- Any state managed in the frontend

## 12. Known Constraints & Design Decisions
Bullet list of non-obvious architectural choices with a one-sentence rationale each (derive from CLAUDE.md and code comments)

## 13. Development Setup
Step-by-step from clone to running server, including first-time Playwright install. Copy from CLAUDE.md but expand with any detail found in the code.

## 14. Running & Testing
- How to start the server and what URL it serves
- How to exercise the gather endpoint manually (curl example)
- How to exercise the search stream endpoint manually (curl --no-buffer example)
- Any test files present (note if none exist)

## 15. Extending the Application
Short guide on: adding a new API endpoint, swapping the embedding model, changing the ChromaDB backend, adding authentication
```

After writing the file, confirm the path where it was saved and its approximate line count.
