"""
Analytics & Data Analysis MCP Server

This MCP server provides data analysis, statistics, and BigQuery analytics tools
for analyzing research data and trends.

Tools exposed:
- analyze_research_trends: Analyze publication trends over time
- generate_statistics: Generate statistical summaries of data
- query_bigquery: Execute BigQuery SQL queries for analytics
- compare_topics: Compare publication metrics between topics

EXPLANATION:
This server enables data-driven insights from research data. It can:
- Track how research topics evolve over time
- Compare publication volumes across different fields
- Generate statistical summaries
- Query large datasets in BigQuery for custom analytics
"""

import asyncio
import json
import os
import sys
from typing import Any, List, Dict, Optional
from datetime import datetime
from collections import Counter, defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp import types

# Import analytics dependencies
try:
    from google.cloud import bigquery
    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

from src.config.settings import settings


# Initialize the MCP server
server = Server("analytics-server")


class AnalyticsService:
    """
    Provides data analysis and statistical tools.

    This service analyzes research data to identify trends, patterns,
    and generate insights from publication metadata.
    """

    def __init__(self):
        self.cache = {}

    def analyze_trends(
        self,
        articles: List[Dict],
        time_period: str = "year"
    ) -> Dict[str, Any]:
        """
        Analyze publication trends over time.

        Args:
            articles: List of article metadata
            time_period: Grouping period ('year', 'month', 'quarter')

        Returns:
            Trend analysis with counts and statistics
        """
        if not articles:
            return {"error": "No articles to analyze"}

        # Group by time period
        time_counts = Counter()
        keyword_trends = defaultdict(list)

        for article in articles:
            pub_date = article.get("publication_date")
            if not pub_date:
                continue

            # Parse date and group by period
            if isinstance(pub_date, str):
                try:
                    pub_date = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                except:
                    continue

            if time_period == "year":
                period_key = pub_date.strftime("%Y")
            elif time_period == "month":
                period_key = pub_date.strftime("%Y-%m")
            elif time_period == "quarter":
                quarter = (pub_date.month - 1) // 3 + 1
                period_key = f"{pub_date.year}-Q{quarter}"
            else:
                period_key = pub_date.strftime("%Y")

            time_counts[period_key] += 1

            # Track keyword trends
            keywords = article.get("keywords", [])
            for keyword in keywords:
                keyword_trends[keyword].append(period_key)

        # Calculate statistics
        counts = list(time_counts.values())
        avg_per_period = sum(counts) / len(counts) if counts else 0
        max_period = max(time_counts.items(), key=lambda x: x[1]) if time_counts else (None, 0)

        # Top trending keywords
        top_keywords = sorted(
            [(kw, len(periods)) for kw, periods in keyword_trends.items()],
            key=lambda x: x[1],
            reverse=True
        )[:10]

        return {
            "total_articles": len(articles),
            "time_period": time_period,
            "timeline": dict(sorted(time_counts.items())),
            "statistics": {
                "average_per_period": avg_per_period,
                "peak_period": max_period[0],
                "peak_count": max_period[1],
            },
            "top_keywords": [{"keyword": kw, "count": count} for kw, count in top_keywords],
        }

    def generate_statistics(self, data: List[Dict], fields: List[str]) -> Dict[str, Any]:
        """
        Generate statistical summaries for specified fields.

        Args:
            data: List of data records
            fields: Fields to analyze

        Returns:
            Statistical summary
        """
        if not data:
            return {"error": "No data to analyze"}

        stats = {}

        for field in fields:
            values = [item.get(field) for item in data if field in item]

            if not values:
                stats[field] = {"error": "No values found"}
                continue

            # Check if numeric
            numeric_values = []
            for v in values:
                try:
                    numeric_values.append(float(v))
                except (ValueError, TypeError):
                    pass

            if numeric_values and NUMPY_AVAILABLE:
                # Numeric statistics
                arr = np.array(numeric_values)
                stats[field] = {
                    "type": "numeric",
                    "count": len(numeric_values),
                    "mean": float(np.mean(arr)),
                    "median": float(np.median(arr)),
                    "std": float(np.std(arr)),
                    "min": float(np.min(arr)),
                    "max": float(np.max(arr)),
                }
            else:
                # Categorical statistics
                value_counts = Counter(values)
                stats[field] = {
                    "type": "categorical",
                    "count": len(values),
                    "unique_values": len(value_counts),
                    "most_common": [
                        {"value": val, "count": count}
                        for val, count in value_counts.most_common(10)
                    ],
                }

        return {
            "total_records": len(data),
            "fields_analyzed": len(fields),
            "statistics": stats,
        }

    def compare_topics(
        self,
        topic_data: Dict[str, List[Dict]]
    ) -> Dict[str, Any]:
        """
        Compare metrics across different topics.

        Args:
            topic_data: Dict mapping topic names to article lists

        Returns:
            Comparative analysis
        """
        comparison = {}

        for topic, articles in topic_data.items():
            if not articles:
                comparison[topic] = {"error": "No articles"}
                continue

            # Calculate metrics
            total = len(articles)
            authors = []
            journals = Counter()
            years = []

            for article in articles:
                authors.extend(article.get("authors", []))
                if article.get("journal"):
                    journals[article["journal"]] += 1

                pub_date = article.get("publication_date")
                if pub_date:
                    if isinstance(pub_date, str):
                        try:
                            pub_date = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                            years.append(pub_date.year)
                        except:
                            pass

            comparison[topic] = {
                "total_articles": total,
                "unique_authors": len(set(authors)),
                "unique_journals": len(journals),
                "top_journals": [
                    {"journal": j, "count": c}
                    for j, c in journals.most_common(5)
                ],
                "year_range": {
                    "earliest": min(years) if years else None,
                    "latest": max(years) if years else None,
                },
            }

        return {
            "topics_compared": len(topic_data),
            "comparison": comparison,
        }


