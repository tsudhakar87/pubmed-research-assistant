import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { PaperResult, VariantMention } from '../types/api.types';
import { VariantScoringModal } from './VariantScoringModal';

interface Props {
  paper: PaperResult;
  onSelectForCompare?: (pmid: string, selected: boolean) => void;
  selectedForCompare?: boolean;
}

function highlightVariants(text: string, variants: VariantMention[]): React.ReactNode {
  if (!variants.length) return text;
  const notations = variants.map((v) => v.notation.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const regex = new RegExp(`(${notations.join('|')})`, 'g');
  const parts = text.split(regex);
  return parts.map((part, i) =>
    notations.some((n) => new RegExp(`^${n}$`).test(part)) ? (
      <mark key={i} style={{ background: '#faf0dc', color: '#8a5c1a', padding: '0 2px', borderRadius: 2 }}>
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

export function PaperCard({ paper, onSelectForCompare, selectedForCompare }: Props) {
  const navigate = useNavigate();
  const [scoringOpen, setScoringOpen] = useState(false);
  const [scoringVariant, setScoringVariant] = useState<VariantMention | null>(null);

  const variants = paper.detected_variants ?? [];
  const primaryVariant = variants[0];
  const abstract = paper.abstract ?? '';
  const snippet = abstract.length > 220 ? abstract.slice(0, 220) + '…' : abstract;

  function openVariantScore(v: VariantMention) {
    setScoringVariant(v);
    setScoringOpen(true);
  }

  return (
    <>
      <div style={{ padding: '16px 0', borderBottom: '1px solid #dbd6c8' }}>
        {onSelectForCompare && (
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={selectedForCompare}
              onChange={(e) => onSelectForCompare(paper.pmid ?? '', e.target.checked)}
            />
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#9aa1ab' }}>
              Compare
            </span>
          </label>
        )}

        <div style={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: 12,
          marginBottom: 5,
        }}>
          <div
            style={{
              fontFamily: 'var(--font-serif)',
              fontWeight: 600,
              fontSize: 16.5,
              lineHeight: 1.4,
              color: '#1c2430',
              cursor: 'pointer',
            }}
            onClick={() => paper.pmid && navigate(`/paper/${paper.pmid}`)}
          >
            {paper.title}
          </div>
          {paper.pmid && (
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10.5,
              color: '#9aa1ab',
              whiteSpace: 'nowrap',
              flexShrink: 0,
            }}>
              PMID {paper.pmid}
            </div>
          )}
        </div>

        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          color: '#5c6470',
          marginBottom: 8,
        }}>
          {paper.journal && <span style={{ color: '#155c51' }}>{paper.journal}</span>}
          {paper.journal && paper.authors.length > 0 && ' · '}
          {paper.authors.slice(0, 3).join(', ')}
          {paper.authors.length > 3 && ' et al.'}
          {paper.publication_date && ` · ${paper.publication_date.slice(0, 4)}`}
        </div>

        {snippet && (
          <div style={{ fontSize: 13.5, lineHeight: 1.6, color: '#5c6470', marginBottom: 10 }}>
            {highlightVariants(snippet, variants)}
          </div>
        )}

        <div style={{ display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
          {paper.pmid && (
            <a
              href={`https://pubmed.ncbi.nlm.nih.gov/${paper.pmid}/`}
              target="_blank"
              rel="noopener noreferrer"
              style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: '#9aa1ab' }}
            >
              ↗ full text
            </a>
          )}
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: '#9aa1ab', cursor: 'pointer' }}>
            ❝ cite
          </span>
          <span
            style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: '#9aa1ab', cursor: 'pointer' }}
            onClick={() => paper.pmid && navigate(`/paper/${paper.pmid}`)}
          >
            ⟟ find similar
          </span>

          {primaryVariant && paper.pmid && (
            <button
              onClick={() => openVariantScore(primaryVariant)}
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
              ⬡ score variant — {primaryVariant.gene ? `${primaryVariant.gene} ` : ''}{primaryVariant.notation}
            </button>
          )}
        </div>
      </div>

      {scoringOpen && paper.pmid && scoringVariant && (
        <VariantScoringModal
          pmid={paper.pmid}
          variant={scoringVariant}
          onClose={() => setScoringOpen(false)}
        />
      )}
    </>
  );
}
