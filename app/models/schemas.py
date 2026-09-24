from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

class Intent(str, Enum):
    SEARCH = "search"
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    COMMENTS = "comments"
    USERS = "users"
    GENERAL = "general"

class Risk(str, Enum):
    READ = "read"
    WRITE = "write"

class RouteDecision(BaseModel):
    intent: Intent
    partner: str = "notion"
    risk: Risk
    objective: str
    requires_mcp: bool

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    thread_id: str = Field(min_length=1, max_length=128)
    user_id: str = Field(min_length=1, max_length=128)
    approve_write: bool = False

class ChatResponse(BaseModel):
    answer: str
    thread_id: str
    intent: Intent
    partner: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    planned_tools: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    approval_required: bool = False
    trace_id: str

class HealthResponse(BaseModel):
    status: str
    openai_configured: bool
    partners: list[dict[str, Any]] = Field(default_factory=list)
