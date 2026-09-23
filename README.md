# Notion Partner Agent — OpenAI + LangGraph + Real MCP

A production-style reference application for the same architectural ideas as an enterprise **Partner Agent**: an AI assistant receives a request, an OpenAI model classifies intent, LangGraph controls the workflow, a partner router selects Notion, the app discovers tools from Notion's **real hosted MCP server**, invokes the selected MCP tool, and OpenAI synthesizes the result.

## Architecture

```text
Client
  |
  v
FastAPI  POST /v1/chat
  |
  v
LangGraph Partner Agent
  |
  +--> classify_intent (OpenAI Structured Output)
  |       intents: search/read/create/update/comments/users/general
  |
  +--> route_partner (NOTION in this project)
  |
  +--> discover_tools (live MCP tools/list)
  |
  +--> select_tool (OpenAI, constrained to discovered tools)
  |
  +--> write approval gate
  |
  +--> execute_tool (MCP tools/call)
  |          |
  |          v
  |    https://mcp.notion.com/mcp
  |          |
  |          v
  |      Your Notion workspace
  |
  +--> synthesize_response (OpenAI grounded on MCP result)
  v
JSON response
```

## Why this is close to the enterprise Partner Agent pattern

| This project | Enterprise equivalent |
|---|---|
| FastAPI `/v1/chat` | AI Assistant/A2A entry point |
| Partner Agent graph | Partner Agent |
| Notion | External partner such as Electric |
| Notion hosted MCP | Electric MCP |
| Notion OAuth user identity | user-scoped partner OAuth |
| Intent classifier | partner/domain intent classification |
| live MCP tool discovery | partner capability discovery |
| tool planner/router | capability routing |
| approval gate | write/action governance |
| LangGraph thread | conversation/workflow state |

## Real components — no dummy partner data

- **OpenAI Responses API** is used for intent classification, tool planning, and final answer generation.
- **Notion's hosted MCP** is used at `https://mcp.notion.com/mcp`.
- The app performs MCP `initialize`, `tools/list`, and `tools/call` through the official Python MCP SDK.
- OAuth is handled by the MCP SDK using authorization-code + PKCE/discovery. Tokens and registered client information are persisted locally for the single-user reference deployment; refresh is automatic through `OAuthClientProvider`.
- Write operations require explicit `approve_write=true` by default.

## 1. Prerequisites

- Python 3.12+
- An OpenAI API key with billing/credits
- A Notion account/workspace

## 2. Install

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

On Windows, copy `.env.example` to `.env` manually if `cp` is unavailable.

Set:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5
```

## 3. Authorize the real Notion MCP

```bash
python scripts/notion_auth.py
```

The script prints an authorization URL. Open it, sign in to Notion, approve access, then paste the **full callback URL from the browser address bar** into the terminal. The localhost callback page itself does not need to render; the script only needs the authorization `code/state` in the redirected URL.

Credentials are stored under `.secrets/`, which is gitignored. Do not commit them.

## 4. Start

```bash
uvicorn app.main:app --reload
```

Swagger: `http://localhost:8000/docs`

Health: `GET http://localhost:8000/health`

## 5. Try real requests

### Search/read

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Search my Notion workspace for Partner Agent architecture and summarize what you find","thread_id":"demo-1","user_id":"user-1"}'
```

### Create page — first request is blocked for approval

```json
{
  "message": "Create a Notion page called Partner Agent Notes with a short explanation of MCP",
  "thread_id": "demo-2",
  "user_id": "user-1",
  "approve_write": false
}
```

Expected: `approval_required: true` and no write MCP call.

After the user confirms, send the same request with:

```json
"approve_write": true
```

Only then can the graph execute the discovered Notion write tool.

## Intent and routing design

The LLM returns a strict structured route:

```json
{
  "intent": "search_knowledge",
  "partner": "notion",
  "risk": "read",
  "objective": "Find Partner Agent architecture information",
  "requires_mcp": true
}
```

The graph—not the LLM—controls what happens next. This separation is intentional:

- **LLM:** semantic understanding and tool choice.
- **LangGraph:** deterministic workflow, gates and state transitions.
- **MCP:** standardized capability discovery/invocation.
- **Partner:** source of truth and authorization boundary.

## Key source files

```text
app/main.py                    FastAPI application
app/api/routes.py              REST API
app/models/schemas.py          request/response + intent DTOs
app/agent/state.py             LangGraph state
app/agent/graph.py             orchestration and safety gates
app/llm/openai_client.py       OpenAI Responses API
app/mcp/notion_client.py       real Notion MCP client
app/mcp/oauth_storage.py       OAuth token/client persistence
scripts/notion_auth.py         interactive OAuth bootstrap
```

## Production hardening notes

This repository is a **production-style reference**, but one important boundary is deliberate: its local OAuth store represents one operator/workspace. For a real multi-user enterprise deployment, replace `FileTokenStorage` with encrypted per-user storage (KMS/Key Vault + database), key it by authenticated application user, and implement the OAuth redirect/callback as real HTTPS application endpoints. Never share one employee's partner token across users.

Before internet-facing deployment also add your organization's SSO/JWT validation at FastAPI, tenant authorization, secrets manager, database-backed LangGraph checkpoints, distributed tracing, centralized logs, rate limiting, request quotas, network egress allowlists, MCP tool allowlists, audit storage, and confirmation/idempotency for writes. The graph already isolates the seams where those controls belong.

For production, **do not trust tool names alone** for authorization. Maintain a configured allowlist with explicit `READ`/`WRITE` metadata for each approved MCP tool. The name-based write detector in this reference is defense-in-depth/demo logic, not an enterprise policy engine.

## Conversation state

Every request includes a stable `thread_id`; LangGraph uses it as the checkpoint key. The included build uses `MemorySaver` so it runs with zero infrastructure. `DATABASE_URL` is reserved for replacing this with Postgres-backed checkpoints in a deployed environment.

A typical production deployment is:

```text
Load Balancer
   |
FastAPI replicas
   |
Partner Agent / LangGraph
   +---- OpenAI API
   +---- PostgreSQL checkpoints/audit
   +---- Secrets/KMS per-user OAuth tokens
   +---- Notion MCP (outbound HTTPS)
```

## Tests

```bash
pytest -q
```

The included tests cover DTO defaults and write-tool detection. In a real CI pipeline add mocked OpenAI/MCP contract tests plus a separate opt-in integration test against a non-sensitive Notion test workspace.

## Security decisions worth carrying to the real Partner Agent

1. User/tenant authentication happens before partner access.
2. Partner credentials are user-scoped, not global.
3. MCP tools are discovered but still filtered by application policy.
4. Read and write intents are separated.
5. Writes require explicit approval by default.
6. The final LLM response is grounded in returned MCP results.
7. Every request has `thread_id`, `user_id`, `trace_id`, intent and tool-call metadata suitable for audit/observability.
8. The partner system remains the source of truth.

## Suggested Notion test content

Create a few non-sensitive pages such as `Engineering Handbook`, `Partner Agent Architecture`, and `Laptop Policy`. Then test search, fetch, creation and updates. Do not connect this learning project to confidential company content.
