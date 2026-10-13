"""Main FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.agent.loop import get_agent_loop
from app.api.routes_tasks import router as tasks_router
from app.api.routes_ui import router as ui_router
from app.api.routes_webhooks import router as webhooks_router
from app.config import settings
from app.services.queue import get_queue_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("notion_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan setup and background task registration."""
    logger.info("Starting Notion AI Agent (env: %s)...", settings.app_env)
    queue = get_queue_service()
    agent_loop = get_agent_loop()

    # Wire local async task execution if in development/mock mode
    queue.register_local_handler(agent_loop.run)
    yield
    logger.info("Shutting down Notion AI Agent...")


app = FastAPI(
    title="Notion AI Agent API",
    description="Autonomous Notion AI Agent on Google Cloud Platform with tool-calling and document intelligence.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
static_dir = Path(__file__).parent.parent / "web" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Routers
app.include_router(ui_router)
app.include_router(tasks_router)
app.include_router(webhooks_router)


@app.get("/health")
async def health_check():
    """Health check probe for Cloud Run and load balancers."""
    return {
        "status": "healthy",
        "env": settings.app_env,
        "gcp_project": settings.gcp_project_id,
        "vertex_ai": settings.use_vertex_ai,
    }
