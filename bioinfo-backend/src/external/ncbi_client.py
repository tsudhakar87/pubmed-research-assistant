"""
NCBI E-utilities API client for PubMed/literature searches
Wrapper for NCBI Entrez E-utilities: https://www.ncbi.nlm.nih.gov/books/NBK25501/
"""
import xml.etree.ElementTree as ET
from typing import List, Optional, Dict

import aiohttp
from .rate_limiter import NCBIRateLimiter
from .data_parser import PubMedArticle, parse_pubmed_xml


class NCBIClient:
    """
    Async client for NCBI E-utilities API

    Primary endpoints used:
    - ESearch: search and retrieve primary IDs
    - EFetch: retrieve full records
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(
        self,
        email: str,
        api_key: Optional[str] = None,
        tool_name: str = "bioinformatics-research-assistant"
    ):
        """
        Initialize NCBI client

        Args:
            email: Email address (required by NCBI)
            api_key: NCBI API key for higher rate limits
            tool_name: Name of your application
        """
        if not email:
            raise ValueError("Email is required by NCBI E-utilities policy")

        self.email = email
        self.api_key = api_key
        self.tool_name = tool_name
        self.rate_limiter = NCBIRateLimiter(api_key=api_key)
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry"""
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        """Async context manager exit"""
        if self._session:
            await self._session.close()
            self._session = None

    def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    def _build_params(self, **kwargs) -> Dict[str, str]:
        """Build common request parameters"""
        params = {
            "email": self.email,
            "tool": self.tool_name,
        }
        if self.api_key:
            params["api_key"] = self.api_key

        # Add additional parameters
        params.update({k: str(v) for k, v in kwargs.items() if v is not None})
        return params

    async def _make_request(self, endpoint: str, params: Dict[str, str]) -> str:
        """
        Make rate-limited request to NCBI API

        Args:
            endpoint: API endpoint (e.g., 'esearch.fcgi', 'efetch.fcgi')
            params: Query parameters

        Returns:
            Response text
        """
        await self.rate_limiter.acquire()

        url = f"{self.BASE_URL}/{endpoint}"
        session = self._get_session()

        async with session.get(url, params=params) as response:
            response.raise_for_status()
            return await response.text()

    async def search(
        self,
        query: str,
        database: str = "pubmed",
        max_results: int = 20,
        sort: str = "relevance",
        min_date: Optional[str] = None,
        max_date: Optional[str] = None
    ) -> List[str]:
        """
        Search NCBI database and return list of IDs

        Args:
            query: Search query string
            database: NCBI database to search (default: pubmed)
            max_results: Maximum number of results to return
            sort: Sort order (relevance, pub_date, etc.)
            min_date: Minimum date (YYYY/MM/DD or YYYY/MM or YYYY)
            max_date: Maximum date (YYYY/MM/DD or YYYY/MM or YYYY)

        Returns:
            List of PubMed IDs (PMIDs)
        """
        params = self._build_params(
            db=database,
            term=query,
            retmax=max_results,
            sort=sort,
            retmode="xml"
        )

        if min_date:
            params["mindate"] = min_date
        if max_date:
            params["maxdate"] = max_date

        response_text = await self._make_request("esearch.fcgi", params)

        # Parse XML response
        root = ET.fromstring(response_text)
        id_list = root.find("IdList")

        if id_list is None:
            return []

        return [id_elem.text for id_elem in id_list.findall("Id")]

    async def fetch_articles(
        self,
        pmids: List[str],
        database: str = "pubmed"
    ) -> List[PubMedArticle]:
        """
        Fetch full article records from PubMed

        Args:
            pmids: List of PubMed IDs to fetch
            database: NCBI database (default: pubmed)

        Returns:
            List of PubMedArticle objects
        """
        if not pmids:
            return []

        # Join PMIDs with commas
        id_string = ",".join(pmids)

        params = self._build_params(
            db=database,
            id=id_string,
            retmode="xml",
            rettype="abstract"
        )

        response_text = await self._make_request("efetch.fcgi", params)

        # Parse XML and extract article data
        return parse_pubmed_xml(response_text)

    async def search_and_fetch(
        self,
        query: str,
        max_results: int = 20,
        **search_kwargs
    ) -> List[PubMedArticle]:
        """
        Convenience method: search and fetch articles in one call

        Args:
            query: Search query
            max_results: Maximum number of results
            **search_kwargs: Additional arguments for search()

        Returns:
            List of PubMedArticle objects
        """
        pmids = await self.search(query, max_results=max_results, **search_kwargs)
        if not pmids:
            return []

        return await self.fetch_articles(pmids)

    async def close(self):
        """Close the aiohttp session"""
        if self._session:
            await self._session.close()
            self._session = None


# Convenience function for one-off queries
async def search_pubmed(
    query: str,
    email: str,
    max_results: int = 20,
    api_key: Optional[str] = None
) -> List[PubMedArticle]:
    """
    Simple function to search PubMed

    Args:
        query: Search query
        email: Your email address
        max_results: Maximum results to return
        api_key: Optional NCBI API key

    Returns:
        List of PubMedArticle objects
    """
    async with NCBIClient(email=email, api_key=api_key) as client:
        return await client.search_and_fetch(query, max_results=max_results)
