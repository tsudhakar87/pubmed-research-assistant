# Plan: Evidence Map (structured findings, timeline, grounded synthesis)

## Context
Today the app returns a list of papers plus a paragraph from Gemini, which only sees the top 5 abstracts (truncated to 500 chars). The year-count trend chart is something PubMed already offers. Result: it still reads as a PubMed wrapper.

This plan turns each abstract into structured data (design, organism, sample size, what was found, and whether it supports the question), aggregates it deterministically, and builds the results page from that data:

1. **Evidence panel**: the question being answered, how the papers split (supports / mixed / no effect / contradicts), filterable by human / animal / in vitro, plus study-design breakdown and evidence gaps.
2. **Findings timeline** (replaces the trend chart): one dot per paper, x = year, lane = stance, color = organism, size = sample size. Shows how the evidence evolved, not how many papers were published.
3. **Grounded synthesis**: Gemini writes from the extracted table and computed facts, cites papers as [n], explains disagreements, and names gaps.

No new paid services. Data comes from fields PubMed already returns, one free NIH API (iCite), and one Gemini extraction call per query.

---

## Critical Design Decisions & Rationale

**Metadata first, LLM second**
PubMed records already carry `PublicationType` (RCT, Meta-Analysis, Review, ...) and MeSH check tags (Humans, Animals, Mice, ...). These are curated by NLM and free. Use them for study design and organism whenever present; Gemini only fills gaps (recent papers not yet MeSH-indexed, preprints) and extracts what nobody tags: sample size, finding, stance.

**Counting happens in code, never in the LLM**
Gemini extracts per-paper fields. Every number shown to the user (stance counts, design counts, largest n, latest RCT year) is computed by `EvidenceAggregator` from those fields. The synthesis prompt receives these numbers as facts. This keeps counts correct and auditable.

**Every finding must quote the abstract**
Extraction returns `finding_quote`, a verbatim span from the abstract. The backend checks it is actually a substring (after whitespace/case normalization). If not, the quote is dropped and the paper is marked `verified=false` and shown with a "not verified" hint. This is the main guard against hallucinated findings, and it lets users check any claim in one glance.

**The question is explicit and shown**
"Supports" only means something relative to a question. The extraction call first rewrites the query as a yes/no evidence question ("Does metformin alter gut microbiome composition in humans or animals?") or declares the query a topic (`answerable=false`, e.g. "CRISPR off-target rates"). The UI shows "Measured against: ..." so stance labels are interpretable. For topic queries, stance UI is hidden and the timeline colors by design instead.

**One extraction call per query, batched, capped at 30 papers**
Papers are already sorted by relevance; extract the top 30 that have abstracts. Split into batches of 10 run in parallel (bounded latency, one bad response only loses 10 papers). Structured JSON output with a response schema, validated with Pydantic. Expected cost per query: ~15k input / ~5k output tokens on a Flash model; ~5 to 10 s added latency, shown as its own pipeline step.

**New Gemini code uses `google-genai`, not `vertexai.generative_models`**
The current SDK path logs a deprecation warning (the module is scheduled for removal) and `VertexAIClient.generate_text()` calls the synchronous `generate_content` inside an async function, which blocks the event loop for the whole generation. `google-genai` is already in `requirements.txt`, supports Vertex AI (`vertexai=True`), async (`client.aio`), and `response_schema` for structured output. New `GeminiClient` wraps it; synthesis moves to it too. `VertexAIClient` stays for any remaining callers until removed.

**Evidence lives in `result_json`, no migration**
`Query.result_json` already stores the full `QueryResponse`, so reopening a past query restores the evidence panel for free. No new columns in v1. (A per-paper extraction cache is a later phase.)

**Drop the trend chart from the results page; keep the endpoint**
The findings timeline replaces it. `GET /api/v1/trends` stays (cheap, may power a "monitor this topic" feature later). Remove `TrendChart.tsx`; recharts stays because the timeline uses it.

**iCite for influence, not for ranking (yet)**
iCite (NIH, free, no key) returns citation count and Relative Citation Ratio per PMID in one batched call, plus human/animal fractions used as an organism fallback. v1 displays citations on cards and lets the user sort by "strongest evidence". It does not silently re-weight stance counts; weighting is a later, explicit toggle.

---

## Phase 0: Verify the APIs (half a day, before writing feature code)

None of these could be called from the cloud session that wrote this plan, so confirm against real data first:

