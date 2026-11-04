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
  const isPreprint = paper.source === 'biorxiv' || paper.source === 'medrxiv';
  // Preprints have no PMID, so they link out by DOI instead of to the detail page
  const doiUrl = paper.doi ? `https://doi.org/${paper.doi}` : null;
  const fullTextUrl = paper.pmid ? `https://pubmed.ncbi.nlm.nih.gov/${paper.pmid}/` : doiUrl;

  function openPaper() {
    if (paper.pmid) navigate(`/paper/${paper.pmid}`);
    else if (doiUrl) window.open(doiUrl, '_blank', 'noopener,noreferrer');
  }

  function openVariantScore(v: VariantMention) {
    setScoringVariant(v);
    setScoringOpen(true);
  }

  return (
    <>
      <div style={{ padding: '16px 0', borderBottom: '1px solid #dbd6c8' }}>
        {onSelectForCompare && paper.pmid && (
          <label
            title="Select to compare side-by-side with other papers"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginBottom: 8, cursor: 'pointer' }}
          >
            <input
              type="checkbox"
              checked={selectedForCompare}
              onChange={(e) => onSelectForCompare(paper.pmid ?? '', e.target.checked)}
            />
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: selectedForCompare ? '#155c51' : '#9aa1ab',
              fontWeight: selectedForCompare ? 600 : 400,
            }}>
              {selectedForCompare ? 'Selected for compare' : 'Compare'}
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
              cursor: paper.pmid || doiUrl ? 'pointer' : 'default',
            }}
            onClick={openPaper}
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
          {isPreprint ? (
            <span
              title="Preprint: not yet peer reviewed"
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 9.5,
                fontWeight: 600,
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
                color: 'var(--text-purple)',
                background: 'var(--bg-purple)',
                border: '1px solid var(--border-purple)',
                borderRadius: 3,
                padding: '1px 5px',
                marginRight: 6,
              }}
            >
              {paper.source === 'biorxiv' ? 'bioRxiv' : 'medRxiv'} preprint
            </span>
          ) : (
            paper.journal && <span style={{ color: '#155c51' }}>{paper.journal}</span>
          )}
          {!isPreprint && paper.journal && paper.authors.length > 0 && ' · '}
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
          {paper.relevance_score != null && (
            <span
              title="Semantic similarity between your query and this paper's title and abstract"
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                color: 'var(--text-teal-dark)',
                background: 'var(--bg-teal)',
                border: '1px solid var(--border-teal)',
                borderRadius: 3,
                padding: '2px 7px',
              }}
            >
              {Math.round(Math.max(0, paper.relevance_score) * 100)}% match
            </span>
          )}
          {fullTextUrl && (
            <a
              href={fullTextUrl}
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
          {paper.pmid && (
            <span
              style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: '#9aa1ab', cursor: 'pointer' }}
              onClick={() => navigate(`/paper/${paper.pmid}`)}
            >
              ⟟ find similar
            </span>
          )}

          {primaryVariant && paper.pmid && (
            <button
              onClick={() => openVariantScore(primaryVariant)}
              disabled={!primaryVariant.ref_sequence || !primaryVariant.alt_sequence}
              title={
                primaryVariant.ref_sequence && primaryVariant.alt_sequence
                  ? undefined
                  : 'Scoring requires nucleotide sequence context, which isn’t available from abstract text alone'
              }
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10.5,
                fontWeight: 600,
                letterSpacing: '0.03em',
                color: primaryVariant.ref_sequence && primaryVariant.alt_sequence ? '#4f4171' : '#9aa1ab',
                border: '1px solid #d7d0e6',
                background: primaryVariant.ref_sequence && primaryVariant.alt_sequence ? '#ece9f4' : '#f6f4ec',
                padding: '4px 9px',
                borderRadius: 3,
                cursor: primaryVariant.ref_sequence && primaryVariant.alt_sequence ? 'pointer' : 'not-allowed',
                opacity: primaryVariant.ref_sequence && primaryVariant.alt_sequence ? 1 : 0.6,
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
