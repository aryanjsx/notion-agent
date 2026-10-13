"""Routes for serving the Web UI."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["UI"])

templates_dir = Path(__file__).parent.parent / "web" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """Serve the Notion AI Agent control dashboard."""
    return templates.TemplateResponse(request=request, name="index.html")
