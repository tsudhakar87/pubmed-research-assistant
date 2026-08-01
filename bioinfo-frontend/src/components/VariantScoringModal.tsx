import { useEffect, useState } from 'react';
import { scoreVariant } from '../services/api';
import type { VariantMention, VariantScore } from '../types/api.types';

interface Props {
  pmid: string;
  variant: VariantMention;
  onClose: () => void;
}

type ModalState = 'loading' | 'result' | 'error';

export function VariantScoringModal({ pmid, variant, onClose }: Props) {
  const [state, setState] = useState<ModalState>('loading');
  const [result, setResult] = useState<VariantScore | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  async function load() {
    if (!variant.ref_sequence || !variant.alt_sequence) {
      setErrorMsg('No nucleotide sequence context available for this variant — scoring requires the actual reference and mutant sequence, not just notation.');
      setState('error');
      return;
    }
    setState('loading');
    try {
      const r = await scoreVariant(pmid, variant.notation, variant.ref_sequence, variant.alt_sequence, variant.gene);
      setResult(r);
      setState('result');
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'Evo2 endpoint unavailable');
      setState('error');
    }
  }

  useEffect(() => { load(); }, []);

  // Close on backdrop click
  function handleBackdropClick(e: React.MouseEvent) {
    if (e.target === e.currentTarget) onClose();
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(28,36,48,.45)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 28,
        zIndex: 1000,
      }}
      onClick={handleBackdropClick}
    >
      <div style={{
        width: 440,
        background: '#fff',
        border: '1px solid #dbd6c8',
        borderRadius: 6,
        boxShadow: '0 24px 60px rgba(28,36,48,.35)',
      }}>
        {/* Header */}
        <div style={{
          borderLeft: '3px solid #6b5b95',
          background: '#ece9f4',
          borderRadius: '6px 6px 0 0',
          padding: '16px 18px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div>
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              letterSpacing: '0.08em',
              textTransform: 'uppercase' as const,
              color: '#4f4171',
              fontWeight: 600,
              display: 'block',
              marginBottom: 4,
            }}>
              Variant Scoring
            </span>
            <div style={{ fontFamily: 'var(--font-serif)', fontStyle: 'italic', fontSize: 19, color: '#1c2430' }}>
              {variant.gene && `${variant.gene} `}{variant.notation}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 13,
              color: '#4f4171',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        {state === 'loading' && <LoadingBody variant={variant} />}
        {state === 'result' && result && <ResultBody result={result} />}
        {state === 'error' && (
          <ErrorBody message={errorMsg} onRetry={load} onDismiss={onClose} />
        )}
      </div>
    </div>
  );
}

function LoadingBody({ variant }: { variant: VariantMention }) {
  return (
    <div style={{ padding: '16px 18px 20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 0, overflowX: 'auto', paddingBottom: 4, marginBottom: 12 }}>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          fontWeight: 600,
          letterSpacing: '0.04em',
          padding: '4px 8px',
          borderRadius: 3,
          background: '#ece9f4',
          color: '#4f4171',
          border: '1px solid #d7d0e6',
          whiteSpace: 'nowrap',
        }}>
          05 · SCORING VARIANT
        </span>
      </div>
      <div style={{
        padding: '9px 11px',
        border: '1px dashed #d7d0e6',
        borderRadius: 6,
        background: '#ece9f4',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        marginBottom: 14,
      }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#4f4171' }}>⬡</span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#4f4171' }}>
          Evo2 NIM inference — typically 10–20s
        </span>
      </div>
      <div style={{
        border: '1px dashed #dbd6c8',
        borderRadius: 6,
        height: 150,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'repeating-linear-gradient(135deg,#f6f4ec,#f6f4ec 10px,#efece1 10px,#efece1 20px)',
      }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: '#9aa1ab' }}>
          scoring {variant.gene && `${variant.gene} `}{variant.notation} ···
        </span>
      </div>
    </div>
  );
}

