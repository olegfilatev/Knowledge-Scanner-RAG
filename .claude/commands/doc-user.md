Generate end-user documentation for this project and write it to `docs/user/$ARGUMENTS-user.md`.

**Project name:** $ARGUMENTS (if empty, use "KnowlegeScannerRAG")

## Steps

1. Read and analyze the following files before writing anything:
   - `CLAUDE.md`
   - `frontend/index.html` (to understand all UI fields, labels, and controls)
   - `frontend/app.js` (to understand user-visible behavior, status messages, and error handling)
   - `frontend/style.css` (to understand tab names and layout)
   - `backend/main.py` (to understand task lifecycle status messages shown to the user)
   - `backend/scraper.py` (to understand progress messages the user sees during gather)

2. Create the directory `docs/user/` if it does not exist.

3. Attempt to capture screenshots automatically:
   - Check if the dev server is already running on http://localhost:8000 by making a request to it.
   - If it is running AND Playwright is available, use it (headless Chromium) to capture screenshots of:
     a. The Gather tab (initial empty state)
     b. The Gather tab with the progress card visible (if achievable without real Confluence)
     c. The Smart Search tab
     d. The Collections tab
   - Save screenshots to `docs/user/screenshots/` as PNG files named: `01-gather-tab.png`, `02-search-tab.png`, `03-collections-tab.png`.
   - If the server is not running or Playwright capture fails, skip silently and use placeholder syntax (see below).

4. Write the file `docs/user/$ARGUMENTS-user.md` (use "KnowlegeScannerRAG" if no argument was given).

---

## Screenshot placeholder syntax

For any screenshot that was NOT captured automatically, insert this exact markdown block:
```
> **[SCREENSHOT PLACEHOLDER]**
> *Caption: <describe what should be shown>*
> `docs/user/screenshots/<filename>.png`
```

For any screenshot that WAS captured, insert:
```markdown
![<alt text>](screenshots/<filename>.png)
*<caption>*
```

---

## Output file structure

```markdown
# $ARGUMENTS — User Guide

> For technical details see: [Developer Documentation](../../dev/$ARGUMENTS-dev.md)

## Table of Contents
(auto-generate with anchor links to every section below)

## What Is This App?
2–3 plain-English sentences explaining what the app does and the problem it solves. No jargon. Use the phrases "Confluence", "knowledge base", and "AI-powered answers".

## Who Is This For?
One short paragraph describing the target user (someone who needs to search Confluence but wants faster, summarized answers).

## Prerequisites
Bulleted list:
- Access to a Confluence instance (URL required)
- The app running locally (link to the setup section in the Developer Documentation)
- A modern web browser
- (Optional) Confluence username and password for auto-login

## Getting Started
Steps to open the app: navigate to http://localhost:8000, what you see on first load (three tabs).

> **[SCREENSHOT PLACEHOLDER]**
> *Caption: The Knowledge Scanner RAG home screen showing three tabs: Gather Data, Smart Search, Collections*
> `docs/user/screenshots/00-home.png`

## Tab 1 — Gather Data
Goal of this tab in one sentence.

### Step 1: Fill in the Form
Table listing every form field visible in the Gather tab:
| Field | What to enter | Example |
with rows for: Confluence Base URL, Search Query, Collection Name, Max Pages, Username, Password.

> **[SCREENSHOT PLACEHOLDER]**
> *Caption: The Gather Data tab with all fields filled in*
> `docs/user/screenshots/01-gather-filled.png`

### Step 2: Open the Browser
What happens when you click "Open Browser":
- A Chromium window appears
- If you did not enter credentials, how to log in manually
- What the progress log shows

> **[SCREENSHOT PLACEHOLDER]**
> *Caption: The progress log showing "Browser ready" message*
> `docs/user/screenshots/02-browser-ready.png`

### Step 3: Process the Current Page
When and why to click "Process Current Page". What the app does next (Claude extracts links, pages are scraped, embeddings are stored).

### Step 4: Wait for Completion
What "done" status looks like. What the total paragraphs count means.

> **[SCREENSHOT PLACEHOLDER]**
> *Caption: Progress log showing "Stored N paragraphs" completion message*
> `docs/user/screenshots/03-gather-done.png`

### Gather — Common Issues
Table: Problem | Likely Cause | Fix
Cover: no links found, browser closed early, SSO login required, collection name with special characters.

## Tab 2 — Smart Search
Goal of this tab in one sentence.

### Step 1: Select a Collection
Dropdown behavior — how collections appear, what to do if the list is empty (go back to Gather).

### Step 2: Enter Your Question
Plain-English tips for writing effective questions.

### Step 3: Adjust Context Chunks (optional)
What the "Context Chunks" number controls and when to increase or decrease it.

### Step 4: Read the Answer
Explain: streaming text, the Sources section at the bottom (page title + URL), what it means if the answer says "not enough information".

> **[SCREENSHOT PLACEHOLDER]**
> *Caption: Smart Search tab showing a streamed answer with sources listed below*
> `docs/user/screenshots/04-search-answer.png`

### Search — Tips & Limitations
- The app only answers from the pages you gathered — it cannot search the live Confluence
- More specific questions yield better answers
- Increase context chunks if the answer seems incomplete

## Tab 3 — Collections
Goal of this tab in one sentence.

### Viewing Collections
What the list shows.

### Deleting a Collection
When you might want to delete one. What happens to the data (ChromaDB records removed, collection disappears from dropdown). Warning: this is irreversible.

> **[SCREENSHOT PLACEHOLDER]**
> *Caption: Collections tab showing a list of stored collections with delete buttons*
> `docs/user/screenshots/05-collections.png`

## End-to-End Workflow Summary
A numbered checklist the user can follow from zero to answer:
1. Open the app
2. Go to "Gather Data"
3. Fill in the form
4. Open Browser → log in if needed → navigate to search results → Process Current Page
5. Wait for "done"
6. Go to "Smart Search"
7. Select your collection → type a question → click Ask
8. Read the answer and sources

## Glossary
Table: Term | Plain-English Definition
Cover: Collection, Embedding, Context Chunks, RAG, Confluence, SSE / streaming.

## Troubleshooting
Table: Symptom | Likely Cause | Resolution
Cover: blank collections dropdown, "No relevant content found", browser window does not open, app won't start, answer cuts off mid-sentence.
```

After writing the file, report:
- The path where it was saved
- Whether any screenshots were captured automatically (list filenames) or all placeholders were used
- Approximate line count of the generated file
