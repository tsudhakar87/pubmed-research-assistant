import { lazy, Suspense, useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useWebSocket } from '../hooks/useWebSocket';
import { Header } from '../components/Header';
import { SearchBar } from '../components/SearchBar';
import { PipelineSteps } from '../components/PipelineSteps';
import { AISynthesis } from '../components/AISynthesis';
import { PaperCard } from '../components/PaperCard';
import { PaperSkeleton } from '../components/LoadingSpinner';
import { EvidencePanel } from '../components/EvidencePanel';
import { compareEvidenceStrength } from '../components/evidenceStyles';
import { HISTORY_CLEARED_EVENT, getQueryHistory, reopenQuery, regenerateSummary } from '../services/api';
import type { HistoryItem, PaperResult } from '../types/api.types';

// recharts is large; load it only when there's a chart to show
const FindingsTimeline = lazy(() =>
  import('../components/FindingsTimeline').then((m) => ({ default: m.FindingsTimeline })),
);

const EXAMPLE_QUERIES = [
  'metformin and gut microbiome',
  'GLP-1 agonists cardiovascular outcomes',
  'CRISPR off-target rates',
];

type SortOrder = 'relevance' | 'evidence' | 'newest' | 'oldest';

function sortPapers(papers: PaperResult[], order: SortOrder): PaperResult[] {
  const copy = [...papers];
  if (order === 'relevance') {
    // ref is the backend's ranking (relevance, then unscored papers), and what citations use
    return copy.sort((a, b) =>
      a.ref != null && b.ref != null
        ? a.ref - b.ref
        : (b.relevance_score ?? 0) - (a.relevance_score ?? 0));
  }
  if (order === 'evidence') {
    return copy.sort(compareEvidenceStrength);
  }
  if (order === 'newest') {
    return copy.sort((a, b) => {
      const da = a.publication_date ? new Date(a.publication_date).getTime() : 0;
      const db = b.publication_date ? new Date(b.publication_date).getTime() : 0;
      return db - da;
    });
  }
  // oldest
  return copy.sort((a, b) => {
    const da = a.publication_date ? new Date(a.publication_date).getTime() : 0;
    const db = b.publication_date ? new Date(b.publication_date).getTime() : 0;
    return da - db;
  });
}

