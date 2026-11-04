import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Evidence, PaperResult, VariantMention } from '../types/api.types';
import { VariantScoringModal } from './VariantScoringModal';
import { DESIGN_LABEL, ORGANISM_LABEL, STANCE_COLOR, STANCE_LABEL } from './evidenceStyles';

interface Props {
  paper: PaperResult;
  onSelectForCompare?: (pmid: string, selected: boolean) => void;
  selectedForCompare?: boolean;
  // Briefly tinted after jumping here from a citation or timeline dot
  highlighted?: boolean;
}

const chip = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  padding: '1px 6px',
  borderRadius: 3,
  border: '1px solid var(--border-default)',
  background: 'var(--bg-muted)',
  color: 'var(--text-secondary)',
  whiteSpace: 'nowrap' as const,
};

function sourceNote(source: string): string {
  return source === 'ai' ? 'Labeled by AI from the abstract' : source === 'icite' ? 'From NIH iCite' : 'From PubMed indexing';
}

function EvidenceRow({ evidence }: { evidence: Evidence }) {
  const [showQuote, setShowQuote] = useState(false);
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', alignItems: 'center', marginBottom: 6 }}>
        <span style={chip} title={sourceNote(evidence.design_source)}>
          {DESIGN_LABEL[evidence.design]}{evidence.design_source === 'ai' && <sup style={{ marginLeft: 2 }}>ai</sup>}
        </span>
        <span style={chip} title={sourceNote(evidence.organism_source)}>
          {ORGANISM_LABEL[evidence.organism]}{evidence.organism_source === 'ai' && <sup style={{ marginLeft: 2 }}>ai</sup>}
        </span>
        {evidence.sample_size != null && (
          <span style={chip}>n = {evidence.sample_size.toLocaleString()}</span>
        )}
        {evidence.stance !== 'not_applicable' && (
          <span style={{
            ...chip,
            fontWeight: 600,
            color: '#fff',
            background: STANCE_COLOR[evidence.stance],
            borderColor: STANCE_COLOR[evidence.stance],
          }}>
            {STANCE_LABEL[evidence.stance]}
          </span>
        )}
      </div>
      <div style={{ fontSize: 13.5, lineHeight: 1.55, color: 'var(--text-navy)' }}>
        {evidence.key_finding}{' '}
        {evidence.verified ? (
          <button
            onClick={() => setShowQuote((v) => !v)}
            style={{
              fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-teal)',
              background: 'none', border: 'none', padding: 0, cursor: 'pointer',
            }}
          >
            {showQuote ? 'hide quote' : 'show quote'}
          </button>
        ) : (
          <span
            title="The AI's supporting quote wasn't found word-for-word in the abstract. Check the abstract before relying on this."
            style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-amber)' }}
          >
            not verified
          </span>
        )}
      </div>
      {showQuote && evidence.finding_quote && (
        <blockquote style={{
          margin: '6px 0 0', padding: '4px 0 4px 10px', borderLeft: '2px solid var(--border-teal)',
          fontFamily: 'var(--font-serif)', fontStyle: 'italic', fontSize: 13.5, color: 'var(--text-secondary)',
        }}>
          “{evidence.finding_quote}”
        </blockquote>
      )}
    </div>
  );
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

export function PaperCard({ paper, onSelectForCompare, selectedForCompare, highlighted }: Props) {
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
      <div
        id={paper.ref != null ? `paper-${paper.ref}` : undefined}
        style={{
          padding: '16px 10px',
          margin: '0 -10px',
          borderBottom: '1px solid #dbd6c8',
          scrollMarginTop: 24,
          background: highlighted ? 'var(--bg-teal)' : 'transparent',
          transition: 'background 0.6s',
        }}
      >
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
            {paper.ref != null && (
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 400, color: '#9aa1ab', marginRight: 6 }}>
                [{paper.ref}]
              </span>
            )}
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

        {paper.evidence && <EvidenceRow evidence={paper.evidence} />}

        {snippet && !paper.evidence && (
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
          {paper.citation_count != null && (
            <span
              title={paper.relative_citation_ratio != null
                ? 'Relative Citation Ratio: citations compared with papers in the same field (1.0 = field average), from NIH iCite'
                : 'Citation count from NIH iCite'}
              style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: '#5c6470' }}
            >
              {paper.citation_count.toLocaleString()} citations
              {paper.relative_citation_ratio != null && ` · RCR ${paper.relative_citation_ratio.toFixed(1)}`}
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
