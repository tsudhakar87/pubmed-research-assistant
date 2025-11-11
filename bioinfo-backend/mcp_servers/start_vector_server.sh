#!/bin/bash

# Startup script for Vector/Embedding MCP Server

# Exit on error
set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Starting Vector/Embedding MCP Server..." >&2
echo "Project root: $PROJECT_ROOT" >&2

# Check if virtual environment exists
VENV_PATH="/Users/thillainayakisudhakar/pubmed-research-assistant/bioinfo-backend/.bioinfo-venv"
if [ -d "$VENV_PATH" ]; then
    echo "Activating virtual environment at $VENV_PATH..." >&2
    source "$VENV_PATH/bin/activate"
elif [ -d "$PROJECT_ROOT/../.bioinfo-venv" ]; then
    echo "Activating virtual environment..." >&2
    source "$PROJECT_ROOT/../.bioinfo-venv/bin/activate"
elif [ -d "$PROJECT_ROOT/venv" ]; then
    echo "Activating virtual environment..." >&2
    source "$PROJECT_ROOT/venv/bin/activate"
else
    echo "Warning: No virtual environment found. Using system Python." >&2
fi

# Check if .env file exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "Warning: .env file not found. Make sure PROJECT_ID is set." >&2
    echo "You can create a .env file with:" >&2
    echo "  PROJECT_ID=your-gcp-project-id" >&2
fi

# Run the server
cd "$PROJECT_ROOT"
exec python mcp_servers/vector_server.py
