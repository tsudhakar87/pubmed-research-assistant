import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { comparePapers } from '../services/api';
import { Header } from '../components/Header';
import type { CompareResult } from '../types/api.types';

export function PaperComparePage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const pmids = (params.get('pmids') ?? '').split(',').filter(Boolean);

  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (pmids.length < 2) {
      setError('Need at least 2 PMIDs to compare');
      setLoading(false);
      return;
    }
    comparePapers(pmids)
      .then(setResult)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ maxWidth: 1040, margin: '0 auto', background: '#fff', border: '1px solid #dbd6c8', borderRadius: 3, boxShadow: '0 1px 2px rgba(28,36,48,.04), 0 18px 40px rgba(28,36,48,.08)', minHeight: '100vh' }}>
      <Header />

      <div style={{ padding: '18px 34px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap' }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: '#1f7a6c', cursor: 'pointer' }} onClick={() => navigate(-1)}>
          ← back to results
        </span>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#5c6470', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 9, height: 9, borderRadius: 2, background: '#faf0dc', border: '1px solid #e8cf9e', display: 'inline-block' }} />
            diverging claim
          </span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#5c6470', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 9, height: 9, borderRadius: 2, background: '#e1efec', border: '1px solid #c3ddd6', display: 'inline-block' }} />
            agreeing claim
          </span>
        </div>
      </div>

      <div style={{ padding: '20px 34px 8px' }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#9aa1ab', marginBottom: 9 }}>
          Comparing {pmids.length} papers
        </div>

        {loading && (
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: '#9aa1ab', padding: '12px 0' }}>
            Generating AI diff synthesis…
          </div>
        )}

        {error && (
          <div style={{ color: '#8a5c1a', fontFamily: 'var(--font-mono)', fontSize: 12 }}>{error}</div>
        )}

        {result && (
          <>
            {/* AI Diff Synthesis */}
            <div style={{
              borderLeft: '3px solid #c98a2e',
              background: '#faf0dc',
              borderRadius: '0 6px 6px 0',
              padding: '16px 18px',
              marginBottom: 8,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#8a5c1a', fontWeight: 600 }}>
                  AI Diff Synthesis
                </span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#9aa1ab' }}>gemini-2.5-flash</span>
              </div>
              <div style={{ fontSize: 14, lineHeight: 1.65, color: '#1c2430', whiteSpace: 'pre-wrap' }}>
                {result.ai_diff_synthesis}
              </div>
            </div>

            {/* Side-by-side papers */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${result.papers.length}, 1fr)`,
              gap: 0,
              padding: '8px 0 30px',
            }}>
              {result.papers.map((paper, i) => (
                <div
                  key={paper.pmid}
                  style={{
                    padding: '14px 20px 0',
                    borderRight: i < result.papers.length - 1 ? '1px solid #dbd6c8' : 'none',
                    paddingLeft: i > 0 ? 20 : 0,
                    paddingRight: i < result.papers.length - 1 ? 20 : 0,
                  }}
                >
                  <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 600, fontSize: 16, lineHeight: 1.4, color: '#1c2430', marginBottom: 6 }}>
                    {paper.title}
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: '#9aa1ab', marginBottom: 14 }}>
                    PMID {paper.pmid}
                    {paper.journal && <> · <span style={{ color: '#155c51' }}>{paper.journal}</span></>}
                    {paper.authors?.[0] && ` · ${paper.authors[0].split(' ').pop()}`}
                    {paper.publication_date && ` · ${paper.publication_date.slice(0, 4)}`}
                  </div>
                  <div style={{ fontSize: 13, lineHeight: 1.7, color: '#1c2430' }}>
                    {paper.abstract.slice(0, 600)}
                    {paper.abstract.length > 600 && '…'}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
