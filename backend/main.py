from __future__ import annotations
import asyncio
import threading
import uuid
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.embedder import embed_batch, split_into_paragraphs
from backend.rag import rag_chat_stream, rag_search_stream
from backend.scraper import search_confluence
from backend.vector_store import delete_collection, list_collections, store_paragraphs

app = FastAPI(title="Knowledge Scanner RAG")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

tasks: dict[str, dict] = {}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    collection_name: str
    messages: list[ChatMessage]
    n_results: int = 5


class GatherRequest(BaseModel):
    base_url: str
    search_query: str
    collection_name: str
    username: Optional[str] = ""
    password: Optional[str] = ""
    max_pages: int = 10


async def _run_gather(task_id: str, req: GatherRequest):
    task = tasks[task_id]
    task["progress"] = []
    task["total_paragraphs"] = 0

    async def progress(msg: str):
        task["progress"].append(msg)

    try:
        pages = await search_confluence(
            base_url=req.base_url,
            search_query=req.search_query,
            username=req.username or "",
            password=req.password or "",
            max_pages=req.max_pages,
            progress_callback=progress,
            proceed_event=task["proceed_event"],
        )

        task["status"] = "processing"
        await progress(f"Generating embeddings for {len(pages)} pages...")
        total = 0
        for page in pages:
            paragraphs = split_into_paragraphs(page["text"])
            if not paragraphs:
                continue
            embeddings = await asyncio.get_event_loop().run_in_executor(
                None, embed_batch, paragraphs
            )
            n = store_paragraphs(
                collection_name=req.collection_name,
                paragraphs=paragraphs,
                embeddings=embeddings,
                source_url=page["url"],
                page_title=page["title"],
            )
            total += n

        task["total_paragraphs"] = total
        task["status"] = "done"
        await progress(f"Stored {total} paragraphs in collection '{req.collection_name}'.")
    except Exception as exc:
        task["status"] = "error"
        task["error"] = str(exc)
        await progress(f"Error: {exc}")


@app.post("/api/gather")
async def start_gather(req: GatherRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    proceed_event = threading.Event()
    tasks[task_id] = {
        "status": "waiting_for_user",
        "progress": [],
        "total_paragraphs": 0,
        "proceed_event": proceed_event,
    }
    background_tasks.add_task(_run_gather, task_id, req)
    return {"task_id": task_id}


@app.post("/api/gather/{task_id}/process")
async def trigger_process(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    task = tasks[task_id]
    if task["status"] != "waiting_for_user":
        raise HTTPException(
            status_code=400,
            detail=f"Task is in state '{task['status']}', expected 'waiting_for_user'",
        )
    task["status"] = "processing"
    task["proceed_event"].set()
    return {"triggered": True}


@app.get("/api/gather/{task_id}")
async def get_gather_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    task = tasks[task_id]
    return {k: v for k, v in task.items() if k != "proceed_event"}


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    if not req.collection_name.strip():
        raise HTTPException(status_code=400, detail="collection_name cannot be empty")
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")
    messages = [m.model_dump() for m in req.messages]
    return StreamingResponse(
        rag_chat_stream(messages, req.collection_name, req.n_results),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/search/stream")
async def search_stream(query: str, collection_name: str, n_results: int = 5):
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if not collection_name.strip():
        raise HTTPException(status_code=400, detail="collection_name cannot be empty")

    return StreamingResponse(
        rag_search_stream(query, collection_name, n_results),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/collections")
async def get_collections():
    return {"collections": list_collections()}


@app.delete("/api/collections/{name}")
async def remove_collection(name: str):
    ok = delete_collection(name)
    if not ok:
        raise HTTPException(status_code=404, detail="Collection not found")
    return {"deleted": name}


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
