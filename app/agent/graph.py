import json

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.agent.state import AgentState
from app.core.config import get_settings
from app.llm.openai_client import LLMService
from app.mcp.notion_client import NotionMCPClient, is_write_tool
from app.models.schemas import Risk

llm = LLMService()
mcp = NotionMCPClient()
settings = get_settings()

async def classify(state: AgentState):
    return {"route": await llm.classify(state["message"]), "selected_tools": [], "tool_calls": [], "tool_results": [], "approval_required": False}

async def general_or_mcp(state: AgentState):
    return "discover_tools" if state["route"].requires_mcp else "general"

async def general(state: AgentState):
    return {"answer": await llm.general_answer(state["message"])}

async def discover_tools(state: AgentState):
    return {"tools": await mcp.list_tools()}

async def plan_tools(state: AgentState):
    remaining = settings.max_mcp_tool_calls - len(state.get("tool_calls", []))
    if remaining <= 0:
        return {"selected_tools": []}
    calls = await llm.select_tools(
        state["message"], state["route"], state["tools"],
        state.get("tool_calls", []), state.get("tool_results", []),
    )
    known={t["name"] for t in state["tools"]}
    completed={(c["name"], json.dumps(c.get("arguments",{}), sort_keys=True, default=str)) for c in state.get("tool_calls",[])}
    calls=[c for c in calls if c["name"] in known
           and not (state["route"].risk == Risk.READ and is_write_tool(c["name"]))
           and (c["name"], json.dumps(c.get("arguments",{}), sort_keys=True, default=str)) not in completed][:remaining]
    return {"selected_tools": calls}

def after_plan(state: AgentState):
    return "approval_gate" if state.get("selected_tools") else "synthesize"

async def approval_gate(state: AgentState):
    writes=[c for c in state.get("selected_tools",[]) if is_write_tool(c["name"])]
    if writes and settings.require_write_approval and not state.get("approve_write",False):
        return {"approval_required":True, "answer":"This request would modify Notion. Re-submit with approve_write=true after reviewing the requested action(s)."}
    return {"approval_required":False}

def after_approval(state: AgentState):
    return END if state.get("approval_required") else "execute_tools"

async def execute_tools(state: AgentState):
    results=list(state.get("tool_results",[])); calls=list(state.get("tool_calls",[]))
    for call in state.get("selected_tools",[]):
        # Defense in depth: route risk and actual tool name must agree.
        if state["route"].risk == Risk.READ and is_write_tool(call["name"]):
            continue
        result=await mcp.call_tool(call["name"], call.get("arguments",{}))
        calls.append({"name":call["name"],"arguments":call.get("arguments",{})})
        results.append(result)
    return {"tool_calls":calls,"tool_results":results}

async def synthesize(state: AgentState):
    return {"answer": await llm.answer(state["message"], state["route"], state.get("tool_results",[]))}

def build_graph(checkpointer=None):
    g=StateGraph(AgentState)
    g.add_node("classify", classify); g.add_node("general", general); g.add_node("discover_tools", discover_tools)
    g.add_node("plan_tools", plan_tools); g.add_node("approval_gate", approval_gate); g.add_node("execute_tools", execute_tools); g.add_node("synthesize", synthesize)
    g.add_edge(START,"classify")
    g.add_conditional_edges("classify", general_or_mcp, {"discover_tools":"discover_tools","general":"general"})
    g.add_edge("general",END); g.add_edge("discover_tools","plan_tools")
    g.add_conditional_edges("plan_tools", after_plan, {"approval_gate":"approval_gate","synthesize":"synthesize"})
    g.add_conditional_edges("approval_gate", after_approval, {END:END,"execute_tools":"execute_tools"})
    g.add_edge("execute_tools","plan_tools"); g.add_edge("synthesize",END)
    return g.compile(checkpointer=checkpointer or MemorySaver())
