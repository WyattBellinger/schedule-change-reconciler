"""Typed MCP stdio server, matching NanoAgent's plugin protocol."""

import os
from pathlib import Path
from typing import Any

import anyio
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from slimconfig import build_output, output_schema, plain_output

from contract import TOOLS, Tool
from plugin import find_schedule_conflicts, normalize_interval, replay_schedule

server = Server("schedule-change-reconciler")
IMPLEMENTATIONS = {
    Tool.NORMALIZE_INTERVAL: normalize_interval,
    Tool.FIND_SCHEDULE_CONFLICTS: find_schedule_conflicts,
    Tool.REPLAY_SCHEDULE: replay_schedule,
}


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(name=tool.value, inputSchema=output_schema(given), outputSchema=output_schema(made))
        for tool, (given, made) in TOOLS.items()
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    tool = Tool(name)
    given, made = TOOLS[tool]
    output = IMPLEMENTATIONS[tool](build_output(arguments, given), Path(os.environ["NANOAGENT_WORKSPACE"]))
    if not isinstance(output, made):
        raise TypeError(f"{name} returned the wrong contract class")
    return plain_output(output)


def main() -> None:
    if "NANOAGENT_WORKSPACE" not in os.environ:
        raise SystemExit("NANOAGENT_WORKSPACE is not set: run this plugin through NanoAgent")
    if set(IMPLEMENTATIONS) != set(Tool):
        raise SystemExit("IMPLEMENTATIONS must cover every contract.Tool")

    async def run() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    anyio.run(run)


if __name__ == "__main__":
    main()
