# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup and Running

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browser (first time only)
playwright install chromium

# Configure environment
cp .env.example .env
# Set ANTHROPIC_API_KEY in .env

# Start the server (serves both API and frontend)
python run.py
# → http://localhost:8000
```

The app must be run from the repo root so that `frontend/` is found by FastAPI's `StaticFiles` mount and the `backend/` package import path resolves correctly.

## Architecture

Two-phase RAG application: **Gather** (scrape Confluence → embed → store) then **Search** (embed query → retrieve chunks → stream Claude answer).

```
browser (Playwright, headed) ──► Confluence search page
                                        │
                              extract_links_with_claude()   ← Claude Sonnet (link extraction)
                                        │
                              scrape each page (BeautifulSoup)
                                        │
                              split_into_paragraphs() + embed_batch()   ← sentence-transformers
                                        │
                              ChromaDB (persistent, cosine similarity)
                                        │
                              rag_search_stream()   ← Claude Sonnet (streaming answer)
                                        │
                              SSE → EventSource in browser
```

### Backend modules (`backend/`)

| Module | Responsibility |
|---|---|
| `config.py` | Loads `.env`; exports `ANTHROPIC_API_KEY`, `CHROMA_PERSIST_DIR` |
| `embedder.py` | Lazy-loads `all-MiniLM-L6-v2` (sentence-transformers); `split_into_paragraphs`, `embed_text`, `embed_batch` |
| `vector_store.py` | ChromaDB singleton; `store_paragraphs` (upsert), `search_collection` (cosine query), `list_collections`, `delete_collection`. Collection names are sanitized to ChromaDB's 3–63 char alphanumeric constraint. |
| `scraper.py` | Playwright (headed Chromium) opens Confluence; `extract_links_with_claude` sends raw HTML (≤60 KB) to Claude and parses a JSON array of `{url, title}`; `extract_text_content` uses BeautifulSoup targeting `#main-content`/`.wiki-content` |
| `rag.py` | `rag_search_stream` async generator: embeds query → retrieves chunks → streams Claude response as SSE events (`type: text`, then `type: sources`, then `[DONE]`). Uses `cache_control: ephemeral` on the system prompt. |
| `main.py` | FastAPI app. In-memory `tasks` dict tracks background gather jobs. Static files mounted last (catches all non-API routes). |

### API endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/gather` | Start background scrape; returns `{task_id}` |
| `GET` | `/api/gather/{task_id}` | Poll gather progress/status |
| `GET` | `/api/search/stream` | SSE stream: `?query=...&collection_name=...&n_results=5` |
| `GET` | `/api/collections` | List ChromaDB collection names |
| `DELETE` | `/api/collections/{name}` | Delete a collection |

### Frontend (`frontend/`)

Vanilla JS single-page app with three tabs (Gather / Smart Search / Collections). SSE streaming is handled via the browser's native `EventSource` API. The search tab must use GET (not POST) because `EventSource` only supports GET requests.

### Key constraints

- **ChromaDB collection names** — sanitized via `_sanitize_name()` in `vector_store.py`: non-alphanumeric chars become `_`, max 63 chars, min 3 chars. The UI collection name and the stored name may differ if special chars are used.
- **Sentence-transformers is CPU-bound/sync** — wrapped with `run_in_executor` in `main.py` and `rag.py` to avoid blocking the event loop.
- **Playwright runs headed** — the browser window is intentionally visible so users can handle Confluence SSO/MFA login manually when credentials aren't provided.
- **HTML truncated at 60 KB** before sending to Claude for link extraction (`scraper.py:18`).
- **Gather task state is in-memory** — restarting the server loses all in-progress or completed task records (the ChromaDB data persists).
