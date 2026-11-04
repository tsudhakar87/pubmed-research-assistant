import type { PipelineStep } from '../types/api.types';

const STEPS: { key: PipelineStep; label: string }[] = [
  { key: 'classifying', label: '01 · CLASSIFYING' },
  { key: 'searching_pubmed', label: '02 · SEARCHING PUBMED' },
  // PubMed and preprint searches run in parallel, so this step covers both
  { key: 'searching_preprints', label: '03 · SEARCHING PUBMED + PREPRINTS' },
  { key: 'retrieving_abstracts', label: '04 · MERGING RESULTS' },
  { key: 'scoring_relevance', label: '05 · SCORING RELEVANCE' },
  { key: 'synthesizing', label: '06 · SYNTHESIZING' },
  { key: 'done', label: '07 · DONE' },
];

interface Props {
  currentStep: PipelineStep;
  timings?: Partial<Record<PipelineStep, string>>;
}

export function PipelineSteps({ currentStep, timings }: Props) {
  if (currentStep === 'idle') return null;

  const active = STEPS.find((s) => s.key === currentStep);
  if (!active) return null;

  const isDone = currentStep === 'done';

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      {!isDone && (
        <span style={{
          display: 'inline-block',
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: '#c98a2e',
          animation: 'pulse 1.2s ease-in-out infinite',
          flexShrink: 0,
        }} />
      )}
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 10.5,
        fontWeight: 600,
        letterSpacing: '0.05em',
        padding: '5px 10px',
        borderRadius: 3,
        background: isDone ? '#e1efec' : '#faf0dc',
        color: isDone ? '#155c51' : '#8a5c1a',
        border: `1px solid ${isDone ? '#c3ddd6' : '#e8cf9e'}`,
      }}>
        {active.label}
      </span>
      {timings?.[currentStep] && (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, color: '#9aa1ab' }}>
          {timings[currentStep]}
        </span>
      )}
    </div>
  );
}