1. **PubMed EFetch XML** for ~20 PMIDs from a real query: confirm `PublicationTypeList`, `MeshHeadingList`, `AbstractText@Label`, `DataBankList` shapes. Save 3 to 4 responses as test fixtures (`tests/fixtures/pubmed_*.xml`): a structured abstract, an RCT, an animal study, a record with inline `<i>`/`<sup>` markup.
2. **iCite**: `GET https://icite.od.nih.gov/api/pubs?pmids=<comma list>`; confirm field names (`citation_count`, `relative_citation_ratio`, `human`, `animal`, `molecular_cellular`), batch limit, behavior for brand-new PMIDs. Save a fixture.
3. **Gemini structured output** via `google-genai` on Vertex AI with the response schema below, on 10 real abstracts. Check quote-verification pass rate (target > 90%) and eyeball stance accuracy.
4. **Europe PMC preprint search** from the previous feature: confirm it returns real bioRxiv/medRxiv hits (it was never tested live).

Go/no-go: if quote verification is poor, lower temperature, shorten batches to 5, and tighten the prompt before building UI.

---

## Files Changed

| File | Change |
|------|--------|
| `src/external/data_parser.py` | Parse publication types, MeSH, labeled abstract sections, trial IDs; fix inline-markup loss |
| `src/external/icite_client.py` | **New**: `ICiteClient` (aiohttp, injectable session) |
| `src/services/gemini_client.py` | **New**: thin async wrapper over `google-genai` (text + JSON-schema generation) |
| `src/services/evidence_extractor.py` | **New**: question framing + per-paper extraction + quote verification |
| `src/services/evidence_aggregator.py` | **New**: deterministic counts, timeline buckets, gap facts |
| `src/utils/study_design.py` | **New**: PublicationType → design mapping, MeSH → organism rules, design tiers |
| `src/models/response_models.py` | `PaperResult`: metadata + `evidence`; `QueryResponse.evidence_summary` |
| `src/agents/bioinfo_agent.py` | New steps: enrich (iCite) + extract, aggregate, grounded synthesis |
| `src/agents/response_synthesizer.py` | Rewrite: prompt from extraction table + facts, `[n]` citations, citation sanitizer |
| `src/api/routes/websocket.py` | Docstring: new `extracting_evidence` event |
| `src/api/routes/query.py` | `regenerate_summary` rebuilds papers incl. evidence fields from `result_json` |
| `bioinfo-frontend/src/types/api.types.ts` | `Evidence`, `EvidenceSummary`, new `PaperResult` fields, `extracting_evidence` step |
| `bioinfo-frontend/src/components/EvidencePanel.tsx` | **New** |
| `bioinfo-frontend/src/components/FindingsTimeline.tsx` | **New** (recharts scatter, wrapped in `ErrorBoundary fallback={null}`, lazy-loaded) |
| `bioinfo-frontend/src/components/PaperCard.tsx` | Evidence row, citation count, `id="paper-n"` anchor |
| `bioinfo-frontend/src/components/AISynthesis.tsx` | Render `[n]` as links that scroll to the paper |
| `bioinfo-frontend/src/components/PipelineSteps.tsx`, `hooks/useWebSocket.ts` | Add `extracting_evidence` |
| `bioinfo-frontend/src/pages/HomePage.tsx` | Replace trend chart with panel + timeline; "Strongest evidence" sort |
| `bioinfo-frontend/src/components/TrendChart.tsx` | **Delete** |
| `tests/fixtures/*.xml`, `tests/fixtures/icite_*.json` | **New** (from Phase 0) |
| `tests/test_data_parser.py`, `test_study_design.py`, `test_icite_client.py`, `test_evidence_extractor.py`, `test_evidence_aggregator.py`, `test_response_synthesizer.py` | **New** |

---

## Step-by-Step Implementation

### 1. Parser (`src/external/data_parser.py`)

Add to `PubMedArticle`:
```python
publication_types: List[str]          # e.g. ["Journal Article", "Randomized Controlled Trial"]
mesh_terms: List[str]                 # DescriptorName text, e.g. ["Humans", "Metformin", "Gastrointestinal Microbiome"]
abstract_sections: Dict[str, str]     # {"BACKGROUND": ..., "RESULTS": ...}; {} for unstructured
trial_ids: List[str]                  # NCT numbers from DataBankList/AccessionNumber
has_abstract: bool
```