class BigQueryService:
    """
    Executes queries against Google BigQuery for large-scale analytics.

    BigQuery is Google's serverless data warehouse that can analyze
    terabytes of data in seconds. Useful for large-scale research analytics.
    """

    def __init__(self):
        if not BIGQUERY_AVAILABLE:
            raise ImportError("BigQuery not installed. Run: pip install google-cloud-bigquery")

        # Initialize BigQuery client
        self.client = bigquery.Client(
            project=settings.project_id
        )
        self.dataset_id = settings.bigquery_dataset

    async def execute_query(self, query: str, max_results: int = 1000) -> Dict[str, Any]:
        """
        Execute a BigQuery SQL query.

        Args:
            query: SQL query to execute
            max_results: Maximum number of rows to return

        Returns:
            Query results
        """
        try:
            # Run query asynchronously
            loop = asyncio.get_event_loop()
            query_job = await loop.run_in_executor(
                None,
                lambda: self.client.query(query)
            )

            # Get results
            results = await loop.run_in_executor(
                None,
                lambda: list(query_job.result(max_results=max_results))
            )

            # Convert to list of dicts
            rows = []
            for row in results:
                rows.append(dict(row))

            return {
                "status": "success",
                "row_count": len(rows),
                "rows": rows,
                "total_bytes_processed": query_job.total_bytes_processed,
                "total_bytes_billed": query_job.total_bytes_billed,
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }


# Initialize services (lazy loading)
_analytics_service: Optional[AnalyticsService] = None
_bigquery_service: Optional[BigQueryService] = None


def get_analytics_service() -> AnalyticsService:
    """Get or create analytics service instance"""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service


def get_bigquery_service() -> BigQueryService:
    """Get or create BigQuery service instance"""
    global _bigquery_service
    if _bigquery_service is None:
        _bigquery_service = BigQueryService()
    return _bigquery_service


# ============================================================================
# TOOL DEFINITIONS
# ============================================================================

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List all available analytics tools"""
    return [
        types.Tool(
            name="analyze_research_trends",
            description="""
                Analyze publication trends over time.

                Given a set of articles, this analyzes how publications
                are distributed over time, identifies peak periods,
                and tracks keyword trends.

                Useful for understanding:
                - How research interest in a topic evolves
                - Peak publication periods
                - Emerging vs. declining topics
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "articles": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of article objects with publication_date and keywords",
                    },
                    "time_period": {
                        "type": "string",
                        "enum": ["year", "month", "quarter"],
                        "description": "Time period for grouping (default: year)",
                        "default": "year",
                    },
                },
                "required": ["articles"],
            },
        ),
        types.Tool(
            name="generate_statistics",
            description="""
                Generate statistical summaries of data.

                Analyzes specified fields and generates statistics:
                - Numeric fields: mean, median, std, min, max
                - Categorical fields: counts, most common values

                Useful for understanding data distributions and patterns.
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of data records to analyze",
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Fields to analyze",
                    },
                },
                "required": ["data", "fields"],
            },
        ),
        types.Tool(
            name="compare_topics",
            description="""
                Compare publication metrics between different topics.

                Given articles grouped by topic, this compares:
                - Total publications
                - Author diversity
                - Journal distribution
                - Time ranges

                Useful for comparative research analysis.
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic_data": {
                        "type": "object",
                        "description": "Object mapping topic names to article arrays",
                        "additionalProperties": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                    },
                },
                "required": ["topic_data"],
            },
        ),
        types.Tool(
            name="query_bigquery",
            description="""
                Execute a SQL query against BigQuery for large-scale analytics.

                BigQuery is Google's data warehouse that can analyze massive datasets.
                Use this for complex analytics queries over large amounts of data.

                Example queries:
                - Aggregating publication counts by year and journal
                - Finding top-cited papers
                - Complex joins and aggregations

                Note: Requires BigQuery dataset to be set up with research data.
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of rows to return (default: 1000)",
                        "default": 1000,
                        "minimum": 1,
                        "maximum": 10000,
                    },
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Execute a tool call"""

    try:
        if name == "analyze_research_trends":
            articles = arguments["articles"]
            time_period = arguments.get("time_period", "year")

            analytics = get_analytics_service()
            result = analytics.analyze_trends(articles, time_period)

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        elif name == "generate_statistics":
            data = arguments["data"]
            fields = arguments["fields"]

            analytics = get_analytics_service()
            result = analytics.generate_statistics(data, fields)

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        elif name == "compare_topics":
            topic_data = arguments["topic_data"]

            analytics = get_analytics_service()
            result = analytics.compare_topics(topic_data)

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        elif name == "query_bigquery":
            query = arguments["query"]
            max_results = arguments.get("max_results", 1000)

            bigquery_service = get_bigquery_service()
            result = await bigquery_service.execute_query(query, max_results)

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
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
    """Main entry point for the analytics MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="analytics-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    """
    Start the analytics MCP server.

    Usage:
        python mcp_servers/analytics_server.py

    Requirements:
        - Google Cloud credentials configured (for BigQuery)
        - PROJECT_ID environment variable set
    """
    asyncio.run(main())
