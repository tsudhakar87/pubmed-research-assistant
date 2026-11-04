import { useState } from 'react';
import type { EvidenceSummary, Organism, Stance, StudyDesign } from '../types/api.types';
import {
  DESIGN_LABEL,
  DESIGN_TIER,
  ORGANISM_LABEL,
  STANCE_COLOR,
  STANCE_LABEL,
  STANCE_ORDER,
} from './evidenceStyles';

interface Props {
  summary: EvidenceSummary;
}

const mono = { fontFamily: 'var(--font-mono)' } as const;
const FILTERS: Organism[] = ['human', 'animal', 'in_vitro', 'mixed'];

export function EvidencePanel({ summary }: Props) {
  const [filter, setFilter] = useState<Organism | 'all'>('all');

  const counts: Partial<Record<Stance, number>> =
    filter === 'all' ? summary.stance_counts : summary.stance_by_organism[filter] ?? {};
  const directional = STANCE_ORDER.reduce((n, s) => n + (counts[s] ?? 0), 0);
  const notTesting = counts.not_applicable ?? 0;
  const filtersWithData = FILTERS.filter((o) =>
    Object.values(summary.stance_by_organism[o] ?? {}).some((n) => (n ?? 0) > 0),
  );

  const designs = (Object.entries(summary.design_counts) as [StudyDesign, number][])
    .filter(([, n]) => n > 0)
    .sort(([a], [b]) => DESIGN_TIER[a] - DESIGN_TIER[b]);

  return (
    <div style={{
      border: '1px solid var(--border-default)',
      borderRadius: 6,
      background: '#fff',
      padding: '16px 18px',
      marginBottom: 18,
    }}>
      <div style={{
        ...mono, fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase',
        color: 'var(--text-muted)', marginBottom: 10, display: 'flex', gap: 8, flexWrap: 'wrap',
      }}>
        Evidence
        <span style={{ color: 'var(--text-secondary)' }}>
          · {summary.papers_with_evidence} abstracts read
          {summary.preprint_count > 0 && ` · ${summary.preprint_count} preprints`}
        </span>
      </div>

      {summary.answerable && (
        <>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>Measured against</div>
          <div style={{
            fontFamily: 'var(--font-serif)', fontStyle: 'italic', fontSize: 17,
            color: 'var(--text-navy)', lineHeight: 1.35, marginBottom: 14,
          }}>
            {summary.question}
          </div>

          {filtersWithData.length > 1 && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }} role="group" aria-label="Filter by organism">
              {(['all', ...filtersWithData] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  aria-pressed={filter === f}
                  style={{
                    ...mono, fontSize: 10, fontWeight: 600, padding: '3px 9px', borderRadius: 3, cursor: 'pointer',
                    border: `1px solid ${filter === f ? 'var(--border-navy)' : 'var(--border-default)'}`,
                    background: filter === f ? 'var(--text-navy)' : 'transparent',
                    color: filter === f ? '#fff' : 'var(--text-secondary)',
                  }}
                >
                  {f === 'all' ? 'All' : ORGANISM_LABEL[f]}
                </button>
              ))}
            </div>
          )}

          {directional > 0 ? (
            <>
              <div
                role="img"
                aria-label={STANCE_ORDER.map((s) => `${counts[s] ?? 0} ${STANCE_LABEL[s].toLowerCase()}`).join(', ')}
                style={{ display: 'flex', height: 12, borderRadius: 3, overflow: 'hidden', gap: 2, marginBottom: 8 }}
              >
                {STANCE_ORDER.filter((s) => counts[s]).map((s) => (
                  <div key={s} style={{ flex: counts[s], background: STANCE_COLOR[s] }} />
                ))}
              </div>
              <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', ...mono, fontSize: 11, color: 'var(--text-secondary)' }}>
                {STANCE_ORDER.map((s) => (
                  <span key={s} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, opacity: counts[s] ? 1 : 0.45 }}>
                    <span style={{ width: 8, height: 8, borderRadius: 2, background: STANCE_COLOR[s] }} />
                    <strong style={{ color: 'var(--text-navy)' }}>{counts[s] ?? 0}</strong> {STANCE_LABEL[s].toLowerCase()}
                  </span>
                ))}
                {notTesting > 0 && <span style={{ color: 'var(--text-muted)' }}>{notTesting} don’t test the question</span>}
              </div>
            </>
          ) : (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No papers in this group test the question directly.</div>
          )}
        </>
      )}

      {!summary.answerable && (
        <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 4 }}>
          Topic: <span style={{ fontFamily: 'var(--font-serif)', fontStyle: 'italic', fontSize: 15, color: 'var(--text-navy)' }}>{summary.question}</span>
        </div>
      )}

      {designs.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 14 }}>
          {designs.map(([d, n]) => (
            <span key={d} style={{
              ...mono, fontSize: 10.5, padding: '2px 7px', borderRadius: 3,
              background: 'var(--bg-muted)', border: '1px solid var(--border-default)', color: 'var(--text-secondary)',
            }}>
              <strong style={{ color: 'var(--text-navy)' }}>{n}</strong> {DESIGN_LABEL[d]}
            </span>
          ))}
        </div>
      )}

      {summary.gaps.length > 0 && (
        <ul style={{ listStyle: 'none', padding: 0, margin: '14px 0 0', display: 'grid', gap: 6 }}>
          {summary.gaps.map((g) => (
            <li key={g} style={{
              fontSize: 13, lineHeight: 1.5, color: 'var(--text-amber)', background: 'var(--bg-amber)',
              border: '1px solid var(--border-amber)', borderRadius: 3, padding: '6px 10px',
            }}>
              {g}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
