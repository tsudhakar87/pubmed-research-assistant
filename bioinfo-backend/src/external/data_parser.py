"""
Parse NCBI responses into structured data objects
"""
import logging
import xml.etree.ElementTree as ET
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

NO_ABSTRACT = "No abstract available"
_NCT_RE = re.compile(r"^NCT\d{8}$")


def _text(elem: Optional[ET.Element]) -> str:
    """All text inside an element, including text after inline tags like <i> or <sup>."""
    if elem is None:
        return ""
    return re.sub(r"\s+", " ", "".join(elem.itertext())).strip()


@dataclass
class PubMedArticle:
    """PubMed article data structure"""
    pmid: str
    title: str
    abstract: str
    authors: List[str]
    journal: Optional[str] = None
    publication_date: Optional[datetime] = None
    doi: Optional[str] = None
    keywords: List[str] = None
    # Curated NLM metadata, e.g. ["Journal Article", "Randomized Controlled Trial"]
    publication_types: List[str] = field(default_factory=list)
    # MeSH descriptor names, including check tags like "Humans" or "Animals"
    mesh_terms: List[str] = field(default_factory=list)
    # Labeled sections of a structured abstract, e.g. {"RESULTS": "..."}; {} if unstructured
    abstract_sections: Dict[str, str] = field(default_factory=dict)
    # ClinicalTrials.gov registry numbers (NCT...) linked to the article
    trial_ids: List[str] = field(default_factory=list)
    has_abstract: bool = True

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []


def parse_pubmed_xml(xml_text: str) -> List[PubMedArticle]:
    """
    Parse PubMed XML response into PubMedArticle objects

    Args:
        xml_text: XML response from EFetch

    Returns:
        List of PubMedArticle objects
    """
    articles = []
    root = ET.fromstring(xml_text)

    for article in root.findall(".//PubmedArticle"):
        try:
            # Extract PMID
            pmid_elem = article.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else ""

            # Extract title
            # itertext(): .text alone stops at the first inline tag (<i>, <sup>, ...)
            title = _text(article.find(".//ArticleTitle")) or "No title available"

            # Extract abstract, keeping section labels of structured abstracts
            abstract_parts = []
            abstract_sections: Dict[str, str] = {}
            abstract_elem = article.find(".//Abstract")
            if abstract_elem is not None:
                for text_elem in abstract_elem.findall(".//AbstractText"):
                    part = _text(text_elem)
                    if not part:
                        continue
                    abstract_parts.append(part)
                    label = (text_elem.get("Label") or "").strip().upper()
                    if label:
                        prev = abstract_sections.get(label)
                        abstract_sections[label] = f"{prev} {part}" if prev else part
            has_abstract = bool(abstract_parts)
            abstract = " ".join(abstract_parts) if has_abstract else NO_ABSTRACT

            # Extract authors
            authors = []
            author_list = article.find(".//AuthorList")
            if author_list is not None:
                for author in author_list.findall(".//Author"):
                    last_name = author.find("LastName")
                    fore_name = author.find("ForeName")
                    if last_name is not None and fore_name is not None:
                        authors.append(f"{fore_name.text} {last_name.text}")
                    elif last_name is not None:
                        authors.append(last_name.text)

            # Extract journal
            journal_elem = article.find(".//Journal/Title")
            journal = journal_elem.text if journal_elem is not None else None

            # Extract publication date
            pub_date = None
            pub_date_elem = article.find(".//PubDate")
            if pub_date_elem is not None:
                year = pub_date_elem.find("Year")
                month = pub_date_elem.find("Month")
                day = pub_date_elem.find("Day")

                if year is not None:
                    try:
                        year_val = int(year.text)
                        month_val = parse_month(month.text) if month is not None else 1
                        day_val = int(day.text) if day is not None else 1
                        pub_date = datetime(year_val, month_val, day_val)
                    except (ValueError, AttributeError):
                        pass

            # Extract DOI
            doi = None
            for article_id in article.findall(".//ArticleId"):
                if article_id.get("IdType") == "doi":
                    doi = article_id.text
                    break

            # Extract keywords
            keywords = []
            keyword_list = article.find(".//KeywordList")
            if keyword_list is not None:
                keywords = [kw.text for kw in keyword_list.findall(".//Keyword") if kw.text]

            publication_types = [
                t for t in (_text(e) for e in article.findall(".//PublicationTypeList/PublicationType")) if t
            ]
            mesh_terms = [
                t for t in (_text(e) for e in article.findall(".//MeshHeadingList/MeshHeading/DescriptorName")) if t
            ]
            trial_ids = []
            for accession in article.findall(".//DataBankList/DataBank/AccessionNumberList/AccessionNumber"):
                acc = _text(accession).upper()
                if _NCT_RE.match(acc) and acc not in trial_ids:
                    trial_ids.append(acc)

            articles.append(PubMedArticle(
                pmid=pmid,
                title=title,
                abstract=abstract,
                authors=authors,
                journal=journal,
                publication_date=pub_date,
                doi=doi,
                keywords=keywords,
                publication_types=publication_types,
                mesh_terms=mesh_terms,
                abstract_sections=abstract_sections,
                trial_ids=trial_ids,
                has_abstract=has_abstract,
            ))

        except Exception as e:
            # Log error but continue processing other articles
            logger.warning("Error parsing article: %s", e)
            continue

    return articles


def parse_month(month_str: str) -> int:
    """
    Convert month name/number to integer

    Args:
        month_str: Month name (e.g., 'Jan', 'January') or number string

    Returns:
        Month as integer (1-12), defaults to 1 if not recognized
    """
    month_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4,
        "may": 5, "jun": 6, "jul": 7, "aug": 8,
        "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }

    month_lower = month_str.lower()[:3]
    return month_map.get(month_lower, 1)
