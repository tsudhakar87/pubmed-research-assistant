"""
Vector & Embedding MCP Server

This MCP server provides semantic search and vector similarity tools
using embeddings and ChromaDB vector store.

Tools exposed:
- semantic_search: Search for similar documents using semantic meaning
- add_documents: Add documents to the vector store
- search_similar_articles: Find similar PubMed articles
- get_embeddings: Generate embeddings for text

EXPLANATION:
Vector embeddings are numerical representations of text that capture semantic meaning.
Similar concepts have similar vector representations, allowing "semantic search" -
searching by meaning rather than just keyword matching.

For example:
- "CRISPR gene editing" and "genome modification technology" are semantically similar
- Their embeddings would be close in vector space
- Traditional keyword search would miss this connection
"""

import asyncio
import json
import os
import sys
from typing import Any, List, Dict, Optional
from datetime import datetime
import hashlib

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp import types

# Import vector/embedding dependencies
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

try:
    import vertexai
    from vertexai.language_models import TextEmbeddingModel
    VERTEX_AVAILABLE = True
except ImportError:
    VERTEX_AVAILABLE = False

from src.config.settings import settings


# Initialize the MCP server
server = Server("vector-embedding-server")


class VectorStore:
    """
    Manages vector storage and retrieval using ChromaDB.

    ChromaDB is a vector database that stores embeddings and enables
    fast similarity search. Think of it as a specialized database
    for finding "similar" items based on their semantic meaning.
    """

    def __init__(self):
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB not installed. Run: pip install chromadb")

        # Initialize ChromaDB client (persistent storage)
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'chroma')
        os.makedirs(data_dir, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=data_dir,
            settings=ChromaSettings(anonymized_telemetry=False)
        )

        # Get or create collection for PubMed articles
        self.collection = self.client.get_or_create_collection(
            name="pubmed_articles",
            metadata={"description": "PubMed article embeddings"}
        )

    def add_documents(
        self,
        texts: List[str],
        metadatas: List[Dict],
        embeddings: List[List[float]],
        ids: Optional[List[str]] = None
    ):
        """Add documents with embeddings to the vector store"""
        if ids is None:
            # Generate IDs from content hash
            ids = [hashlib.md5(text.encode()).hexdigest() for text in texts]

        self.collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

    def search(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        where: Optional[Dict] = None
    ) -> Dict:
        """Search for similar documents using embedding"""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where
        )

        return {
            "documents": results["documents"][0] if results["documents"] else [],
            "distances": results["distances"][0] if results["distances"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else [],
            "ids": results["ids"][0] if results["ids"] else [],
        }


class EmbeddingService:
    """
    Generates text embeddings using Google's Vertex AI.

    Embeddings are dense vector representations of text (e.g., 768 dimensions).
    The model is trained so that semantically similar texts have similar embeddings.
    """

    def __init__(self):
        if not VERTEX_AVAILABLE:
            raise ImportError("Vertex AI not installed. Run: pip install google-cloud-aiplatform")

        # Initialize Vertex AI
        vertexai.init(
            project=settings.project_id,
            location=settings.region
        )

        # Use Vertex AI's text embedding model
        # This model converts text into 768-dimensional vectors
        self.model = TextEmbeddingModel.from_pretrained("textembedding-gecko@003")

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (each is a list of floats)
        """
        # Vertex AI embedding is sync, run in executor for async
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: self.model.get_embeddings(texts)
        )

        # Extract the values (embeddings is a list of TextEmbedding objects)
        return [emb.values for emb in embeddings]


# Initialize services (lazy loading)
_vector_store: Optional[VectorStore] = None
_embedding_service: Optional[EmbeddingService] = None


def get_vector_store() -> VectorStore:
    """Get or create vector store instance"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def get_embedding_service() -> EmbeddingService:
    """Get or create embedding service instance"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


# ============================================================================
# TOOL DEFINITIONS
# ============================================================================

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List all available vector/embedding tools"""
    return [
        types.Tool(
            name="semantic_search",
            description="""
                Perform semantic search to find similar documents.

                This uses AI embeddings to understand meaning, not just keywords.
                For example, searching "gene modification" will also find documents
                about "CRISPR editing" because they're semantically similar.

                Use this when you want to find conceptually related content,
                even if the exact keywords don't match.
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query or question",
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of results to return (default: 10)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50,
                    },
                    "filter": {
                        "type": "object",
                        "description": "Optional metadata filters (e.g., {'journal': 'Nature'})",
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="add_documents",
            description="""
                Add documents to the vector store for future semantic search.

                This generates embeddings for the documents and stores them,
                making them searchable via semantic_search.

                Use this to build up a knowledge base of articles or documents
                that can be searched semantically.
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "documents": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "metadata": {"type": "object"},
                                "id": {"type": "string"},
                            },
                            "required": ["text"],
                        },
                        "description": "List of documents to add",
                        "minItems": 1,
                        "maxItems": 100,
                    },
                },
                "required": ["documents"],
            },
        ),
        types.Tool(
            name="get_embeddings",
            description="""
                Generate embedding vectors for text.

                This converts text into a numerical vector representation
                that captures its semantic meaning. The resulting vectors
                can be used for similarity calculations, clustering, etc.

                Returns 768-dimensional vectors from Vertex AI's embedding model.
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "texts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of texts to embed",
                        "minItems": 1,
                        "maxItems": 50,
                    },
                },
                "required": ["texts"],
            },
        ),
        types.Tool(
            name="search_similar_articles",
            description="""
                Find articles similar to a given PubMed article.

                Given an article's text or abstract, this finds other articles
                in the vector store that are semantically similar.

                Useful for finding related research or discovering connections
                between different papers.
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "article_text": {
                        "type": "string",
                        "description": "Article title + abstract to find similar articles for",
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of similar articles to return (default: 5)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
                "required": ["article_text"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Execute a tool call"""

    try:
        if name == "semantic_search":
            query = arguments["query"]
            n_results = arguments.get("n_results", 10)
            filter_dict = arguments.get("filter")

            # Get services
            embedding_service = get_embedding_service()
            vector_store = get_vector_store()

            # Generate embedding for query
            query_embeddings = await embedding_service.get_embeddings([query])
            query_embedding = query_embeddings[0]

            # Search vector store
            results = vector_store.search(
                query_embedding=query_embedding,
                n_results=n_results,
                where=filter_dict
            )

            # Format results
            formatted_results = {
                "query": query,
                "total_results": len(results["documents"]),
                "results": [
                    {
                        "document": doc,
                        "similarity_score": 1 - dist,  # Convert distance to similarity
                        "metadata": meta,
                        "id": doc_id,
                    }
                    for doc, dist, meta, doc_id in zip(
                        results["documents"],
                        results["distances"],
                        results["metadatas"],
                        results["ids"]
                    )
                ],
            }

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(formatted_results, indent=2),
                )
            ]

        elif name == "add_documents":
            documents = arguments["documents"]

            # Extract texts, metadata, and IDs
            texts = [doc["text"] for doc in documents]
            metadatas = [doc.get("metadata", {}) for doc in documents]
            ids = [doc.get("id") for doc in documents]

            # Generate embeddings
            embedding_service = get_embedding_service()
            embeddings = await embedding_service.get_embeddings(texts)

            # Add to vector store
            vector_store = get_vector_store()
            vector_store.add_documents(
                texts=texts,
                metadatas=metadatas,
                embeddings=embeddings,
                ids=ids if all(ids) else None
            )

            result = {
                "status": "success",
                "documents_added": len(documents),
                "timestamp": datetime.now().isoformat(),
            }

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        elif name == "get_embeddings":
            texts = arguments["texts"]

            # Generate embeddings
            embedding_service = get_embedding_service()
            embeddings = await embedding_service.get_embeddings(texts)

            result = {
                "texts": texts,
                "embeddings": embeddings,
                "dimensions": len(embeddings[0]) if embeddings else 0,
                "count": len(embeddings),
            }

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        elif name == "search_similar_articles":
            article_text = arguments["article_text"]
            n_results = arguments.get("n_results", 5)

            # Generate embedding for the article
            embedding_service = get_embedding_service()
            embeddings = await embedding_service.get_embeddings([article_text])
            article_embedding = embeddings[0]

            # Search for similar articles
            vector_store = get_vector_store()
            results = vector_store.search(
                query_embedding=article_embedding,
                n_results=n_results + 1  # +1 because it might match itself
            )

            # Format results
            formatted_results = {
                "query_article_preview": article_text[:200] + "...",
                "similar_articles": [
                    {
                        "document": doc,
                        "similarity_score": 1 - dist,
                        "metadata": meta,
                    }
                    for doc, dist, meta in zip(
                        results["documents"],
                        results["distances"],
                        results["metadatas"]
                    )
                ][:n_results],  # Exclude self-match if present
            }

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(formatted_results, indent=2),
                )
            ]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        error_result = {
            "error": str(e),
            "tool": name,
            "timestamp": datetime.now().isoformat(),
        }
        return [
            types.TextContent(
                type="text",
                text=json.dumps(error_result, indent=2),
            )
        ]


# ============================================================================
# SERVER ENTRY POINT
# ============================================================================

async def main():
    """Main entry point for the vector/embedding MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="vector-embedding-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    """
    Start the vector/embedding MCP server.

    Usage:
        python mcp_servers/vector_server.py

    Requirements:
        - Google Cloud credentials configured
        - PROJECT_ID environment variable set
    """
    asyncio.run(main())
