"""Repo-local MCP entrypoint shim.

The installed ``mts-mcp-server`` command uses
``mts_client_integration.tools.mcp_server``. This module re-exports the same
API for ``src/server.py:create_server`` (MCP Inspector) and
``python src/server.py``.
"""

from __future__ import annotations

from mts_client_integration.tools.mcp_server import create_server, main

__all__ = ["create_server", "main"]

if __name__ == "__main__":
    main()