Fixes:
- Use `"".join(elem.itertext())` for `ArticleTitle` and each `AbstractText`. `elem.text` drops everything after the first inline tag (`<i>`, `<sup>`), silently truncating abstracts today.
- Read `AbstractText@Label` into `abstract_sections`; keep the joined `abstract` as now.
- Set `has_abstract=False` instead of relying on the `"No abstract available"` placeholder string (keep the placeholder for display compatibility).

### 2. Design and organism rules (`src/utils/study_design.py`)

```python
StudyDesign = Literal["meta_analysis", "systematic_review", "rct", "clinical_trial",
                      "cohort", "case_control", "cross_sectional", "case_report",
                      "review", "animal", "in_vitro", "other"]
Organism = Literal["human", "animal", "in_vitro", "mixed", "unknown"]

PUBTYPE_TO_DESIGN = [  # first match wins, most specific first
    ("Meta-Analysis", "meta_analysis"),
    ("Systematic Review", "systematic_review"),
    ("Randomized Controlled Trial", "rct"),
    ("Clinical Trial", "clinical_trial"),   # also matches "Clinical Trial, Phase III" via startswith
    ("Observational Study", "cohort"),
    ("Case Reports", "case_report"),
    ("Review", "review"),
]

DESIGN_TIER = {"meta_analysis": 1, "systematic_review": 1, "rct": 2, "clinical_trial": 3,
               "cohort": 4, "case_control": 4, "cross_sectional": 5, "animal": 6,
               "in_vitro": 7, "case_report": 7, "review": 8, "other": 9}

def design_from_pubtypes(pubtypes: List[str]) -> Optional[StudyDesign]: ...
def organism_from_mesh(mesh: List[str]) -> Optional[Organism]:
    # "Humans" only -> human; "Animals" (or Mice/Rats/...) only -> animal; both -> mixed; neither -> None
def organism_from_icite(human: float, animal: float, molecular_cellular: float) -> Optional[Organism]:
    # dominant fraction >= 0.6 wins, else None
```
Precedence: design = pubtypes → Gemini; organism = MeSH → iCite → Gemini. Record the source (`"pubmed"`, `"icite"`, `"ai"`) so the UI can show where a label came from.

### 3. iCite client (`src/external/icite_client.py`)

Same shape as `PreprintClient`: injectable `aiohttp.ClientSession`, 10 s timeout, never raises.
```python
@dataclass
class CitationInfo:
    pmid: str
    citation_count: int
    relative_citation_ratio: Optional[float]
    human: float; animal: float; molecular_cellular: float

class ICiteClient:
    async def fetch(self, pmids: List[str]) -> Dict[str, CitationInfo]  # batched (verify limit in Phase 0)
```

### 4. Gemini client (`src/services/gemini_client.py`)

```python
class GeminiClient:
    def __init__(self, project_id, location, model_name): ...   # genai.Client(vertexai=True, ...)
    @property
    def available(self) -> bool
    async def generate_text(self, prompt, temperature=0.3, max_tokens=2048) -> Optional[str]
    async def generate_json(self, prompt, schema: Type[BaseModel], temperature=0.1) -> Optional[BaseModel]
        # client.aio.models.generate_content(config={"response_mime_type": "application/json",
        #                                            "response_schema": schema, ...})
        # returns None on any failure; logs it
def get_gemini_client() -> GeminiClient   # singleton, lazy, mirrors get_embedding_service()
```

### 5. Extraction (`src/services/evidence_extractor.py`)

Schemas (Pydantic; also used as the Gemini `response_schema`):
```python
class PaperEvidence(BaseModel):
    index: int                                  # 1-based position in the batch prompt
    design: StudyDesign
    organism: Organism
    sample_size: Optional[int]                  # null if not stated; never guessed
    population: Optional[str]                   # "adults with T2D", "C57BL/6 mice"
    intervention: Optional[str]
    outcome: Optional[str]
    stance: Literal["supports", "contradicts", "mixed", "no_effect", "not_applicable"]
    key_finding: str                            # <= 25 words, plain language
    finding_quote: str                          # verbatim sentence/clause from the abstract

class FramedQuestion(BaseModel):
    question: str
    answerable: bool                            # false for topic queries

class ExtractionBatch(BaseModel):
    papers: List[PaperEvidence]
```

