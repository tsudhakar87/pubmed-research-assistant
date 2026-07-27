#!/bin/bash
# Start the BioNeMo MCP server
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
exec python mcp_servers/bionemo_server.py
