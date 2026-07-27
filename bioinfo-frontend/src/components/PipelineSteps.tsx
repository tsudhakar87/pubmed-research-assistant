import type { PipelineStep } from '../types/api.types';

const STEPS: { key: PipelineStep; label: string }[] = [
  { key: 'classifying', label: '01 · CLASSIFYING' },
  { key: 'searching_pubmed', label: '02 · SEARCHING PUBMED' },
  { key: 'retrieving_abstracts', label: '03 · RETRIEVING ABSTRACTS' },
  { key: 'synthesizing', label: '04 · SYNTHESIZING' },
  { key: 'done', label: '05 · DONE' },
];

const STEP_ORDER = STEPS.map((s) => s.key);

type StepState = 'done' | 'active' | 'pending';

function getState(stepKey: PipelineStep, currentStep: PipelineStep): StepState {
  const currentIdx = STEP_ORDER.indexOf(currentStep);
  const stepIdx = STEP_ORDER.indexOf(stepKey);
  if (stepIdx < currentIdx) return 'done';
  if (stepIdx === currentIdx) return 'active';
  return 'pending';
}

function stepStyle(state: StepState): React.CSSProperties {
  if (state === 'done') {
    return {
      background: '#e1efec',
      color: '#155c51',
      border: '1px solid #c3ddd6',
    };
  }
  if (state === 'active') {
    return {
      background: '#faf0dc',
      color: '#8a5c1a',
      border: '1px solid #e8cf9e',
    };
  }
  return {
    background: 'transparent',
    color: '#9aa1ab',
    border: '1px dashed #dbd6c8',
  };
}

interface Props {
  currentStep: PipelineStep;
  timings?: Partial<Record<PipelineStep, string>>;
}

export function PipelineSteps({ currentStep, timings }: Props) {
  if (currentStep === 'idle') return null;

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 0,
      marginTop: 16,
      overflowX: 'auto',
      paddingBottom: 4,
    }}>
      {STEPS.map((step, i) => {
        const state = getState(step.key, currentStep);
        return (
          <div key={step.key} style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
            {i > 0 && (
              <div style={{
                width: 22,
                height: 1,
                borderTop: '1.5px dotted #9aa1ab',
                flexShrink: 0,
                margin: '0 6px',
              }} />
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10.5,
                fontWeight: 600,
                letterSpacing: '0.05em',
                padding: '5px 10px',
                borderRadius: 3,
                whiteSpace: 'nowrap',
                ...stepStyle(state),
              }}>
                {step.label}
              </span>
              {timings?.[step.key] && (
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 9.5,
                  color: '#9aa1ab',
                  minWidth: 36,
                }}>
                  {timings[step.key]}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
