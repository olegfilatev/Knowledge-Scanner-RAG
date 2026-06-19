from __future__ import annotations
import asyncio
import json
import queue as queue_module
import re
import sys
import threading
from typing import Callable, Awaitable
from urllib.parse import urljoin

import anthropic
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from backend.config import ANTHROPIC_API_KEY

_anthropic = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


async def _extract_links_from_dom(page, base_url: str) -> list[dict]:
    """Query the live rendered DOM for Confluence page links.

    Scopes to the search-results area only — Confluence Cloud renders the left
    navigation tree inside <nav>/<aside>/[role="navigation"] which are excluded
    both by scoping to <main> and by the closest() guard below.
    """
    try:
        items = await page.evaluate("""() => {
            const scope =
                document.querySelector('[data-testid="advanced-search-resultlist"]') ||
                document.querySelector('[data-testid*="search-result" i]') ||
                document.querySelector('[id*="search-result" i]') ||
                document.querySelector('[class*="SearchResult"]') ||
                document.querySelector('main') ||
                document.querySelector('[role="main"]') ||
                document.body;

            // Selectors that identify sidebar / navigation containers to skip.
            const NAV_SELECTOR = [
                'nav',
                'aside',
                '[role="navigation"]',
                '[role="complementary"]',
                '[data-navgroup]',
                '[class*="Sidebar"]',
                '[class*="sidebar"]',
                '[class*="PageTree"]',
                '[class*="page-tree"]',
                '[class*="SpaceNav"]',
                '[class*="space-nav"]',
                '[class*="treeNav"]',
                '[class*="TreeNav"]',
                '[class*="leftPanel"]',
                '[class*="LeftPanel"]',
            ].join(', ');

            const seen = new Set();
            const out = [];

            for (const a of scope.querySelectorAll('a[href]')) {
                const url = a.href;
                if (!url || seen.has(url)) continue;

                // Must be a Confluence content page URL
                const isPage = (
                    url.includes('/wiki/spaces/') ||
                    url.includes('/wiki/pages/') ||
                    url.includes('/display/') ||
                    url.includes('/pages/viewpage.action') ||
                    url.includes('/pages/resumedraft.action')
                );
                if (!isPage) continue;

                // Skip utility pages
                if (/\\/(search|login|logout|setup|admin|createpage|editpage)/.test(url)) continue;

                // Skip anything inside a nav / sidebar container
                if (a.closest(NAV_SELECTOR)) continue;

                // Prefer a heading from the closest result card, fall back to link text
                const card = a.closest(
                    '[class*="result" i], [class*="Result" i], ' +
                    '[data-type], [class*="card" i], li, article'
                );
                const heading = card?.querySelector('h1,h2,h3,h4,h5,h6');
                const title = (heading?.innerText || a.innerText || a.title || '').trim();
                if (!title || title.length < 2) continue;

                seen.add(url);
                out.push({ url, title });
            }
            return out;
        }""")
        return items or []
    except Exception:
        return []


async def _extract_links_with_claude_fallback(
    page, base_url: str, search_query: str
) -> list[dict]:
    """Send visible text (not raw HTML) to Claude as a last resort.

    Uses innerText of the body instead of page.content() so the token budget
    is spent on actual human-readable content rather than JS bundles.
    """
    try:
        body_text = await page.evaluate("() => document.body?.innerText || ''")
    except Exception:
        body_text = ""
    truncated = body_text[:40_000]
    message = await _anthropic.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Below is the visible text of a Confluence search results page. "
                    f"The user searched for: \"{search_query}\"\n\n"
                    f"Extract page URLs and titles from the search results. "
                    f"Return ONLY a JSON array of objects with keys 'url' and 'title'. "
                    f"Base URL for resolving relative paths: {base_url}\n\n"
                    f"Text:\n{truncated}\n\n"
                    f"Return only the JSON array, no explanation."
                ),
            }
        ],
    )
    raw = message.content[0].text.strip()
    json_match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not json_match:
        return []
    try:
        links = json.loads(json_match.group())
        result = []
        for item in links:
            url = item.get("url", "").strip()
            title = item.get("title", "").strip()
            if url:
                if not url.startswith("http"):
                    url = urljoin(base_url, url)
                result.append({"url": url, "title": title})
        return result
    except json.JSONDecodeError:
        return []


# Ordered from most-specific to most-generic.
# Confluence Cloud uses .ak-renderer-document; Server uses #main-content / .wiki-content.
_CONTENT_SELECTORS = [
    "[data-testid='default-layout']",
    ".ak-renderer-document",
    "#main-content",
    ".wiki-content",
    "#content",
    "main",
    "article",
]


