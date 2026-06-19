from __future__ import annotations
import json
from typing import AsyncIterator

import anthropic

from backend.config import ANTHROPIC_API_KEY
from backend.embedder import embed_text
from backend.vector_store import search_collection

_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are a helpful knowledge base assistant. \
Answer the user's question using ONLY the context excerpts provided. \
If the context does not contain enough information to answer fully, say so honestly. \
Be concise, accurate, and cite page titles when referencing specific sources. \
Do not invent information beyond what is in the provided context."""


async def rag_search_stream(
    query: str,
    collection_name: str,
    n_results: int = 5,
) -> AsyncIterator[str]:
    async for chunk in rag_chat_stream(
        [{"role": "user", "content": query}], collection_name, n_results
    ):
        yield chunk


async def rag_chat_stream(
    messages: list[dict],
    collection_name: str,
    n_results: int = 5,
) -> AsyncIterator[str]:
    latest_query = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )
    query_embedding = await _run_sync(embed_text, latest_query)
    chunks = search_collection(collection_name, query_embedding, n_results)

    if not chunks:
        yield f"data: {json.dumps({'type': 'text', 'content': 'No relevant content found in the knowledge base for this question.'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(
            f"[{i}] Source: {chunk['page_title']} ({chunk['source_url']})\n{chunk['text']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    # Inject RAG context into the latest user turn only
    claude_messages = list(messages)
    last_user_idx = next(
        i for i in range(len(claude_messages) - 1, -1, -1)
        if claude_messages[i]["role"] == "user"
    )
    claude_messages[last_user_idx] = {
        "role": "user",
        "content": f"Context excerpts:\n{context}\n\nQuestion: {claude_messages[last_user_idx]['content']}",
    }

    async with _client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=claude_messages,
    ) as stream:
        async for text in stream.text_stream:
            yield f"data: {json.dumps({'type': 'text', 'content': text})}\n\n"

    yield f"data: {json.dumps({'type': 'sources', 'content': chunks})}\n\n"
    yield "data: [DONE]\n\n"


async def _run_sync(fn, *args):
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn, *args)
