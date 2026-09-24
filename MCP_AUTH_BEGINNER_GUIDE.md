# MCP and OAuth: A Beginner's Guide

This guide explains what MCP does, why Notion and Linear require authorization, what the authorization scripts do, and when you need to run them.

## The short answer

You normally authorize each partner only once:

```powershell
python -m scripts.partner_auth notion
python -m scripts.partner_auth linear
```

The credentials are saved locally. After that, you only need to start the application. The MCP client automatically uses the saved credentials and refreshes access tokens when possible.

You need to authorize again only when access was revoked, the refresh token stopped working, the `.secrets` directory was deleted, the OAuth client configuration changed, or you want to connect a different account or workspace.

## A simple analogy

Think of the application as a personal assistant that needs permission to enter different offices:

- Notion is one office.
- Linear is another office.
- MCP is the standard language the assistant uses inside each office.
- OAuth is the security desk that decides whether the assistant may enter.

OAuth grants access to an account. The application's write-approval gate separately decides whether a particular request may modify something.

## What is MCP?

MCP stands for **Model Context Protocol**. It gives AI applications a standard way to communicate with external services.

Using MCP, an application can:

1. Connect to an MCP server.
2. Ask which tools the server provides.
3. Learn the arguments required by each tool.
4. Call a selected tool.
5. Receive a structured result.

Linear might provide tools for listing, reading, creating, and updating issues. Notion might provide tools for searching, fetching, creating, and updating pages.

The application therefore does not need to implement every underlying Notion or Linear API operation itself. It uses the common MCP operations `initialize`, `tools/list`, and `tools/call`.

## Why is authorization required?

Notion and Linear workspaces contain private information. Their MCP servers need to know:

- Who is requesting access?
- Which workspace may they access?
- Did the user approve access?
- Which read and write permissions were granted?
- Was access later revoked?

Notion and Linear answer these questions through OAuth.

## What happens during authorization?

### 1. The application contacts the MCP server

The configured hosted servers are:

```text
Notion: https://mcp.notion.com/mcp
Linear: https://mcp.linear.app/mcp
```

The application asks the server how it can obtain authorization.

### 2. The application registers itself

These hosted servers support dynamic OAuth client registration. The application provides information such as its name and callback address:

```text
Application: Partner Agent
Callback: http://localhost:3030/callback
Requested permissions: read and write
```

The server returns client-registration information. The project stores it in files such as:

```text
.secrets/notion_mcp_client.json
.secrets/linear_mcp_client.json
```

This registration identifies the application. It is not the same as the user's authorization token.

### 3. The script prints an authorization URL

The authorization script prints a partner URL containing details such as:

- The registered client identifier
- The requested permissions
- The callback URL
- Security values used to prevent request interception and forgery

### 4. The user approves access

The user opens that URL and signs in directly to Notion or Linear. The password is entered on the partner's website, not into this Python application.

The partner displays a consent screen explaining the requested permissions. When the user approves, the partner records that consent.

### 5. The browser redirects to localhost

After approval, the browser redirects to a URL resembling:

```text
http://localhost:3030/callback?code=abc123&state=xyz
```

The callback page may fail to load because this project does not run a callback web server on port 3030. That is expected. Copy the complete URL from the browser address bar and paste it into the terminal.

Important values in this URL include:

- `code`: A short-lived, one-time authorization code
- `state`: A value proving that the callback belongs to the authorization request the application started

### 6. The code is exchanged for tokens

The application sends the one-time code to the partner. If it is valid, the partner returns an access token, usually a refresh token, and expiration information.

The authorization code cannot normally be reused.

### 7. Tokens are stored locally

The project saves partner tokens in:

```text
.secrets/notion_mcp_token.json
.secrets/linear_mcp_token.json
```

These files provide access to the connected workspaces and must remain private. The `.secrets/` directory is excluded from Git and must never be committed or shared.

## Access tokens and refresh tokens

An **access token** is like a temporary building pass. The application sends it to the MCP server with its requests.

Access tokens normally expire. Short-lived access limits the damage if a token is stolen.

A **refresh token** allows the application to request a replacement access token without making the user approve access again:

```text
Access token expires
        |
        v
Application sends refresh token
        |
        v
Partner returns a new access token
        |
        v
Original MCP request continues
```

If the refresh token is also rejected, the user must run the partner authorization script again.

## What happens when the application starts?

Starting FastAPI does not normally perform OAuth again. A typical request works like this:

