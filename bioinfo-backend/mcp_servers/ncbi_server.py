"""
NCBI MCP Server

This MCP server provides tools for interacting with NCBI's PubMed database.

Tools exposed:
- search_pubmed: Search for articles in PubMed
- fetch_article_details: Get full details for specific PubMed IDs
- get_recent_articles: Get recently published articles for a topic

MCP (Model Context Protocol) is Anthropic's protocol that allows AI assistants
to connect to external data sources. This server acts as a bridge between
Claude and the NCBI E-utilities API.
"""

import asyncio
import json
import os
import sys
from typing import Any
from datetime import datetime, timedelta

# Add parent directory to path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp import types

from src.external import NCBIClient, PubMedArticle
from src.config.settings import settings


# Initialize the MCP server
# A server is a process that exposes tools and data to AI assistants
server = Server("ncbi-research-server")


# Helper function to convert PubMedArticle to dictionary
def article_to_dict(article: PubMedArticle) -> dict:
    """Convert PubMedArticle dataclass to JSON-serializable dict"""
    return {
        "pmid": article.pmid,
        "title": article.title,
        "abstract": article.abstract,
        "authors": article.authors,
        "journal": article.journal,
        "publication_date": article.publication_date.isoformat() if article.publication_date else None,
        "doi": article.doi,
        "keywords": article.keywords,
    }


# ============================================================================
# TOOL DEFINITIONS
# Tools are functions that Claude can call. Each tool needs:
# 1. A @server.list_tools() handler to register it
# 2. A @server.call_tool() handler to execute it
# ============================================================================

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List all available tools.

    This is called by Claude to discover what tools are available.
    Each tool has a name, description, and input schema (JSON Schema).
    """
    return [
        types.Tool(
            name="search_pubmed",
            description="""
                Search PubMed for scientific articles and literature.

                This tool queries NCBI's PubMed database and returns matching articles
                with their metadata (title, abstract, authors, journal, etc.).

                Use this when you need to:
                - Find research papers on a specific topic
                - Look up literature for a biological question
                - Get recent publications in a field

                The query uses PubMed's search syntax. Examples:
                - "CRISPR gene editing"
                - "cancer AND immunotherapy"
                - "COVID-19[Title]"
                - "Nature[Journal]"
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "PubMed search query (supports PubMed search syntax)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 20, max: 100)",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "sort": {
                        "type": "string",
                        "description": "Sort order: 'relevance' or 'pub_date'",
                        "enum": ["relevance", "pub_date"],
                        "default": "relevance",
                    },
                    "min_date": {
                        "type": "string",
                        "description": "Minimum publication date (YYYY, YYYY/MM, or YYYY/MM/DD)",
                    },
                    "max_date": {
                        "type": "string",
                        "description": "Maximum publication date (YYYY, YYYY/MM, or YYYY/MM/DD)",
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="fetch_article_details",
            description="""
                Fetch full details for specific PubMed articles by their PMIDs.

                Use this when you have PubMed IDs and need complete article information
                including abstracts, author lists, keywords, and publication metadata.

                PMIDs are unique identifiers for articles (e.g., "12345678").
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "pmids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of PubMed IDs to fetch",
                        "minItems": 1,
                        "maxItems": 50,
                    },
                },
                "required": ["pmids"],
            },
        ),
        types.Tool(
            name="get_recent_articles",
            description="""
                Get recently published articles on a topic.

                This is a convenience tool that searches PubMed for articles
                published within the last N days, sorted by publication date.

                Useful for staying up-to-date with latest research in a field.
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Research topic or search query",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back (default: 30)",
                        "default": 30,
                        "minimum": 1,
                        "maximum": 365,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 10)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
                "required": ["topic"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Execute a tool call.

    This is called when Claude wants to use one of our tools.
    We receive the tool name and arguments, execute the logic,
    and return the results.
    """

    # Initialize NCBI client with credentials from settings
    async with NCBIClient(
        email=settings.ncbi_email,
        api_key=settings.ncbi_api_key,
        tool_name=settings.ncbi_tool_name
    ) as client:

        if name == "search_pubmed":
            # Extract arguments with defaults
            query = arguments["query"]
            max_results = arguments.get("max_results", 20)
            sort = arguments.get("sort", "relevance")
            min_date = arguments.get("min_date")
            max_date = arguments.get("max_date")

            # Perform the search
            articles = await client.search_and_fetch(
                query=query,
                max_results=max_results,
                sort=sort,
                min_date=min_date,
                max_date=max_date,
            )

            # Convert articles to JSON-serializable format
            results = {
                "query": query,
                "total_results": len(articles),
                "articles": [article_to_dict(article) for article in articles],
            }

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(results, indent=2),
                )
            ]

        elif name == "fetch_article_details":
            pmids = arguments["pmids"]

            # Fetch articles by PMID
            articles = await client.fetch_articles(pmids)

            results = {
                "requested_pmids": pmids,
                "found": len(articles),
                "articles": [article_to_dict(article) for article in articles],
            }

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(results, indent=2),
                )
            ]

        elif name == "get_recent_articles":
            topic = arguments["topic"]
            days = arguments.get("days", 30)
            max_results = arguments.get("max_results", 10)

            # Calculate date range
            max_date = datetime.now()
            min_date = max_date - timedelta(days=days)

            # Format dates for NCBI (YYYY/MM/DD)
            max_date_str = max_date.strftime("%Y/%m/%d")
            min_date_str = min_date.strftime("%Y/%m/%d")

            # Search with date filters
            articles = await client.search_and_fetch(
                query=topic,
                max_results=max_results,
                sort="pub_date",
                min_date=min_date_str,
                max_date=max_date_str,
            )

            results = {
                "topic": topic,
                "date_range": {
                    "from": min_date_str,
                    "to": max_date_str,
                },
                "total_results": len(articles),
                "articles": [article_to_dict(article) for article in articles],
            }

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(results, indent=2),
                )
            ]

        else:
            raise ValueError(f"Unknown tool: {name}")


# ============================================================================
# SERVER ENTRY POINT
# ============================================================================

async def main():
    """
    Main entry point for the MCP server.

    This runs the server using stdio (standard input/output) transport,
    which means Claude communicates with this server via stdin/stdout.
    """

    # Run the server using stdio transport
    # This allows Claude to communicate with the server via stdin/stdout
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ncbi-research-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    """
    When this script is run directly, start the MCP server.

    Usage:
        python mcp_servers/ncbi_server.py

    The server will run in the foreground and communicate via stdio.
    """
    asyncio.run(main())
