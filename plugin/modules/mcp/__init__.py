# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""MCP JSON-RPC protocol module.

Owns the HTTP server lifecycle and exposes tools via MCP streamable HTTP.
Supports custom filtered endpoints for smaller LLMs.
"""

import json
import logging

from plugin.framework.module_base import ModuleBase

log = logging.getLogger("libremcp.mcp")

PRESETS = {
    "writer-edit": [
        "list_open_documents",
        "get_document_info",
        "get_document_outline",
        "open_document",
        "create_document",
        "save_document",
        "close_document",
        "read_paragraphs",
        "get_heading_content",
        "find_text",
        "insert_at_paragraph",
        "insert_paragraphs_batch",
        "set_paragraph_text",
        "set_paragraph_style",
        "delete_paragraph",
        "duplicate_paragraph",
        "insert_image",
        "insert_hyperlink",
        "create_table",
        "write_table_cell",
        "execute_batch",
        "undo",
        "redo",
        "resolve_locator",
        "get_document_stats",
    ],
    "writer-read": [
        "list_open_documents",
        "get_document_info",
        "get_document_outline",
        "get_document_content",
        "read_paragraphs",
        "get_heading_content",
        "find_text",
        "search_in_document",
        "get_document_stats",
        "list_images",
        "list_tables",
        "list_comments",
        "resolve_locator",
        "get_document_tree",
    ],
    "calc": [
        "list_open_documents",
        "get_document_info",
        "open_document",
        "create_document",
        "save_document",
        "read_table",
        "write_table_cell",
        "write_table_row",
        "create_chart",
        "list_tables",
        "execute_batch",
        "undo",
        "redo",
    ],
    "minimal": [
        "list_open_documents",
        "get_document_info",
        "open_document",
        "create_document",
        "save_document",
        "read_paragraphs",
        "insert_at_paragraph",
        "insert_image",
    ],
}


def on_create_preset():
    """Create a custom endpoint from the selected preset."""
    from plugin.main import get_services
    from plugin.framework.dialogs import msgbox
    from plugin.framework.uno_context import get_ctx

    ctx = get_ctx()
    services = get_services()
    if not services:
        return

    cfg = services.config.proxy_for("mcp")
    preset_name = cfg.get("preset") or "minimal"

    if preset_name not in PRESETS:
        msgbox(ctx, "LibreMCP", "Unknown preset: %s" % preset_name)
        return

    tools_list = PRESETS[preset_name]
    tools_text = "\n".join(tools_list)

    raw = cfg.get("custom_endpoints") or "[]"
    try:
        items = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        items = []

    items.append(
        {
            "name": preset_name,
            "path": "/mcp/%s" % preset_name.replace("-", "/"),
            "tools": tools_text,
        }
    )
    cfg.set("custom_endpoints", json.dumps(items))
    msgbox(
        ctx,
        "LibreMCP",
        "Endpoint '/mcp/%s' created with %d tools.\n"
        "Reopen Options to see it." % (preset_name.replace("-", "/"), len(tools_list)),
    )


class MCPModule(ModuleBase):
    """Owns the HTTP server and exposes tools via MCP JSON-RPC routes."""

    def initialize(self, services):
        from plugin.framework.http_routes import HttpRouteRegistry

        self._services = services
        self._protocol = None
        self._routes_registered = False
        self._server = None

        # Create and register the HTTP route registry as a service
        self._registry = HttpRouteRegistry()
        services.register_instance("http_routes", self._registry)

        cfg = services.config.proxy_for(self.name)
        if cfg.get("enabled"):
            self._register_routes(services)

        if hasattr(services, "events"):
            services.events.subscribe("config:changed", self._on_config_changed)

    def start_background(self, services):
        cfg = services.config.proxy_for(self.name)
        if cfg.get("enabled"):
            self._start_server(services)

    def _on_config_changed(self, **data):
        key = data.get("key", "")
        if not key.startswith("mcp."):
            return
        cfg = self._services.config.proxy_for(self.name)
        enabled = cfg.get("enabled")

        # Toggle MCP routes
        if enabled and not self._routes_registered:
            self._register_routes(self._services)
        elif not enabled and self._routes_registered:
            self._unregister_routes(self._services)

        # Toggle server on/off
        if enabled and not self._server:
            self._start_server(self._services)
        elif not enabled and self._server:
            self._stop_server()

    def _register_routes(self, services):
        from plugin.modules.mcp.protocol import MCPProtocolHandler

        self._protocol = MCPProtocolHandler(services)
        routes = self._registry
        p = self._protocol

        # MCP streamable HTTP transport
        routes.add("POST", "/mcp", p.handle_mcp_post, raw=True)
        routes.add("GET", "/mcp", p.handle_mcp_sse, raw=True)
        routes.add("DELETE", "/mcp", p.handle_mcp_delete, raw=True)

        # Health / readiness probe
        routes.add("GET", "/health", p.handle_health, raw=True)

        self._routes_registered = True
        self._custom_routes = []
        log.info("MCP routes registered")

        # Register custom filtered endpoints
        self._register_custom_endpoints(services)

    def _register_custom_endpoints(self, services):
        """Register custom filtered MCP endpoints from config."""
        cfg = services.config.proxy_for(self.name)
        raw = cfg.get("custom_endpoints") or "[]"
        try:
            endpoints = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(endpoints, list):
            return

        routes = self._registry

        for ep in endpoints:
            name = ep.get("name", "")
            path = ep.get("path", "")
            if not path or not path.startswith("/mcp/"):
                continue
            if not ep.get("enabled", True):
                continue

            tools_text = ep.get("tools", "")
            tool_filter = set()
            for line in tools_text.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    tool_filter.add(line)

            if not tool_filter:
                continue

            from plugin.modules.mcp.protocol import MCPProtocolHandler

            handler = MCPProtocolHandler(services, tool_filter=tool_filter)

            routes.add("POST", path, handler.handle_mcp_post, raw=True)
            routes.add("GET", path, handler.handle_mcp_sse, raw=True)
            routes.add("DELETE", path, handler.handle_mcp_delete, raw=True)
            self._custom_routes.append(path)
            log.info(
                "Custom MCP endpoint: %s (%s, %d tools)", path, name, len(tool_filter)
            )

    def _unregister_routes(self, services):
        routes = self._registry
        for method, path in [
            ("POST", "/mcp"),
            ("GET", "/mcp"),
            ("DELETE", "/mcp"),
            ("GET", "/health"),
        ]:
            routes.remove(method, path)
        for path in getattr(self, "_custom_routes", []):
            for method in ("POST", "GET", "DELETE"):
                routes.remove(method, path)
        self._custom_routes = []
        self._routes_registered = False
        self._protocol = None
        log.info("MCP routes unregistered")

    def _start_server(self, services):
        from plugin.framework.http_server import HttpServer

        cfg = services.config.proxy_for(self.name)
        event_bus = getattr(services, "events", None)

        self._server = HttpServer(
            route_registry=self._registry,
            port=cfg.get("port") or 9876,
            host=cfg.get("host") or "localhost",
            use_ssl=cfg.get("use_ssl") or False,
            ssl_cert=cfg.get("ssl_cert") or "",
            ssl_key=cfg.get("ssl_key") or "",
        )
        try:
            self._server.start()
            if event_bus:
                status = self._server.get_status()
                event_bus.emit(
                    "http:server_started",
                    port=status["port"],
                    host=status["host"],
                    url=status["url"],
                )
                event_bus.emit("menu:update")
        except Exception:
            log.exception("Failed to start HTTP server")
            self._server = None

    def _stop_server(self):
        if self._server:
            self._server.stop()
            self._server = None
            event_bus = getattr(self._services, "events", None)
            if event_bus:
                event_bus.emit("http:server_stopped", reason="shutdown")
                event_bus.emit("menu:update")

    # ── Action dispatch ──────────────────────────────────────────────

    def on_action(self, action):
        if action == "toggle_server":
            self._action_toggle_server()
        elif action == "server_status":
            self._action_server_status()
        else:
            super().on_action(action)

    def get_menu_text(self, action):
        if action == "toggle_server":
            if self._server and self._server.is_running():
                return "Stop MCP Server"
            return "Start MCP Server"
        return None

    def get_menu_icon(self, action):
        running = self._server and self._server.is_running()
        if action == "toggle_server":
            return "stopped" if running else "running"
        if action == "server_status":
            return "running" if running else "stopped"
        return None

    def _action_toggle_server(self):
        from plugin.framework.dialogs import msgbox
        from plugin.framework.uno_context import get_ctx

        ctx = get_ctx()
        if self._server and self._server.is_running():
            log.info("Stopping MCP server via toggle")
            self._stop_server()
            msgbox(ctx, "LibreMCP", "MCP server stopped")
        else:
            log.info("Starting MCP server via toggle")
            self._start_server(self._services)
            if self._server and self._server.is_running():
                status = self._server.get_status()
                msgbox(
                    ctx, "LibreMCP", "MCP server started\n%s" % status.get("url", "")
                )
            else:
                msgbox(
                    ctx, "LibreMCP", "MCP server failed to start\nCheck ~/libremcp.log"
                )

    def _action_server_status(self):
        from plugin.framework.dialogs import msgbox
        from plugin.framework.uno_context import get_ctx

        ctx = get_ctx()
        if not self._server:
            msgbox(ctx, "LibreMCP", "MCP server is not running")
            return

        status = self._server.get_status()
        running = status.get("running", False)
        if not running:
            msgbox(ctx, "LibreMCP", "MCP server not running")
            return

        url = status.get("url", "?")
        routes = status.get("routes", 0)
        msgbox(
            ctx, "LibreMCP", "MCP server running\nURL: %s\nRoutes: %d" % (url, routes)
        )

    def shutdown(self):
        if self._routes_registered:
            try:
                self._unregister_routes(self._services)
            except Exception:
                log.exception("Error unregistering MCP routes")
        self._stop_server()