Flow:
1. `frame_question(query) -> FramedQuestion`: one small call (or fold into batch 1; measure in Phase 0).
2. `extract(question, papers) -> List[Optional[Evidence]]`:
   - Take the top 30 papers with `has_abstract`; batches of 10 via `asyncio.gather`.
   - Prompt per batch: the question, then `[1] Title / Publication types / MeSH / Abstract (with section labels)`, ... Rules in the prompt: use only the abstract; `sample_size` null unless a number is stated; quote must be copied exactly; `not_applicable` when the paper doesn't address the question; preprints are not peer reviewed (no effect on stance, just context).
   - Validate: drop items with out-of-range `index` or duplicate index; verify `finding_quote` is a normalized substring of the abstract, else blank it and `verified=False`.
   - Override `design` / `organism` with PubMed/iCite values when available (step 2 precedence), recording `design_source` / `organism_source`.
3. Any batch failure returns `None` for its papers; the page still renders without evidence for them.

Stored on `PaperResult`:
```python
class Evidence(BaseModel):
    design: StudyDesign; design_source: Literal["pubmed", "ai"]
    organism: Organism; organism_source: Literal["pubmed", "icite", "ai"]
    sample_size: Optional[int]
    population: Optional[str]; intervention: Optional[str]; outcome: Optional[str]
    stance: ...; key_finding: str
    finding_quote: Optional[str]; verified: bool

class PaperResult(BaseModel):
    ...existing...
    publication_types: List[str] = []
    mesh_terms: List[str] = []
    trial_ids: List[str] = []
    citation_count: Optional[int] = None
    relative_citation_ratio: Optional[float] = None
    evidence: Optional[Evidence] = None
```

### 6. Aggregation (`src/services/evidence_aggregator.py`)

Pure functions, no I/O:
```python
class EvidenceSummary(BaseModel):
    question: str
    answerable: bool
    papers_with_evidence: int
    stance_counts: Dict[str, int]                       # over all
    stance_by_organism: Dict[str, Dict[str, int]]       # {"human": {...}, "animal": {...}}
    design_counts: Dict[str, int]
    by_year: List[Dict]                                 # [{year, supports, contradicts, ...}]
    gaps: List[str]                                     # machine-generated facts, see below
    largest_study: Optional[Dict]                       # {index, n, design}
    latest_rct_year: Optional[int]
    preprint_count: int
```
Gap facts (each a short sentence the synthesis may use verbatim):
- No RCTs / meta-analyses among the results.
- No human studies; or human evidence only from studies with n < 50.
- Latest RCT is older than 5 years.
- Human and animal evidence point in opposite directions (majority stance differs).
- Stance shifted over time (majority before vs after the median year differs).
- More than half of supporting evidence is from preprints.

### 7. Agent pipeline (`src/agents/bioinfo_agent.py`)

```
classify
→ searching_pubmed / searching_preprints   (parallel, unchanged)
→ retrieving_abstracts                     (merge, dedup, cap, unchanged)
→ scoring_relevance                        (unchanged; decides which 30 get extracted)
→ extracting_evidence                      gather(icite.fetch(pmids), extractor.frame_question + extract)
                                            → attach citations + evidence → aggregate
→ synthesizing                             grounded synthesis
→ done                                     QueryResponse(..., evidence_summary=...)
```
If Gemini is unavailable, skip extraction (no event), `evidence_summary=None`, synthesis falls back to today's behavior.

### 8. Grounded synthesis (`src/agents/response_synthesizer.py`)

- Input: question, the numbered table (index, year, design, organism, n, stance, key finding, source) for papers with evidence, plus `EvidenceSummary` numbers and gap facts.
- Prompt asks for 3 short paragraphs: where the evidence points (with counts from the facts, not recounted), where and why studies disagree (population, design, dose, era), what is missing. Cite as `[n]` matching the paper list order shown in the UI.
- `sanitize_citations(text, n_papers)`: remove `[k]` where k is out of range; collapse duplicates.
- Topic queries (`answerable=false`): themes and how methods/results changed over time instead of stance.
- Uses `GeminiClient.generate_text` (async; fixes the event-loop blocking).

Citation numbering must match the UI order. Number by the backend's relevance order and have the frontend display that number on each card (it does not change when the user re-sorts).

### 9. Frontend

**`EvidencePanel.tsx`** (between AI synthesis and paper list)
- "Measured against: <question>" (hidden for topic queries).
- Stacked horizontal stance bar with counts; filter chips All / Human / Animal / In vitro (client-side from `stance_by_organism`).
- Design chips: "2 meta-analyses · 4 RCTs · 9 cohort · 6 animal".
- Gaps list (amber, from `gaps`).

