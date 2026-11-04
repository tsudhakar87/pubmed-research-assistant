"""
Preprint search for bioRxiv and medRxiv.

The bioRxiv/medRxiv API (api.biorxiv.org) only lists preprints by date range or DOI;
it has no keyword search. Europe PMC indexes both servers and supports full query
syntax, so searches go through its REST API, filtered to one preprint server at a time:
https://europepmc.org/RestfulWebService
"""
import html
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import aiohttp

logger = logging.getLogger(__name__)

EUROPE_PMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

# Our server key -> publisher name as Europe PMC records it
SERVERS = {"biorxiv": "bioRxiv", "medrxiv": "medRxiv"}

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_markup(text: Optional[str]) -> str:
    """Europe PMC abstracts can contain HTML (<h4>, <i>, ...). Return plain text."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub(" ", text))).strip()


def _to_epmc_date(date: str) -> str:
    """'2024/01/31' or '2024' (PubMed style) -> '2024-01-31' / '2024-01-01'."""
    parts = date.replace("-", "/").split("/")
    year = parts[0]
    month = parts[1] if len(parts) > 1 else "01"
    day = parts[2] if len(parts) > 2 else "01"
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def build_query(
    query: str,
    server: str,
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
) -> str:
    """Europe PMC query restricted to one preprint server and an optional date range."""
    q = query.strip()
    if q.count('"') % 2:
        q = q.replace('"', "")  # unbalanced quotes would make the query invalid
    parts = [f"({q})", "SRC:PPR", f'PUBLISHER:"{SERVERS[server]}"']
    if min_date or max_date:
        lo = _to_epmc_date(min_date) if min_date else "1900-01-01"
        hi = _to_epmc_date(max_date) if max_date else "3000-12-31"
        parts.append(f"FIRST_PDATE:[{lo} TO {hi}]")
    return " AND ".join(parts)


@dataclass
class PreprintArticle:
    title: str
    authors: List[str]
    abstract: str
    doi: str
    publication_date: Optional[datetime]
    server: str  # "biorxiv" | "medrxiv"
    keywords: List[str] = field(default_factory=list)


def parse_record(item: dict, server: str) -> PreprintArticle:
    """Convert one Europe PMC 'core' result into a PreprintArticle."""
    author_list = (item.get("authorList") or {}).get("author") or []
    authors = [a["fullName"].strip() for a in author_list if a.get("fullName")]
    if not authors and item.get("authorString"):
        authors = [a.strip() for a in item["authorString"].rstrip(".").split(",") if a.strip()]

    date_str = item.get("firstPublicationDate")
    pub_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else None

    keywords = ((item.get("keywordList") or {}).get("keyword")) or []

    return PreprintArticle(
        title=_strip_markup(item.get("title")),
        authors=authors,
        abstract=_strip_markup(item.get("abstractText")),
        doi=(item.get("doi") or "").strip(),
        publication_date=pub_date,
        server=server,
        keywords=[k for k in keywords if isinstance(k, str)],
    )


class PreprintClient:
    """
    Async preprint search. Pass an aiohttp session to share one (and to test with a mock);
    otherwise the client creates its own and closes it in close().
    """

    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self._session = session
        self._owns_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        return self._session

    async def search(
        self,
        query: str,
        server: str,
        max_results: int = 10,
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
    ) -> List[PreprintArticle]:
        """Search one server ("biorxiv" or "medrxiv"). Never raises: failures return []."""
        if server not in SERVERS:
            raise ValueError(f"Unknown preprint server: {server}")

        params = {
            "query": build_query(query, server, min_date, max_date),
            "format": "json",
            "resultType": "core",
            "pageSize": str(max_results),
        }
        try:
            session = await self._get_session()
            async with session.get(EUROPE_PMC_SEARCH, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
            items = (data.get("resultList") or {}).get("result") or []
        except Exception as exc:
            logger.warning("Preprint search failed (%s): %s", server, exc)
            return []

        articles = []
        for item in items[:max_results]:
            try:
                article = parse_record(item, server)
            except Exception:
                continue  # skip a malformed record, keep the rest
            if article.title:
                articles.append(article)
        return articles

    async def close(self) -> None:
        if self._owns_session and self._session:
            await self._session.close()
            self._session = None
