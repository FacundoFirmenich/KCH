"""KCH 0.11 MCP surface with corrected semantic field schemas."""

from __future__ import annotations

from . import mcp_server_base as _base

_base.FIELD_SCHEMAS.update(
    {
        "deliverables": _base.ARRAY,
        "cost_receipt": _base.OBJECT,
        "genealogy": _base.ARRAY,
    }
)
_base.TOOLS = tuple(
    _base.BASE_TOOLS
    + [_base.control_tool(control_id) for control_id in sorted(_base.CONTROL_CATALOG)]
)

SERVER_NAME = _base.SERVER_NAME
SERVER_VERSION = _base.SERVER_VERSION
PROTOCOL_VERSION = _base.PROTOCOL_VERSION
TOOLS = _base.TOOLS
RESOURCES = _base.RESOURCES
MCPServer = _base.MCPServer
default_registry = _base.default_registry
build_gateway = _base.build_gateway
main = _base.main

__all__ = [
    "MCPServer",
    "PROTOCOL_VERSION",
    "RESOURCES",
    "SERVER_NAME",
    "SERVER_VERSION",
    "TOOLS",
    "build_gateway",
    "default_registry",
    "main",
]


if __name__ == "__main__":
    main()
