# Knowledge Scanner RAG

A two-phase Retrieval-Augmented Generation (RAG) app that scrapes Confluence pages, embeds them into a local vector store, and lets you chat with your knowledge base using Claude AI.

## How It Works

**Phase 1 — Gather:** Open a Confluence search page in a real browser (Playwright), scrape the result pages, split text into paragraphs, embed them with `all-MiniLM-L6-v2`, and persist to ChromaDB.

**Phase 2 — Search:** Ask a question in the chat UI. The query is embedded, similar chunks are retrieved from ChromaDB, and Claude streams an answer grounded in those sources.

```
Confluence search page (Playwright, headed browser)
        │
        ▼
  extract links (DOM scraping + Claude fallback)
        │
        ▼
  scrape each page (BeautifulSoup)
        │
        ▼
  split → embed (sentence-transformers)  →  ChromaDB (local)
                                                  │
                                     embed query ─┘
                                                  │
                                       retrieve top-N chunks
                                                  │
                                       Claude Sonnet (streaming)
                                                  │
                                       SSE → browser chat UI
```

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Claude Sonnet (`claude-sonnet-4-6`) via Anthropic API |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers, runs locally) |
| Vector store | ChromaDB (persistent, cosine similarity) |
| Scraping | Playwright (headed Chromium) + BeautifulSoup |
| Backend | FastAPI + Uvicorn |
| Frontend | Vanilla JS (EventSource SSE streaming) |

## Prerequisites

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/)
- Access to a Confluence instance (Cloud or Server)

## Setup

```bash
# 1. Clone and install dependencies
git clone https://github.com/your-username/KnowlegeScannerRAG.git
cd KnowlegeScannerRAG
pip install -r requirements.txt

# 2. Install the Playwright browser (first time only)
playwright install chromium

# 3. Configure environment
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
```

**.env** fields:

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key |
| `CHROMA_PERSIST_DIR` | No | Path to ChromaDB storage (default: `./chroma_db`) |
| `HF_TOKEN` | No | HuggingFace token for higher model download rate limits |

## Running

```bash
python run.py
# → http://localhost:8000
```

Run from the repo root so FastAPI can find the `frontend/` directory.

## Usage

### 1. Gather Data

1. Open the **Gather Data** tab.
2. Enter your Confluence base URL (e.g. `https://yourcompany.atlassian.net/wiki`).
3. Enter a search query and a collection name.
4. Click **Open Browser** — a Chromium window opens.
5. Log in to Confluence if prompted (SSO/MFA is handled manually in the browser).
6. Navigate to the search results you want to index.
7. Click **Process Current Page** in the app — the scraper extracts and indexes all result pages.

### 2. Smart Search

1. Open the **Smart Search** tab.
2. Select a collection from the dropdown.
3. Ask a question — Claude streams an answer with source references.

### 3. Manage Collections

Use the **Collections** tab to view and delete stored knowledge bases.

## Project Structure

```
backend/
  config.py        # Loads .env; exports API keys and paths
  embedder.py      # sentence-transformers: split + embed
  vector_store.py  # ChromaDB: store, search, list, delete
  scraper.py       # Playwright + BeautifulSoup scraping
  rag.py           # RAG pipeline: embed query → retrieve → stream Claude
  main.py          # FastAPI app + background task management
frontend/
  index.html       # Single-page app (three tabs)
  style.css
  app.js           # SSE streaming via EventSource
run.py             # Entry point (sets Windows ProactorEventLoop before uvicorn)
```

## API Reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/gather` | Start background scrape; returns `{task_id}` |
| `GET` | `/api/gather/{task_id}` | Poll gather progress/status |
| `GET` | `/api/search/stream` | SSE stream (`?query=&collection_name=&n_results=5`) |
| `GET` | `/api/collections` | List all ChromaDB collections |
| `DELETE` | `/api/collections/{name}` | Delete a collection |

## Notes

- **Headed browser** — Playwright runs with a visible window so you can complete Confluence SSO/MFA login manually. Credentials are optional; leave them blank to log in interactively.
- **ChromaDB collection names** are sanitized: non-alphanumeric characters become `_`, length clamped to 3–63 chars.
- **Gather task state is in-memory** — restarting the server clears task history, but the indexed ChromaDB data persists on disk.
- **CPU-bound embedding** is offloaded with `run_in_executor` to avoid blocking the async event loop.

## License

MIT
