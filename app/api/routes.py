from fastapi import APIRouter, HTTPException
from app.core.config import get_settings
from app.mcp.partners import build_partner_registry
from app.models.schemas import ChatRequest, ChatResponse, HealthResponse
from app.services.agent_service import AgentService

router=APIRouter(); service=AgentService()


def dependency_error_detail(error: BaseException) -> str:
    """Expose actionable leaf causes hidden by AnyIO task groups."""
    leaves: list[BaseException] = []
    pending = [error]
    while pending:
        current = pending.pop(0)
        nested = getattr(current, "exceptions", None)
        if nested:
            pending[0:0] = list(nested)
        else:
            leaves.append(current)
    details = []
    for leaf in leaves or [error]:
        detail = f"{type(leaf).__name__}: {leaf}"
        if detail not in details:
            details.append(detail)
    return "; ".join(details)[:2000]

@router.get("/health", response_model=HealthResponse)
async def health():
    s=get_settings()
    return HealthResponse(
        status="ok",
        openai_configured=bool(s.openai_api_key),
        partners=build_partner_registry(s).status(),
    )

@router.get("/v1/status")
async def status():
    s = get_settings()
    return {
        **(await health()).model_dump(),
        "model": s.openai_model,
        "environment": s.app_env,
        "require_write_approval": s.require_write_approval,
        "max_tool_calls": s.max_mcp_tool_calls,
        "mcp_timeout_seconds": s.mcp_timeout_seconds,
    }

@router.post("/v1/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try: return await service.chat(req)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Partner agent dependency failed: {dependency_error_detail(e)}",
        ) from e