```text
Start the application
        |
        v
User asks about Linear
        |
        v
Load the saved Linear token
        |
        v
Refresh it automatically if necessary
        |
        v
Call the Linear MCP server
```

If no usable authorization exists, the application reports that partner authorization is required.

## What happens when a user sends a message?

For example:

> Create a Linear issue called "Fix login timeout."

The workflow is:

```text
User message
    |
    v
OpenAI classifies the request
    |
    +-- Partner: Linear
    +-- Intent: create
    +-- Risk: write
    |
    v
Load the Linear MCP client
    |
    v
Discover Linear's available tools
    |
    v
Select the appropriate issue-creation tool
    |
    v
Stop and request write approval
    |
    v
User approves
    |
    v
Call the Linear MCP tool
    |
    v
Return a response grounded in the tool result
```

A Notion request follows the same workflow but selects the Notion client and uses the Notion credentials. Credentials from an unrelated partner are not sent.

## OAuth consent and write approval are different

OAuth consent answers:

> May this application access my partner account?

The user normally provides this consent once in the browser.

The write-approval gate answers:

> May this particular request create or modify something?

When write approval is enabled, the graph asks this for every write request. OAuth may give the application the technical ability to write, but the graph still prevents the tool call until the specific operation is approved.

## Do all MCP servers use OAuth?

No. MCP standardizes communication, but individual servers choose how authentication works.

### Hosted MCP with OAuth

Notion and Linear use this approach:

```text
Browser login -> consent -> access token -> refresh token
```

This is the type best supported by the current reusable remote MCP client.

### API key or personal access token

Some servers require a token created manually in the service's settings:

```env
PARTNER_API_KEY=...
```

These integrations may not use a browser or refresh tokens.

### No authentication

A public MCP server may expose non-private information without requiring credentials.

### Local MCP server

A local MCP server can run as a subprocess on the user's computer:

```text
Application -> local MCP process -> local files or tools
```

Local servers often use the `stdio` transport instead of a remote HTTP URL. Adding one to this project would require a local-transport client behind the same partner interface.

### Enterprise authentication

Enterprise MCP servers may use service accounts, managed identities, organization-controlled SSO, signed JWTs, or client certificates. These servers need specialized authentication adapters.

## How the project supports additional partners

The common workflow is separate from partner configuration:

```text
Shared workflow
|-- Classify the request
|-- Select a partner
|-- Discover tools
|-- Plan tool calls
|-- Require write approval
|-- Execute tools
`-- Generate the answer

Partner registry
|-- Notion configuration
|-- Linear configuration
`-- Future partner configuration
```

Partner definitions are located in `app/mcp/partners.py`. The reusable hosted MCP client is located in `app/mcp/remote_client.py`.

Adding another hosted OAuth MCP partner normally requires:

1. A partner registry entry
2. An MCP server URL setting
3. A token-file setting
4. A specialized OAuth provider only if the server requires different behavior
5. Routing guidance and tests for the new partner's domain

An API-key server or local `stdio` server would use a different client adapter while still fitting behind the same registry interface.

## When should the authorization scripts be run again?

Run a partner authorization script again when:

- The partner reports that authorization is required
- Access was revoked in the partner's settings
- The access token and refresh token are no longer accepted
- The `.secrets` directory or token file was deleted
- OAuth registration or callback configuration changed
- A different account or workspace needs to be connected

Do not run the scripts every time the application starts.

## Current single-user limitation

This repository is a local, single-operator reference implementation. Although chat requests contain a `user_id`, that identifier does not select different partner credentials.

Currently, every local application user shares:

```text
One Notion token file
One Linear token file
```

A production multi-user system should store credentials by organization, authenticated application user, partner, and workspace:

```text
user-123 / notion / workspace-A
user-123 / linear / workspace-B
user-456 / notion / workspace-C
```

Those credentials should be encrypted in a database or secrets manager, with appropriate key management, tenant isolation, rotation, auditing, and revocation controls. They should not be ordinary shared files on the application server.

## Security checklist

- Never commit or share `.secrets/`.
- Never print access or refresh tokens in logs.
- Use the minimum partner permissions required.
- Keep write approval enabled for state-changing tools.
- Treat token files like passwords.
- Revoke partner access immediately if credentials may have leaked.
- Use encrypted, per-user credential storage in production.
- Authenticate application users before allowing them to access partner data.
- Maintain explicit read/write tool policies instead of trusting tool names alone.
