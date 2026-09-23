import uuid
from app.agent.graph import build_graph
from app.models.schemas import ChatRequest, ChatResponse, Intent

graph = build_graph()

class AgentService:
    async def chat(self, req: ChatRequest) -> ChatResponse:
        trace_id=str(uuid.uuid4())
        state={"message":req.message,"thread_id":req.thread_id,"user_id":req.user_id,"approve_write":req.approve_write}
        result=await graph.ainvoke(state, config={"configurable":{"thread_id":req.thread_id},"metadata":{"trace_id":trace_id,"user_id":req.user_id}})
        route=result.get("route")
        return ChatResponse(answer=result.get("answer","No response generated."),thread_id=req.thread_id,
            intent=route.intent if route else Intent.GENERAL, partner=route.partner if route else "notion",
            tool_calls=result.get("tool_calls",[]),
            planned_tools=result.get("selected_tools",[]) if result.get("approval_required") else [],
            tool_results=result.get("tool_results",[]),
            approval_required=result.get("approval_required",False),trace_id=trace_id)
