from typing import Any, TypedDict
from app.models.schemas import RouteDecision

class AgentState(TypedDict, total=False):
    message: str
    user_id: str
    thread_id: str
    approve_write: bool
    route: RouteDecision
    tools: list[dict[str, Any]]
    selected_tools: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    answer: str
    approval_required: bool
    error: str
