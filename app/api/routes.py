from pathlib import Path
from fastapi import APIRouter, HTTPException
from app.core.config import get_settings
from app.models.schemas import ChatRequest, ChatResponse, HealthResponse
from app.services.agent_service import AgentService

router=APIRouter(); service=AgentService()

@router.get("/health", response_model=HealthResponse)
async def health():
    s=get_settings()
    return HealthResponse(status="ok",openai_configured=bool(s.openai_api_key),notion_token_present=Path(s.notion_mcp_token_file).exists())

@router.get("/v1/status")
async def status():
    s = get_settings()
    return {
        **(await health()).model_dump(),
        "model": s.openai_model,
        "environment": s.app_env,
        "notion_mcp_url": s.notion_mcp_url,
        "require_write_approval": s.require_write_approval,
        "max_tool_calls": s.max_mcp_tool_calls,
        "mcp_timeout_seconds": s.mcp_timeout_seconds,
    }

@router.post("/v1/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try: return await service.chat(req)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Partner agent dependency failed: {type(e).__name__}: {e}") from e
