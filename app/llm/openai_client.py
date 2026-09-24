import json
from openai import AsyncOpenAI
from app.core.config import get_settings
from app.mcp.partners import SUPPORTED_PARTNERS
from app.models.schemas import RouteDecision

ROUTE_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type":"string","enum":["search","read","create","update","comments","users","general"]},
        "partner": {"type":"string","enum":list(SUPPORTED_PARTNERS)},
        "risk": {"type":"string","enum":["read","write"]},
        "objective": {"type":"string"},
        "requires_mcp": {"type":"boolean"}
    },
    "required": ["intent","partner","risk","objective","requires_mcp"],
    "additionalProperties": False
}

class LLMService:
    def __init__(self):
        s = get_settings()
        self.model = s.openai_model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            key = get_settings().openai_api_key
            if not key:
                raise RuntimeError("Set OPENAI_API_KEY in .env and restart the server to enable chat.")
            self._client = AsyncOpenAI(api_key=key)
        return self._client

    async def classify(self, message: str) -> RouteDecision:
        response = await self.client.responses.create(
            model=self.model,
            instructions=("You are an enterprise multi-partner agent router. Route explicit Notion page/workspace requests to notion, "
                          "and Linear issue/project/cycle/team requests to linear. When the partner is implicit, infer it from the object "
                          "being discussed; default ambiguous knowledge/page requests to notion and ambiguous issue/project requests to linear. "
                          "Read/search/fetch/list are read risk. Create/update/move/comment/assign are write risk. "
                          "Set requires_mcp=false only for greetings or general conversation that does not need workspace data."),
            input=message,
            text={"format":{"type":"json_schema","name":"route_decision","strict":True,"schema":ROUTE_SCHEMA}},
        )
        return RouteDecision.model_validate_json(response.output_text)

    async def select_tools(self, message: str, route: RouteDecision, tools: list[dict],
                           previous_calls: list[dict] | None = None,
                           previous_results: list[dict] | None = None) -> list[dict]:
        compact = [{"name":t["name"],"description":t.get("description",""),"inputSchema":t.get("inputSchema",{})} for t in tools]
        # Strict Structured Outputs cannot contain an open-ended object schema:
        # every object must set additionalProperties=false. MCP argument shapes
        # are discovered at runtime, so carry each argument object as JSON text
        # and decode it only after the structured response has been validated.
        schema = {"type":"object","properties":{"calls":{"type":"array","maxItems":4,"items":{"type":"object","properties":{"name":{"type":"string"},"arguments_json":{"type":"string"}},"required":["name","arguments_json"],"additionalProperties":False}}},"required":["calls"],"additionalProperties":False}
        response = await self.client.responses.create(
            model=self.model,
            instructions=(f"You are planning tools for the {route.partner} partner. Choose the minimum MCP tool calls needed. "
                          "Only choose names from AVAILABLE_TOOLS. "
                          "Never choose a write tool for a read request. If a fetch needs an ID that search can discover, choose search first only; the graph can plan another round after results."),
            input=(f"USER_REQUEST:\n{message}\n\nROUTE:\n{route.model_dump_json()}\n\nAVAILABLE_TOOLS:\n{json.dumps(compact)}\n\n"
                   f"PREVIOUS_TOOL_CALLS:\n{json.dumps(previous_calls or [], default=str)}\n\n"
                   f"PREVIOUS_TOOL_RESULTS:\n{json.dumps(previous_results or [], default=str)[:50000]}\n\n"
                   "Do not repeat a completed call. If a capability-discovery or tool-access result is needed, use it first, then choose from newly available tools. "
                   "Return an empty calls list when the available results are sufficient to answer. "
                   "For every call, put the tool arguments object in arguments_json as valid JSON text."),
            text={"format":{"type":"json_schema","name":"tool_plan","strict":True,"schema":schema}},
        )
        calls = []
        for call in json.loads(response.output_text)["calls"]:
            try:
                arguments = json.loads(call["arguments_json"])
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(arguments, dict):
                calls.append({"name": call["name"], "arguments": arguments})
        return calls

    async def answer(self, message: str, route: RouteDecision, results: list[dict]) -> str:
        response = await self.client.responses.create(
            model=self.model,
            instructions=("You are a concise enterprise knowledge assistant. Answer only from MCP results when workspace facts are requested. "
                          "If results are empty or failed, say that clearly. Never claim a write succeeded unless the tool result says it succeeded."),
            input=f"USER_REQUEST:\n{message}\n\nROUTE:\n{route.model_dump_json()}\n\nMCP_RESULTS:\n{json.dumps(results, default=str)[:50000]}",
        )
        return response.output_text

    async def general_answer(self, message: str) -> str:
        r = await self.client.responses.create(model=self.model, input=message)
        return r.output_text
