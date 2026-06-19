import sys
import asyncio

# uvicorn forces WindowsSelectorEventLoopPolicy on Windows, which doesn't support
# subprocess creation (needed by Playwright). Override it before uvicorn loads.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
