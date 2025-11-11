# MCP Servers for Bioinformatics Research Assistant

This directory contains MCP (Model Context Protocol) servers that expose various bioinformatics tools and APIs to AI assistants like Claude.

## What is MCP?

**MCP (Model Context Protocol)** is Anthropic's open protocol that allows AI assistants to securely connect to external data sources and tools. Think of MCP servers as "plugins" that give Claude new capabilities.

An MCP server can expose:
- **Tools**: Functions Claude can call (like searching PubMed)
- **Resources**: Data Claude can read (like cached articles)
- **Prompts**: Pre-defined templates for common tasks

## Available Servers

### 1. NCBI Server (`ncbi_server.py`)

Provides access to NCBI's PubMed database for scientific literature searches.

**Tools:**
- `search_pubmed`: Search for articles in PubMed
- `fetch_article_details`: Get full details for specific PubMed IDs
- `get_recent_articles`: Get recently published articles on a topic

**Configuration Required:**
- `NCBI_EMAIL`: Your email (required by NCBI)
- `NCBI_API_KEY`: Optional API key for higher rate limits

### 2. Vector Server (`vector_server.py`)

Provides semantic search and vector embeddings using ChromaDB and Google Vertex AI.

**Tools:**
- `semantic_search`: Find similar documents by meaning (not just keywords)
- `add_documents`: Add documents to the vector store for semantic search
- `get_embeddings`: Generate AI embeddings for text
- `search_similar_articles`: Find articles similar to a given article

**Configuration Required:**
- `PROJECT_ID`: Google Cloud Project ID (for Vertex AI embeddings)
- Google Cloud credentials configured

**What is it?**
Think of it as "Google for concepts" - it finds articles that are semantically similar, even if they use different words. For example, searching for "gene modification" will also find "CRISPR editing" because they mean similar things.

### 3. Analytics Server (`analytics_server.py`)

Provides data analysis and BigQuery analytics for research trends.

**Tools:**
- `analyze_research_trends`: Analyze publication trends over time
- `generate_statistics`: Generate statistical summaries (mean, median, counts, etc.)
- `compare_topics`: Compare metrics between different research topics
- `query_bigquery`: Execute SQL queries on BigQuery for large-scale analytics

**Configuration Required:**
- `PROJECT_ID`: Google Cloud Project ID (for BigQuery)
- Google Cloud credentials configured
- BigQuery dataset set up (optional, for query_bigquery tool)

**What is it?**
This is your data science assistant - it analyzes patterns in research data, tracks trends over time, compares different topics, and can query massive datasets.

## Setup Instructions

### 1. Install Dependencies

The MCP dependencies are already in `requirements.txt`:
```bash
pip install mcp mcp-server mcp-tools
```

### 2. Configure Environment Variables

Create or update your `.env` file in the project root:
```bash
# Required for NCBI server
NCBI_EMAIL=your-email@example.com

# Optional - get higher rate limits from NCBI
NCBI_API_KEY=your-api-key-here
```

You can get an NCBI API key here: https://www.ncbi.nlm.nih.gov/account/settings/

### 3. Test the Server Manually

You can test the server standalone:
```bash
# Make the startup script executable
chmod +x mcp_servers/start_ncbi_server.sh

# Run the server (it will listen on stdin/stdout)
./mcp_servers/start_ncbi_server.sh
```

The server will run and wait for MCP protocol messages on stdin.

### 4. Configure Claude Desktop (or other MCP client)

To use this with Claude Desktop, add the server configuration to your Claude config file.

**Location of Claude Desktop config:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%/Claude/claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

**Add this to the config:**
```json
{
  "mcpServers": {
    "ncbi-research": {
      "command": "bash",
      "args": [
        "/full/path/to/bioinfo-backend/mcp_servers/start_ncbi_server.sh"
      ],
      "env": {
        "NCBI_EMAIL": "your-email@example.com",
        "NCBI_API_KEY": "optional-api-key"
      }
    }
  }
}
```

**Important:** Replace `/full/path/to/` with the actual absolute path to your project!

### 5. Restart Claude Desktop

After updating the config, restart Claude Desktop. The NCBI server will now be available as a tool.

## Using the Server

Once configured, you can ask Claude things like:

- "Search PubMed for recent articles on CRISPR gene editing"
- "Find papers about cancer immunotherapy from the last 30 days"
- "Get details for PubMed ID 12345678"

Claude will automatically use the `search_pubmed`, `fetch_article_details`, or `get_recent_articles` tools from your MCP server.

## How It Works

### Architecture

```
┌─────────────────┐
│  Claude Desktop │
│   (MCP Client)  │
└────────┬────────┘
         │ JSON-RPC over stdio
         │
┌────────▼────────┐
│   MCP Server    │ ← ncbi_server.py
│  (This Code)    │
└────────┬────────┘
         │ HTTP/REST
         │
┌────────▼────────┐
│  NCBI E-utils   │
│  PubMed API     │
└─────────────────┘
```

### Communication Flow

1. **Tool Discovery**: Claude calls the server to discover available tools
2. **Tool Execution**: When you ask Claude to search PubMed, it calls the `search_pubmed` tool
3. **API Request**: The server forwards the request to NCBI's API
4. **Response**: The server formats the response and sends it back to Claude
5. **Claude's Response**: Claude processes the data and presents it to you

### Code Structure

The MCP server has three main parts:

1. **Tool Registration** (`@server.list_tools()`):
   - Tells Claude what tools are available
   - Defines the input schema (what parameters each tool accepts)

2. **Tool Execution** (`@server.call_tool()`):
   - Executes the actual logic when a tool is called
   - Makes API calls to NCBI
   - Returns formatted results

3. **Server Entry Point** (`main()`):
   - Sets up stdio transport
   - Runs the server event loop

## Troubleshooting

### Server won't start
- Check that your virtual environment is activated
- Verify `NCBI_EMAIL` is set in `.env` or environment
- Check the path in `start_ncbi_server.sh` points to the correct location

### Claude can't see the server
- Verify the path in `claude_desktop_config.json` is absolute (not relative)
- Make sure you restarted Claude Desktop after updating config
- Check Claude Desktop logs (Help → Show Logs)

### NCBI API errors
- Verify your email is valid
- If you're hitting rate limits, add an API key
- Check your internet connection

## Development

### Adding a New Tool

To add a new tool to the NCBI server:

1. Add the tool definition in `handle_list_tools()`:
```python
types.Tool(
    name="my_new_tool",
    description="What this tool does",
    inputSchema={
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "..."},
        },
        "required": ["param1"],
    },
)
```

2. Add the handler in `handle_call_tool()`:
```python
elif name == "my_new_tool":
    param1 = arguments["param1"]
    # Your logic here
    result = do_something(param1)
    return [types.TextContent(type="text", text=json.dumps(result))]
```

3. Test the tool and restart the server

## Resources

- [MCP Documentation](https://modelcontextprotocol.io)
- [NCBI E-utilities API](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
- [PubMed Search Syntax](https://pubmed.ncbi.nlm.nih.gov/help/)
