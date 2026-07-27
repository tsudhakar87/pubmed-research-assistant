"""
BioNeMo MCP Server

Exposes one tool to Claude Desktop:
  score_variant — score a genetic variant using NVIDIA BioNeMo Evo2-40b NIM

Usage (add to claude_desktop_config.json):
  {
    "bionemo": {
      "command": "bash",
      "args": ["bioinfo-backend/mcp_servers/start_bionemo_server.sh"]
    }
  }
"""
import asyncio
import json
import os
import sys
from typing import Any

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp import types

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
EVO2_URL = "https://health.api.nvidia.com/v1/biology/arc/evo2-40b/score"

server = Server("bionemo-server")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="score_variant",
            description=(
                "Score a genetic variant using BioNeMo Evo2-40b (NVIDIA NIM). "
                "Provide the variant in HGVS or protein notation (e.g. V600E, c.1799T>A). "
                "Returns a Δ-likelihood score and a classification (disruptive / moderate / neutral)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "variant": {
                        "type": "string",
                        "description": "Variant notation, e.g. 'V600E' or 'c.1799T>A'",
                    },
                    "gene": {
                        "type": "string",
                        "description": "Gene symbol, e.g. 'BRAF' (optional but improves accuracy)",
                    },
                    "sequence_context": {
                        "type": "string",
                        "description": "Optional surrounding nucleotide sequence if known",
                    },
                },
                "required": ["variant"],
            },
        ),
        types.Tool(
            name="detect_variants_in_text",
            description=(
                "Scan a block of text (e.g. a PubMed abstract) for genetic variant mentions "
                "using HGVS patterns, protein shorthand (V600E), and dbSNP IDs. "
                "Returns a list of detected variants with type classification."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The abstract or text to scan for variant mentions",
                    }
                },
                "required": ["text"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:

    if name == "score_variant":
        return await _score_variant(arguments)
    elif name == "detect_variants_in_text":
        return await _detect_variants(arguments)
    else:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def _score_variant(args: dict) -> list[types.TextContent]:
    variant = args.get("variant", "")
    gene = args.get("gene")
    seq_context = args.get("sequence_context")

    if not NVIDIA_API_KEY:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": "NVIDIA_API_KEY not set — cannot call BioNeMo NIM"}),
        )]

    payload: dict[str, Any] = {"variant": variant, "model": "evo2-40b"}
    if gene:
        payload["gene"] = gene
    if seq_context:
        payload["sequence_context"] = seq_context

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                EVO2_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {NVIDIA_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            result = resp.json()

        score: float = result.get("score", result.get("delta_likelihood", 0.0))
        classification = (
            "disruptive" if score >= 0.7
            else ("neutral" if score <= 0.3 else "moderate")
        )

        output = {
            "variant": variant,
            "gene": gene,
            "score": round(score, 3),
            "classification": classification,
            "sequence_context": result.get("sequence_context"),
            "model": "evo2-40b",
            "source": "BioNeMo NIM",
        }
    except httpx.TimeoutException:
        output = {"error": "BioNeMo Evo2 timed out (>30s)", "variant": variant}
    except httpx.HTTPStatusError as e:
        output = {"error": f"BioNeMo HTTP {e.response.status_code}", "variant": variant}
    except Exception as e:
        output = {"error": str(e), "variant": variant}

    return [types.TextContent(type="text", text=json.dumps(output, indent=2))]


async def _detect_variants(args: dict) -> list[types.TextContent]:
    # Import here to avoid circular imports when run standalone
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    try:
        from utils.variant_detection import detect_variants
        variants = detect_variants(args.get("text", ""))
    except ImportError:
        # Fallback minimal detection if module not importable
        import re
        pattern = re.compile(r"\b([A-Z])(\d{1,6})([A-Z])\b")
        variants = [
            {"notation": m.group(0), "type": "protein_short"}
            for m in pattern.finditer(args.get("text", ""))
        ]

    return [types.TextContent(type="text", text=json.dumps(variants, indent=2))]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="bionemo-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
