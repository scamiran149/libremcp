# Connect ChatGPT to LibreOffice via Tailscale

This guide explains how to expose your LibreMCP server to the internet using Tailscale Funnel, so that ChatGPT (or any remote MCP client) can control your LibreOffice documents.

## Prerequisites

- LibreMCP installed in LibreOffice
- A Tailscale account (free tier works)

## Step 1 — Install Tailscale

Download and install Tailscale from https://tailscale.com/download

Then log in:

```
tailscale login
```

Enable Funnel (allows public HTTPS access to your machine):

```
tailscale funnel on
```

## Step 2 — Configure LibreMCP

Open **Tools > Options > LibreMCP**.

### HTTP Server

Go to the **HTTP** page and verify:

- **Enabled**: checked
- **Port**: 8766 (default)
- **Host**: localhost

You do not need to enable SSL — Tailscale Funnel handles HTTPS termination automatically.

### Tunnel

Go to the **Tunnel** page:

- **Provider**: select **Tailscale**
- **Auto Start**: check this if you want the tunnel to start every time LibreOffice opens

### MCP

Go to the **MCP** page:

- **Enabled**: checked
- Choose a **Preset** appropriate for your use case (e.g. `writer-edit` for full Writer editing)

## Step 3 — Start the tunnel

From the menu: **Tools > LibreMCP > Tunnel > Start Tunnel**

The status bar will show the tunnel URL once connected. You can also check it via **Tools > LibreMCP > Tunnel > Tunnel Status**.

The URL looks like: `https://your-machine.tail1234.ts.net`

## Step 4 — Connect ChatGPT

In ChatGPT, configure a Custom GPT or use the API with:

- **MCP endpoint**: `https://your-machine.tail1234.ts.net/mcp`
- **SSE endpoint**: `https://your-machine.tail1234.ts.net/sse` (for streaming)

The MCP endpoint accepts JSON-RPC requests. The SSE endpoint provides Server-Sent Events for real-time streaming.

## Step 5 — Test

Ask ChatGPT to list open documents:

> "List the documents currently open in LibreOffice"

If it returns document names, the connection is working.

## Custom Endpoints

If you want to expose only a subset of tools (recommended for ChatGPT which has a limited tool window), create a custom endpoint in **Options > LibreMCP > MCP**:

1. Click **Add** in Custom Endpoints
2. Give it a name (e.g. "chatgpt")
3. Set the path (e.g. "/chatgpt")
4. List only the tools you need in the textarea

The endpoint will be available at `https://your-machine.tail1234.ts.net/chatgpt/mcp`.

## Troubleshooting

- **Tunnel won't start**: Make sure `tailscale funnel on` was run and that Tailscale is connected
- **ChatGPT can't reach the URL**: Funnel can take a few seconds to propagate. Check `tailscale funnel status`
- **Tools not showing**: Verify MCP is enabled and the preset includes the tools you need