export function HomePage() {
  const { token, signOut } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { step, result, error, isRunning, earlyPapers, submitQuery, loadCachedResult } = useWebSocket(signOut);

  const [selectedForCompare, setSelectedForCompare] = useState<Set<string>>(new Set());
  const [sortOrder, setSortOrder] = useState<SortOrder>('relevance');
  const [recentQueries, setRecentQueries] = useState<HistoryItem[]>([]);
  const [searchValue, setSearchValue] = useState('');
  const [highlightedRef, setHighlightedRef] = useState<number | null>(null);
  const [aiCollapsed, setAiCollapsed] = useState(false);
  const [page, setPage] = useState(1);

  const PAGE_SIZE = 10;

  // Jump to a paper from a [n] citation or a timeline dot, and tint it briefly
  function goToPaper(ref: number) {
    requestAnimationFrame(() => {
      document.getElementById(`paper-${ref}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
    setHighlightedRef(ref);
  }

  useEffect(() => {
    if (highlightedRef == null) return;
    const t = setTimeout(() => setHighlightedRef(null), 1600);
    return () => clearTimeout(t);
  }, [highlightedRef]);

  // Fetch query history for sidebar
  useEffect(() => {
    if (!token) return;
    getQueryHistory(10)
      .then((data) => setRecentQueries(data.queries))
      .catch(() => {/* DB may not be set up — silently ignore */});
  }, [token, result]); // refetch after each new result

  useEffect(() => {
    const onCleared = () => setRecentQueries([]);
    window.addEventListener(HISTORY_CLEARED_EVENT, onCleared);
    return () => window.removeEventListener(HISTORY_CLEARED_EVENT, onCleared);
  }, []);

  // Load cached result when navigated to with ?reopen=queryId
  useEffect(() => {
    const queryId = searchParams.get('reopen');
    if (!queryId || !token) return;
    reopenQuery(queryId)
      .then((cached) => {
        loadCachedResult(cached);
        if (cached.original_query) setSearchValue(cached.original_query);
        setSearchParams({}, { replace: true }); // clean URL
      })
      .catch(() => {/* cached result unavailable — ignore */});
  }, [searchParams, token]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSubmit(query: string) {
    if (!token) return;
    setSearchValue(query);
    setSelectedForCompare(new Set());
    setSortOrder('relevance');
    setPage(1);
    submitQuery(query, token, 20);
  }

  function toggleCompare(pmid: string, selected: boolean) {
    setSelectedForCompare((prev) => {
      const next = new Set(prev);
      if (selected && next.size < 3) next.add(pmid);
      else next.delete(pmid);
      return next;
    });
  }

  const showSkeleton = isRunning && step !== 'done';
  const showResults = result || showSkeleton;
  const papers = sortPapers(result?.literature_results ?? earlyPapers, sortOrder);
  const totalPages = Math.ceil(papers.length / PAGE_SIZE);
  const pagedPapers = papers.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div style={{ minHeight: '100vh' }}>
      <Header />

      <div style={{ padding: '22px 34px 18px', borderBottom: '1px solid #dbd6c8' }}>
        <SearchBar value={searchValue} onChange={setSearchValue} onSubmit={handleSubmit} loading={isRunning} />
        {step !== 'idle' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 14 }}>
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: '#9aa1ab',
            }}>
              Analysis pipeline
            </span>
            <PipelineSteps currentStep={step} />
            {result?.metadata?.history_saved === false && (
              <span
                title="The results are complete, but saving them failed (check the backend logs)."
                style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--text-amber)' }}
              >
                not saved to history
              </span>
            )}
          </div>
        )}
      </div>

      {/* Pre-query state: full-width history list */}
      {!showResults && !error && (
        <div style={{ padding: '24px 34px 34px' }}>
          {recentQueries.length === 0 ? (
            <EmptyState onExampleClick={handleSubmit} />
          ) : (
            <RecentQueriesList queries={recentQueries} onSelect={handleSubmit} />
          )}
        </div>
      )}

      {error && (
        <div style={{ padding: '24px 34px', color: '#8a5c1a', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* Results state: two-column layout with sidebar */}
      {showResults && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 240px' }}>
          <div style={{ padding: '24px 34px 34px' }}>
          {showResults && (
            <>
            <AISynthesis
              summary={result?.ai_summary ?? null}
              loading={isRunning && step !== 'done'}
              sourcesCount={papers.length}
              onRegenerate={result?.query_id ? async () => {
                const { ai_summary } = await regenerateSummary(result.query_id);
                loadCachedResult({ ...result, ai_summary: ai_summary ?? result.ai_summary });
              } : undefined}
              onCite={goToPaper}
              collapsed={aiCollapsed}
              onToggleCollapsed={() => setAiCollapsed(c => !c)}
            />

            {!aiCollapsed && result?.evidence_summary && !showSkeleton && (
              <>
                <EvidencePanel summary={result.evidence_summary} />
                <Suspense fallback={null}>
                  <FindingsTimeline
                    papers={result.literature_results}
                    answerable={result.evidence_summary.answerable}
                    onSelect={goToPaper}
                  />
                </Suspense>
              </>
            )}

            {/* Papers header with sort controls */}
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10.5,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: '#9aa1ab',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              marginBottom: 14,
            }}>
              Papers{' '}
              <span style={{ color: '#5c6470', fontWeight: 600 }}>
                · {showSkeleton ? 'searching…' : `${papers.length} found`}
              </span>
              <div style={{ flex: 1, height: 1, background: '#dbd6c8' }} />

              {/* Sort controls */}
              {papers.length > 1 && !showSkeleton && (
                <SortPicker value={sortOrder} onChange={setSortOrder} hasEvidence={!!result?.evidence_summary} />
              )}

              {selectedForCompare.size >= 2 && (
                <button
                  onClick={() => navigate(`/compare?pmids=${[...selectedForCompare].join(',')}`)}
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10,
                    fontWeight: 600,
                    color: '#155c51',
                    background: '#e1efec',
                    border: '1px solid #c3ddd6',
                    borderRadius: 3,
                    padding: '3px 9px',
                    cursor: 'pointer',
                  }}
                >
                  Compare {selectedForCompare.size} →
                </button>
              )}
            </div>

            {showSkeleton && !papers.length ? (
              <>
                <PaperSkeleton />
                <PaperSkeleton />
                <PaperSkeleton />
              </>
            ) : (
              pagedPapers.map((paper, i) => (
                <PaperCard
                  key={paper.pmid ?? paper.doi ?? i}
                  paper={paper}
                  onSelectForCompare={toggleCompare}
                  selectedForCompare={selectedForCompare.has(paper.pmid ?? '')}
                  highlighted={paper.ref != null && paper.ref === highlightedRef}
                />
              ))
            )}

            {totalPages > 1 && !showSkeleton && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, padding: '18px 0 8px', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  style={{ background: 'transparent', border: '1px solid #dbd6c8', borderRadius: 3, padding: '4px 10px', cursor: page === 1 ? 'not-allowed' : 'pointer', color: page === 1 ? '#9aa1ab' : '#1c2430', fontFamily: 'var(--font-mono)', fontSize: 11 }}
                >← prev</button>
                <span style={{ color: '#9aa1ab' }}>{page} / {totalPages}</span>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  style={{ background: 'transparent', border: '1px solid #dbd6c8', borderRadius: 3, padding: '4px 10px', cursor: page === totalPages ? 'not-allowed' : 'pointer', color: page === totalPages ? '#9aa1ab' : '#1c2430', fontFamily: 'var(--font-mono)', fontSize: 11 }}
                >next →</button>
              </div>
            )}
            </>
          )}
          </div>

          <Sidebar recentQueries={recentQueries} />
        </div>
      )}
    </div>
  );
}

function SortPicker({ value, onChange, hasEvidence }: { value: SortOrder; onChange: (v: SortOrder) => void; hasEvidence: boolean }) {
  const allOptions: { label: string; value: SortOrder }[] = [
    { label: 'Relevance', value: 'relevance' },
    { label: 'Strongest evidence', value: 'evidence' },
    { label: 'Newest', value: 'newest' },
    { label: 'Oldest', value: 'oldest' },
  ];
  const options = allOptions.filter((o) => hasEvidence || o.value !== 'evidence');
  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 9.5,
            fontWeight: 600,
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
            padding: '2px 7px',
            borderRadius: 3,
            border: '1px solid',
            cursor: 'pointer',
            background: value === o.value ? '#1c2430' : 'transparent',
            color: value === o.value ? '#fff' : '#9aa1ab',
            borderColor: value === o.value ? '#1c2430' : '#dbd6c8',
            transition: 'all 0.1s',
          }}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function RecentQueriesList({ queries, onSelect }: { queries: HistoryItem[]; onSelect: (q: string) => void }) {
  const navigate = useNavigate();
  return (
    <div>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 10.5,
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        color: '#9aa1ab',
        marginBottom: 16,
        display: 'flex',
        alignItems: 'center',
        gap: 10,
      }}>
        Recent queries
        <div style={{ flex: 1, height: 1, background: '#dbd6c8' }} />
        <span
          style={{ color: '#1f7a6c', cursor: 'pointer', fontSize: 10, fontWeight: 600 }}
          onClick={() => navigate('/history')}
        >
          View all →
        </span>
      </div>
      {queries.map((q) => (
        <div
          key={q.query_id}
          style={{
            padding: '13px 0',
            borderBottom: '1px solid #dbd6c8',
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            cursor: 'pointer',
          }}
          onClick={() => onSelect(q.original_query)}
        >
          <div>
            <div style={{ fontFamily: 'var(--font-sans)', fontSize: 15, color: '#1c2430' }}>
              {q.original_query}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: '#9aa1ab', marginTop: 4 }}>
              {new Date(q.created_at).toLocaleString()}
              {q.total_results > 0 && ` · ${q.total_results} results`}
              {q.has_ai_summary && ' · ai summary'}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyState({ onExampleClick }: { onExampleClick: (q: string) => void }) {
  return (
    <div style={{ padding: '56px 34px 60px', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 6 }}>
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#9aa1ab" strokeWidth="1.5" style={{ marginBottom: 6 }}>
        <circle cx="11" cy="11" r="7" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <div style={{ fontFamily: 'var(--font-serif)', fontStyle: 'italic', fontWeight: 600, fontSize: 22, color: '#1c2430' }}>
        No queries yet
      </div>
      <div style={{ fontSize: 13.5, lineHeight: 1.6, color: '#5c6470', maxWidth: 380, marginBottom: 18 }}>
        Ask a question above and pub/med assistant will search PubMed and synthesize findings with Gemini. Your history will build up here.
      </div>

      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#9aa1ab', marginBottom: 10 }}>
        Try one of these
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', maxWidth: 460 }}>
        {EXAMPLE_QUERIES.map((q) => (
          <button
            key={q}
            onClick={() => onExampleClick(q)}
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: '#9aa1ab',
              border: '1px dashed #dbd6c8',
              borderRadius: 14,
              padding: '6px 12px',
              background: 'transparent',
              cursor: 'pointer',
            }}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

function Sidebar({ recentQueries }: { recentQueries: HistoryItem[] }) {
  const navigate = useNavigate();
  return (
    <div style={{ padding: '24px 22px 34px', borderLeft: '1px solid #dbd6c8' }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#9aa1ab', marginBottom: 12 }}>
        Recent queries
      </div>
      {recentQueries.length === 0 ? (
        <div style={{ fontSize: 11.5, lineHeight: 1.6, color: '#9aa1ab', fontFamily: 'var(--font-sans)' }}>
          Your queries will appear here.
        </div>
      ) : (
        recentQueries.map((q) => (
          <div
            key={q.query_id}
            style={{ padding: '9px 0', borderBottom: '1px solid #dbd6c8', cursor: 'pointer' }}
            onClick={() => navigate(`/?reopen=${q.query_id}`)}
          >
            <div style={{ fontSize: 12.5, lineHeight: 1.45, color: '#5c6470' }}>{q.original_query}</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#9aa1ab', marginTop: 3 }}>
              {new Date(q.created_at).toLocaleString()}
            </div>
          </div>
        ))
      )}

      <div
        style={{ marginTop: 16, fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: '#1f7a6c', cursor: 'pointer' }}
        onClick={() => navigate('/history')}
      >
        View full history →
      </div>
    </div>
  );
}