def extract_text_content(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    main = None
    for sel in _CONTENT_SELECTORS:
        # BeautifulSoup CSS-style select returns a list; take first match
        results = soup.select(sel)
        if results:
            main = results[0]
            break
    if main is None:
        main = soup.body or soup
    return main.get_text(separator="\n")


async def _scrape_page(page, url: str) -> tuple[str, str, str]:
    """Returns (title, text, note) where note describes what happened."""
    try:
        # networkidle waits until no network requests for 500 ms — required for
        # Confluence Cloud's React SPA which injects content after domcontentloaded.
        try:
            await page.goto(url, timeout=45_000, wait_until="networkidle")
        except Exception:
            # networkidle can time out on pages with persistent background polls;
            # fall back to domcontentloaded + an explicit wait.
            await page.goto(url, timeout=45_000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

        # Wait for the first recognisable Confluence content container to appear.
        for sel in _CONTENT_SELECTORS:
            try:
                await page.wait_for_selector(sel, timeout=4000)
                break
            except Exception:
                continue

        html = await page.content()
        title = await page.title()
        text = extract_text_content(html)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        clean = "\n\n".join(lines)
        note = f"{len(clean):,} chars"
        return title, clean, note
    except Exception as exc:
        return "", "", f"ERROR: {exc}"



async def _playwright_session(
    base_url: str,
    search_query: str,
    username: str,
    password: str,
    max_pages: int,
    progress_callback: Callable[[str], Awaitable[None]],
    proceed_event: threading.Event,
) -> list[dict]:
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=False)
    context = await browser.new_context()

    if username and password:
        await context.set_http_credentials({"username": username, "password": password})

    page = await context.new_page()

    try:
        await progress_callback("Opening Confluence...")
        search_url = f"{base_url.rstrip('/')}/search?text={search_query.replace(' ', '+')}"
        try:
            await page.goto(search_url, timeout=30_000, wait_until="domcontentloaded")
        except Exception:
            await page.goto(search_url, timeout=60_000, wait_until="load")

        await page.wait_for_timeout(1500)
        await progress_callback(
            "Browser ready. Log in if needed and navigate to the search results you want, "
            "then click 'Process Current Page' in the app."
        )

        # Wait until the user clicks "Process Page" in the UI (sets proceed_event)
        # or closes the browser.
        while not proceed_event.is_set():
            await asyncio.sleep(0.3)
            if not browser.is_connected():
                await progress_callback("Browser was closed before processing.")
                return []

        await progress_callback("Processing current page...")
        await progress_callback("Extracting links from DOM...")
        links = await _extract_links_from_dom(page, base_url)
        await progress_callback(f"DOM extraction: {len(links)} link(s) found.")

        if not links:
            await progress_callback("DOM extraction found nothing — trying Claude fallback...")
            links = await _extract_links_with_claude_fallback(page, base_url, search_query)
            await progress_callback(f"Claude fallback: {len(links)} link(s) found.")

        if not links:
            await progress_callback(
                "No links found. Make sure you are on a Confluence search results page "
                "with visible results."
            )
            await browser.close()
            return []

        links = links[:max_pages]
        await progress_callback(f"Found {len(links)} pages to scrape.")

        results = []
        for i, link in enumerate(links, 1):
            url = link["url"]
            await progress_callback(f"[{i}/{len(links)}] {link.get('title') or url}")
            title, text, note = await _scrape_page(page, url)
            if text:
                results.append({
                    "url": url,
                    "title": title or link.get("title", ""),
                    "text": text,
                })
                await progress_callback(f"    ✓ {note}")
            else:
                await progress_callback(f"    ✗ Skipped — {note}")

        ok = len(results)
        skipped = len(links) - ok
        await progress_callback(
            f"Scraping done: {ok} pages extracted"
            + (f", {skipped} skipped." if skipped else ".")
        )
        await browser.close()
        return results

    except Exception:
        if browser.is_connected():
            await browser.close()
        raise
    finally:
        await pw.stop()


async def search_confluence(
    base_url: str,
    search_query: str,
    username: str = "",
    password: str = "",
    max_pages: int = 10,
    progress_callback: Callable[[str], Awaitable[None]] | None = None,
    proceed_event: threading.Event | None = None,
) -> list[dict]:
    """Run the Playwright session in a dedicated thread with a ProactorEventLoop.

    Pauses after opening the browser and waits for `proceed_event` to be set
    before processing the page. If `proceed_event` is None, processing starts
    immediately (auto-proceed).
    """
    if proceed_event is None:
        proceed_event = threading.Event()
        proceed_event.set()  # auto-proceed

    progress_q: queue_module.Queue = queue_module.Queue()
    result_container: list = []
    error_container: list = []

    def _thread_main():
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
        else:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _local_progress(msg: str):
            progress_q.put(("progress", msg))

        try:
            pages = loop.run_until_complete(
                _playwright_session(
                    base_url, search_query, username, password,
                    max_pages, _local_progress, proceed_event,
                )
            )
            result_container.append(pages)
        except Exception as exc:
            error_container.append(exc)
        finally:
            progress_q.put(("done", None))
            loop.close()

    thread = threading.Thread(target=_thread_main, daemon=True)
    thread.start()

    finished = False
    while not finished:
        try:
            kind, value = progress_q.get(timeout=0.1)
            if kind == "progress":
                if progress_callback:
                    await progress_callback(value)
            elif kind == "done":
                finished = True
        except queue_module.Empty:
            await asyncio.sleep(0.05)

    thread.join()

    if error_container:
        raise error_container[0]

    return result_container[0] if result_container else []
