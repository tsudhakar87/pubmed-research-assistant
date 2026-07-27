import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getPaper } from '../services/api';
import { Header } from '../components/Header';
import { VariantScoringModal } from '../components/VariantScoringModal';
import type { PaperDetail, VariantMention } from '../types/api.types';

export function PaperDetailPage() {
  const { pmid } = useParams<{ pmid: string }>();
  const navigate = useNavigate();
  const [paper, setPaper] = useState<PaperDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [scoringVariant, setScoringVariant] = useState<VariantMention | null>(null);

  useEffect(() => {
    if (!pmid) return;
    getPaper(pmid)
      .then(setPaper)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [pmid]);

  if (loading) {
    return (
      <div style={{ maxWidth: 860, margin: '0 auto', background: '#fff', border: '1px solid #dbd6c8', borderRadius: 3, minHeight: '100vh' }}>
        <Header />
        <div style={{ padding: '40px 34px', color: '#9aa1ab', fontFamily: 'var(--font-mono)', fontSize: 12 }}>Loading…</div>
      </div>
    );
  }

  if (error || !paper) {
    return (
      <div style={{ maxWidth: 860, margin: '0 auto', background: '#fff', border: '1px solid #dbd6c8', borderRadius: 3, minHeight: '100vh' }}>
        <Header />
        <div style={{ padding: '40px 34px', color: '#8a5c1a', fontFamily: 'var(--font-mono)', fontSize: 12 }}>{error || 'Paper not found'}</div>
      </div>
    );
  }

  const primaryVariant = paper.detected_variants[0];

  return (
    <>
      <div style={{ maxWidth: 860, margin: '0 auto', background: '#fff', border: '1px solid #dbd6c8', borderRadius: 3, boxShadow: '0 1px 2px rgba(28,36,48,.04), 0 18px 40px rgba(28,36,48,.08)', minHeight: '100vh' }}>
        <Header />

        <div style={{ padding: '18px 34px 0' }}>
          <span
            style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: '#1f7a6c', cursor: 'pointer' }}
            onClick={() => navigate(-1)}
          >
            ← back to results
          </span>
        </div>

        <div style={{ padding: '20px 34px 30px', display: 'grid', gridTemplateColumns: '1fr 240px', gap: 0 }}>
          <div style={{ paddingRight: 30 }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: '#9aa1ab', marginBottom: 10 }}>
              PMID {paper.pmid}
              {paper.journal && <> · <span style={{ color: '#155c51' }}>{paper.journal}</span></>}
              {paper.publication_date && ` · ${paper.publication_date.slice(0, 4)}`}
            </div>

            <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 600, fontSize: 26, lineHeight: 1.3, color: '#1c2430', marginBottom: 12 }}>
              {paper.title}
            </div>

            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5, color: '#5c6470', marginBottom: 18 }}>
              {paper.authors.slice(0, 4).join(', ')}
              {paper.authors.length > 4 && ' et al.'}
            </div>

            {paper.keywords.length > 0 && (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 22 }}>
                {paper.keywords.map((kw) => (
                  <span key={kw} style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#5c6470', border: '1px solid #dbd6c8', borderRadius: 12, padding: '4px 10px' }}>
                    {kw}
                  </span>
                ))}
              </div>
            )}

            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#9aa1ab', display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              Abstract
              <div style={{ flex: 1, height: 1, background: '#dbd6c8' }} />
            </div>

            <div style={{ fontSize: 14, lineHeight: 1.75, color: '#1c2430', marginBottom: 24 }}>
              {paper.abstract}
            </div>

            <div style={{ display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
              <a href={paper.pubmed_url} target="_blank" rel="noopener noreferrer" style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: '#9aa1ab' }}>
                ↗ full text
              </a>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: '#9aa1ab', cursor: 'pointer' }}>❝ cite</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: '#9aa1ab', cursor: 'pointer' }}>⟟ find similar</span>
              {primaryVariant && (
                <button
                  onClick={() => setScoringVariant(primaryVariant)}
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10.5,
                    fontWeight: 600,
                    letterSpacing: '0.03em',
                    color: '#4f4171',
                    border: '1px solid #d7d0e6',
                    background: '#ece9f4',
                    padding: '4px 9px',
                    borderRadius: 3,
                    cursor: 'pointer',
                  }}
                >
                  ⬡ score variant — {primaryVariant.gene && `${primaryVariant.gene} `}{primaryVariant.notation}
                </button>
              )}
            </div>
          </div>

          <div style={{ paddingLeft: 26, borderLeft: '1px solid #dbd6c8' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#9aa1ab', marginBottom: 12 }}>
              Citation
            </div>
            <div style={{ fontSize: 11.5, lineHeight: 1.6, color: '#5c6470', padding: '10px 12px', border: '1px dashed #dbd6c8', borderRadius: 6, marginBottom: 24 }}>
              {paper.authors[0]?.split(' ').pop() ?? 'Author'} et al. ({paper.publication_date?.slice(0, 4) ?? 'n.d.'}). {paper.title}.{paper.journal && <> <em>{paper.journal}</em>.</>}
            </div>

            {paper.detected_variants.length > 0 && (
              <>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#9aa1ab', marginBottom: 10 }}>
                  Detected variants
                </div>
                {paper.detected_variants.map((v, i) => (
                  <div key={i} style={{ padding: '7px 0', borderBottom: '1px solid #dbd6c8', fontSize: 12.5, color: '#5c6470', fontFamily: 'var(--font-mono)' }}>
                    {v.gene && `${v.gene} `}{v.notation}
                    <span style={{ display: 'block', fontSize: 10, color: '#9aa1ab', marginTop: 2 }}>{v.type}</span>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      </div>

      {scoringVariant && (
        <VariantScoringModal
          pmid={paper.pmid}
          variant={scoringVariant}
          onClose={() => setScoringVariant(null)}
        />
      )}
    </>
  );
}
