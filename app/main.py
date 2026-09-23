import logging, structlog
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.api.routes import router
from app.core.config import get_settings

s=get_settings()
logging.basicConfig(level=s.log_level)
structlog.configure(processors=[structlog.processors.TimeStamper(fmt="iso"),structlog.processors.JSONRenderer()])
app=FastAPI(title="Notion Partner Agent",version="1.0.0",description="Production-style Partner Agent using OpenAI, LangGraph and Notion's real MCP server.")
app.include_router(router)
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", include_in_schema=False)
async def workspace():
    return FileResponse(static_dir / "index.html")
