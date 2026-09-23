import json
from openai import AsyncOpenAI
from app.core.config import get_settings
from app.models.schemas import RouteDecision

ROUTE_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type":"string","enum":["search_knowledge","read_page","create_page","update_page","comments","users","general"]},
        "partner": {"type":"string","enum":["notion"]},
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
            instructions=("You are an enterprise partner-agent router. Classify the user's request for a Notion knowledge partner. "
                          "Read/search/fetch/list are read risk. Create/update/move/comment are write risk. "
                          "Set requires_mcp=false only for greetings or general conversation that does not need workspace data."),
            input=message,
            text={"format":{"type":"json_schema","name":"route_decision","strict":True,"schema":ROUTE_SCHEMA}},
        )
        return RouteDecision.model_validate_json(response.output_text)

    async def select_tools(self, message: str, route: RouteDecision, tools: list[dict]) -> list[dict]:
        compact = [{"name":t["name"],"description":t.get("description",""),"inputSchema":t.get("inputSchema",{})} for t in tools]
        schema = {"type":"object","properties":{"calls":{"type":"array","maxItems":4,"items":{"type":"object","properties":{"name":{"type":"string"},"arguments":{"type":"object","additionalProperties":True}},"required":["name","arguments"],"additionalProperties":False}}},"required":["calls"],"additionalProperties":False}
        response = await self.client.responses.create(
            model=self.model,
            instructions=("Choose the minimum MCP tool calls needed. Only choose names from AVAILABLE_TOOLS. "
                          "Never choose a write tool for a read request. If a fetch needs an ID that search can discover, choose search first only; the graph can plan another round after results."),
            input=f"USER_REQUEST:\n{message}\n\nROUTE:\n{route.model_dump_json()}\n\nAVAILABLE_TOOLS:\n{json.dumps(compact)}",
            text={"format":{"type":"json_schema","name":"tool_plan","strict":True,"schema":schema}},
        )
        return json.loads(response.output_text)["calls"]

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
