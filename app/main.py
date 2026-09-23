import logging, structlog
from fastapi import FastAPI
from app.api.routes import router
from app.core.config import get_settings

s=get_settings()
logging.basicConfig(level=s.log_level)
structlog.configure(processors=[structlog.processors.TimeStamper(fmt="iso"),structlog.processors.JSONRenderer()])
app=FastAPI(title="Notion Partner Agent",version="1.0.0",description="Production-style Partner Agent using OpenAI, LangGraph and Notion's real MCP server.")
app.include_router(router)