**`FindingsTimeline.tsx`** (lazy-loaded, error-bounded)
- recharts `ScatterChart`: x = year, y = stance lane (supports / mixed / no effect / contradicts) with small jitter; color = organism; radius ∝ log(sample_size) (unknown n = small fixed dot); preprints hollow.
- Tooltip: title, design, n, key finding. Click scrolls to `#paper-n`.
- Topic queries: y = design tier instead of stance.

**`PaperCard.tsx`**
- Show the paper's citation number `[n]`.
- Evidence row: design chip, organism chip, `n = 1,240`, stance chip, key finding; the quote on hover/expand; "not verified" marker when `verified=false`; small "AI" marker when design/organism came from Gemini.
- Citations: "212 citations · RCR 3.1" for PubMed papers with iCite data.

**`AISynthesis.tsx`**: render `[n]` as buttons that scroll to `#paper-n` and briefly highlight it.

**`HomePage.tsx`**: remove trend fetch/chart; add panel + timeline; add sort "Strongest evidence" = design tier, then sample size, then RCR.

---

## Later Phases (out of scope for v1)

1. **Extraction cache**: table keyed by PMID/DOI + extractor version for question-independent fields (design, organism, n, population, finding); only stance is recomputed per query. Cuts cost and latency for repeated topics.
2. **ClinicalTrials.gov enrichment**: for papers with `trial_ids`, pull registered enrollment, phase, primary outcome; surface registered-but-unpublished trials as a gap.
3. **PubTator3 entities**: genes/variants/chemicals/diseases per paper without LLM calls; could feed the existing variant scoring.
4. **Open-access full text** (PMC / Europe PMC) for doses and effect sizes on papers where it is available.
5. **Editable question**: let users correct the framed question and re-run stance only.
6. **Weighted view**: optional toggle weighting stance by design tier and RCR, clearly labeled.

---

## Testing Plan

**`test_data_parser.py`** (fixtures from Phase 0): publication types, MeSH, labeled sections, trial IDs parsed; inline `<i>` no longer truncates title/abstract; missing abstract → `has_abstract=False`.

**`test_study_design.py`**: pubtype precedence (Meta-Analysis beats Review; "Clinical Trial, Phase III" → clinical_trial); MeSH organism rules (Humans / Animals / both / neither); iCite fallback thresholds.

**`test_icite_client.py`** (mock session, same pattern as `test_preprint_client.py`): parses fixture; HTTP error → `{}`; batches large PMID lists; unknown PMID absent from result.

**`test_evidence_extractor.py`** (fake `GeminiClient`): quote verified when substring, blanked + `verified=False` when not; out-of-range/duplicate index dropped; PubMed design/organism override AI values with correct `*_source`; failed batch → `None` for its papers only; only top 30 with abstracts are sent; papers without abstracts skipped.

**`test_evidence_aggregator.py`**: counts by stance/organism/design; each gap rule fires and doesn't fire; `by_year` buckets; topic query (`answerable=False`) skips stance-based gaps.

**`test_response_synthesizer.py`**: prompt contains the computed counts (not raw abstracts); `sanitize_citations` removes out-of-range refs; fallback path when evidence is missing.

**Agent pipeline** (extend `test_bioinfo_agent_dedup.py`): event order includes `extracting_evidence`; evidence and citations attached to the right papers; Gemini unavailable → no event, `evidence_summary=None`, response still valid.

---

## Verification Checklist

1. Phase 0 results recorded (fixtures saved, quote-verification rate, stance spot-check on 10 papers).
2. `pytest` and `ruff` pass; `npx tsc --noEmit` and `npm run build` pass.
3. Live query "metformin gut microbiome": event order `classifying → searching_pubmed → searching_preprints → retrieving_abstracts → scoring_relevance → extracting_evidence → synthesizing → done`; added latency under ~10 s.
4. Response: `evidence_summary` present; counts equal a manual count of the papers' `evidence.stance`; every non-null `finding_quote` appears in its abstract.
5. UI: panel shows question, stance bar, filters change counts; timeline dots click through to the right card; synthesis `[n]` links land on the right card; cards show design / n / stance / citations.
6. Topic query ("CRISPR off-target rates"): no stance UI; timeline by design; synthesis describes themes.
7. Vertex AI disabled (no project): page renders papers as before, no evidence panel, no crash.
8. Reopen the query from history: panel and timeline restored from `result_json`.
