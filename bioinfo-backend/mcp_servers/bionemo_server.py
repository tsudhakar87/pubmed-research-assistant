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
import base64
import io
import json
import os
import sys
from typing import Any

import httpx
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp import types

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
# Evo2 NIM has no direct "/score" endpoint — only /generate and /forward.
# Variant effect is the delta in teacher-forced log-likelihood between the
# wildtype and mutant nucleotide sequence, computed from /forward logits.
EVO2_FORWARD_URL = "https://health.api.nvidia.com/v1/biology/arc/evo2-40b/forward"

server = Server("bionemo-server")


async def _evo2_log_likelihood(client: httpx.AsyncClient, sequence: str) -> float:
    """Teacher-forced log-likelihood of `sequence` under Evo2's byte-level tokenizer."""
    resp = await client.post(
        EVO2_FORWARD_URL,
        json={"sequence": sequence, "output_layers": ["unembed"]},
        headers={
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    resp.raise_for_status()
    raw = base64.b64decode(resp.json()["data"])
    npz = np.load(io.BytesIO(raw))
    logits = npz["unembed.output"][0]

    log_probs = logits - np.logaddexp.reduce(logits, axis=-1, keepdims=True)
    token_ids = [ord(c) for c in sequence]
    return float(sum(log_probs[i, token_ids[i + 1]] for i in range(len(sequence) - 1)))


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="score_variant",
            description=(
                "Score a genetic variant's predicted effect using BioNeMo Evo2-40b (NVIDIA NIM). "
                "Requires the actual wildtype and mutant nucleotide sequence around the variant — "
                "protein notation like 'V600E' alone is not sufficient input for this nucleotide-level "
                "model. Returns the delta in teacher-forced log-likelihood and a classification "
                "(disruptive / moderate / neutral)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "variant": {
                        "type": "string",
                        "description": "Variant notation for labeling, e.g. 'V600E' or 'c.1799T>A'",
                    },
                    "gene": {
                        "type": "string",
                        "description": "Gene symbol, e.g. 'BRAF' (optional, for labeling only)",
                    },
                    "ref_sequence": {
                        "type": "string",
                        "description": "Wildtype nucleotide sequence around the variant (ACGT)",
                    },
                    "alt_sequence": {
                        "type": "string",
                        "description": "Mutant nucleotide sequence around the variant (ACGT), same length as ref_sequence",
                    },
                },
                "required": ["variant", "ref_sequence", "alt_sequence"],
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
    ref_sequence = args.get("ref_sequence", "")
    alt_sequence = args.get("alt_sequence", "")

    if not NVIDIA_API_KEY:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": "NVIDIA_API_KEY not set — cannot call BioNeMo NIM"}),
        )]

    if not ref_sequence or not alt_sequence:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "ref_sequence and alt_sequence are required — variant notation "
                         "alone cannot be scored by a nucleotide-level model",
                "variant": variant,
            }),
        )]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            ref_ll, alt_ll = await asyncio.gather(
                _evo2_log_likelihood(client, ref_sequence),
                _evo2_log_likelihood(client, alt_sequence),
            )

        delta = alt_ll - ref_ll
        classification = (
            "disruptive" if delta <= -1.0
            else ("neutral" if delta >= -0.1 else "moderate")
        )

        output = {
            "variant": variant,
            "gene": gene,
            "delta_log_likelihood": round(delta, 4),
            "ref_log_likelihood": round(ref_ll, 4),
            "alt_log_likelihood": round(alt_ll, 4),
            "classification": classification,
            "model": "evo2-40b",
            "source": "BioNeMo NIM (forward-pass log-likelihood)",
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