function ResultBody({ result }: { result: VariantScore }) {
  // Visual scale only — disruptive threshold (delta <= -1.0) maps to ~100%.
  const pct = Math.max(0, Math.min(100, Math.round((-result.delta_log_likelihood / 2) * 100)));
  return (
    <div style={{ padding: '16px 18px 0' }}>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, color: '#9aa1ab' }}>
        BioNeMo NIM · evo2-40b
      </span>

      <div style={{
        marginTop: 10,
        border: '1px dashed #dbd6c8',
        borderRadius: 6,
        padding: 14,
        background: 'repeating-linear-gradient(135deg,#f6f4ec,#f6f4ec 10px,#efece1 10px,#efece1 20px)',
      }}>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 8.5,
          letterSpacing: '0.08em',
          textTransform: 'uppercase' as const,
          color: '#9aa1ab',
          marginBottom: 6,
        }}>
          Ref → Alt sequence
        </div>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          lineHeight: 1.7,
          color: '#5c6470',
          wordBreak: 'break-all',
        }}>
          {result.ref_sequence}
          <br />
          {result.alt_sequence}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 14 }}>
        <div>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 9,
            letterSpacing: '0.08em',
            textTransform: 'uppercase' as const,
            color: '#9aa1ab',
            marginBottom: 3,
          }}>
            Predicted effect (Δ log-likelihood)
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 600, color: '#4f4171' }}>
            {result.delta_log_likelihood.toFixed(2)} · {result.classification}
          </div>
        </div>
        <div style={{
          flex: 1,
          maxWidth: 160,
          height: 6,
          borderRadius: 3,
          background: '#ece9f4',
          marginLeft: 16,
          overflow: 'hidden',
        }}>
          <div style={{ width: `${pct}%`, height: '100%', background: '#6b5b95' }} />
        </div>
      </div>

      <div style={{
        margin: '14px 0 18px',
        paddingTop: 12,
        borderTop: '1px dashed #dbd6c8',
        display: 'flex',
        gap: 8,
      }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#4f4171', flexShrink: 0 }}>⬡</span>
        <div style={{ fontSize: 11, lineHeight: 1.6, color: '#9aa1ab' }}>
          Generated by <strong style={{ color: '#5c6470' }}>BioNeMo NIM</strong> from sequence — not sourced from the paper.
        </div>
      </div>
    </div>
  );
}

function ErrorBody({
  message,
  onRetry,
  onDismiss,
}: {
  message: string;
  onRetry: () => void;
  onDismiss: () => void;
}) {
  return (
    <div style={{ padding: '16px 18px 18px' }}>
      <div style={{
        borderLeft: '3px solid #9aa1ab',
        background: '#f6f4ec',
        borderRadius: '0 6px 6px 0',
        padding: '14px 16px',
      }}>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 9.5,
          color: '#9aa1ab',
          display: 'block',
          marginBottom: 6,
        }}>
          Evo2 NIM
        </span>
        <div style={{ fontSize: 13, lineHeight: 1.6, color: '#5c6470' }}>
          {message.includes('timeout') || message.includes('timed out')
            ? "Score unavailable — the Evo2 endpoint didn't respond in time. This doesn't affect your literature results."
            : message}
        </div>
      </div>
      <div style={{ marginTop: 14, display: 'flex', gap: 10 }}>
        <button
          onClick={onRetry}
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10.5,
            fontWeight: 600,
            letterSpacing: '0.03em',
            color: '#5c6470',
            border: '1px solid #dbd6c8',
            padding: '6px 12px',
            borderRadius: 4,
            background: 'transparent',
            cursor: 'pointer',
          }}
        >
          retry
        </button>
        <button
          onClick={onDismiss}
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10.5,
            color: '#9aa1ab',
            background: 'transparent',
            border: 'none',
            padding: '6px 0',
            cursor: 'pointer',
          }}
        >
          dismiss
        </button>
      </div>
    </div>
  );
}
