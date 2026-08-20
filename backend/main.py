from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from llm import GeminiLLM, GPT
from scheduler import start_scheduler, stop_scheduler
from routers import build, prices, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Instantiate LLM providers once, start the scheduler, clean up on shutdown."""
    app.state.llm_providers = [
        GeminiLLM(),
        GPT(),
    ]

    # start_scheduler()

    yield

    # stop_scheduler()

    for p in app.state.llm_providers:
        if hasattr(p, "client") and hasattr(p.client, "close"):
            try:
                p.client.close()
            except Exception:
                pass


app = FastAPI(
    title="EG PC Builder API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten this in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(build.router)
app.include_router(prices.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    """Quick liveness check."""
    return {"status": "ok"}
