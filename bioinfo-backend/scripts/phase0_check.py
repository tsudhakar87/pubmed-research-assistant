"""
Phase 0 check for the evidence map: run the app's own clients against the real APIs.

    cd bioinfo-backend
    python -m scripts.phase0_check "metformin gut microbiome"      # all checks
    python -m scripts.phase0_check "metformin gut microbiome" --no-gemini

Needs NCBI_EMAIL (and optionally NCBI_API_KEY) in the environment or .env.
The Gemini check also needs PROJECT_ID/GOOGLE_CLOUD_PROJECT and Google
application-default credentials (`gcloud auth application-default login`).

What it does:
1. PubMed: searches, fetches records, saves the raw EFetch XML to
   tests/fixtures/real/, and reports how many records have publication types,
   MeSH terms, structured abstracts and trial IDs.
2. iCite: fetches citation data for those PMIDs, saves the raw JSON, reports coverage.
3. Europe PMC: runs the preprint search for bioRxiv and medRxiv and reports hit counts.
4. Gemini: frames the question and extracts evidence for up to 10 abstracts, then
   prints each paper's labels and the quote-verification rate (target: > 90%).
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

from src.agents.bioinfo_agent import BioinfoAgent
from src.config.settings import settings
from src.external.data_parser import parse_pubmed_xml
from src.external.icite_client import _FIELDS, ICITE_PUBS, ICiteClient
from src.external.ncbi_client import NCBIClient
from src.external.preprint_client import PreprintClient
from src.services.evidence_extractor import EvidenceExtractor, build_evidence
from src.services.gemini_client import get_gemini_client

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "real"


def pct(n: int, total: int) -> str:
    return f"{n}/{total} ({100 * n / total:.0f}%)" if total else "0/0"


async def check_pubmed(query: str, n: int):
    print(f"\n== PubMed: '{query}' ==")
    async with NCBIClient(email=settings.ncbi_email, api_key=settings.ncbi_api_key) as ncbi:
        pmids = await ncbi.search(query, max_results=n)
        xml = await ncbi._make_request("efetch.fcgi", ncbi._build_params(
            db="pubmed", id=",".join(pmids), retmode="xml", rettype="abstract"))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pubmed_efetch.xml").write_text(xml)
    articles = parse_pubmed_xml(xml)
    total = len(articles)
    print(f"Saved {OUT / 'pubmed_efetch.xml'}  ({total} records)")
    print("  with abstract:          ", pct(sum(a.has_abstract for a in articles), total))
    print("  with design pubtype:    ", pct(sum(any(t != "Journal Article" for t in a.publication_types) for a in articles), total))
    print("  with MeSH terms:        ", pct(sum(bool(a.mesh_terms) for a in articles), total))
    print("  structured abstract:    ", pct(sum(bool(a.abstract_sections) for a in articles), total))
    print("  with trial IDs:         ", pct(sum(bool(a.trial_ids) for a in articles), total))
    return articles


async def check_icite(pmids):
    print("\n== iCite ==")
    client = ICiteClient()
    try:
        session = await client._get_session()
        async with session.get(ICITE_PUBS, params={"pmids": ",".join(pmids), "fl": _FIELDS + ",year,title"}) as resp:
            raw = await resp.json(content_type=None)
        (OUT / "icite_pubs.json").write_text(json.dumps(raw, indent=1))
        print(f"Saved {OUT / 'icite_pubs.json'}")
        data = await client.fetch(pmids)
    finally:
        await client.close()
    print("  PMIDs with data:        ", pct(len(data), len(pmids)))
    print("  with RCR:               ", pct(sum(c.relative_citation_ratio is not None for c in data.values()), len(pmids)))
    return data


async def check_preprints(query: str):
    print("\n== Europe PMC preprints ==")
    client = PreprintClient()
    try:
        for server in ("biorxiv", "medrxiv"):
            hits = await client.search(query, server=server, max_results=10)
            print(f"  {server}: {len(hits)} hits" + (f"; first: {hits[0].title[:70]}" if hits else ""))
    finally:
        await client.close()


async def check_gemini(query: str, articles, citations):
    print("\n== Gemini extraction ==")
    extractor = EvidenceExtractor()
    if not extractor.available:
        print("  skipped: no PROJECT_ID / GOOGLE_CLOUD_PROJECT configured")
        return
    framed = await extractor.frame_question(query)
    if framed is None:
        print("  framing failed (check credentials and model name)")
        return
    print(f"  question: {framed.question}  (answerable={framed.answerable})")
    papers = BioinfoAgent._convert_to_paper_results(None, articles)[:10]
    raw = await extractor.extract(framed, papers)
    if not raw:
        print("  extraction returned nothing")
        return
    verified = 0
    for i, r in sorted(raw.items()):
        ev = build_evidence(r, papers[i], citations.get(papers[i].pmid or ""))
        verified += ev.verified
        print(f"  [{i + 1}] {ev.design}/{ev.design_source} {ev.organism}/{ev.organism_source} "
              f"n={ev.sample_size} {ev.stance} {'OK ' if ev.verified else 'UNVERIFIED'} | {ev.key_finding}")
    print(f"  extracted: {pct(len(raw), len(papers))}   quotes verified: {pct(verified, len(raw))}  (target > 90%)")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("-n", type=int, default=20)
    ap.add_argument("--no-gemini", action="store_true")
    args = ap.parse_args()

    if settings.ncbi_email == "your-email@example.com":
        sys.exit("Set NCBI_EMAIL first (NCBI requires a contact email).")

    articles = await check_pubmed(args.query, args.n)
    citations = await check_icite([a.pmid for a in articles])
    await check_preprints(args.query)
    if not args.no_gemini:
        try:
            await check_gemini(args.query, articles, citations)
        finally:
            await get_gemini_client().aclose()


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    asyncio.run(main())
