"""
NIH iCite client: citation counts, Relative Citation Ratio (RCR) and
human/animal/molecular-cellular fractions per PubMed ID.
Free, no API key. Docs: https://icite.od.nih.gov/api
"""
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

ICITE_PUBS = "https://icite.od.nih.gov/api/pubs"
# Kept well under iCite's documented per-request limit
BATCH_SIZE = 200
_FIELDS = "pmid,citation_count,relative_citation_ratio,human,animal,molecular_cellular"


@dataclass
class CitationInfo:
    pmid: str
    citation_count: int
    # None for papers too new to have a field-normalized score
    relative_citation_ratio: Optional[float]
    human: float
    animal: float
    molecular_cellular: float


def _float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_record(item: dict) -> CitationInfo:
    rcr = item.get("relative_citation_ratio")
    return CitationInfo(
        pmid=str(item["pmid"]),
        citation_count=int(item.get("citation_count") or 0),
        relative_citation_ratio=float(rcr) if rcr is not None else None,
        human=_float(item.get("human")),
        animal=_float(item.get("animal")),
        molecular_cellular=_float(item.get("molecular_cellular")),
    )


class ICiteClient:
    """Pass an aiohttp session to share one (or a mock in tests); otherwise one is created."""

    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self._session = session
        self._owns_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        return self._session

    async def _fetch_batch(self, pmids: List[str]) -> Dict[str, CitationInfo]:
        params = {"pmids": ",".join(pmids), "fl": _FIELDS}
        try:
            session = await self._get_session()
            async with session.get(ICITE_PUBS, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
            items = data.get("data") or []
        except Exception as exc:
            logger.warning("iCite request failed: %s", exc)
            return {}

        out: Dict[str, CitationInfo] = {}
        for item in items:
            try:
                info = parse_record(item)
            except Exception:
                continue
            out[info.pmid] = info
        return out

    async def fetch(self, pmids: List[str]) -> Dict[str, CitationInfo]:
        """Citation info keyed by PMID. Unknown PMIDs are absent. Never raises."""
        unique = list(dict.fromkeys(p for p in pmids if p))
        result: Dict[str, CitationInfo] = {}
        for i in range(0, len(unique), BATCH_SIZE):
            result.update(await self._fetch_batch(unique[i:i + BATCH_SIZE]))
        return result

    async def close(self) -> None:
        if self._owns_session and self._session:
            await self._session.close()
            self._session = None
