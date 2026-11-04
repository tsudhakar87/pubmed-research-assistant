import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts';
import type { PaperResult, StudyDesign } from '../types/api.types';
import { ErrorBoundary } from './ErrorBoundary';
import {
  DESIGN_LABEL,
  ORGANISM_COLOR,
  ORGANISM_LABEL,
  STANCE_LABEL,
  isPreprint,
} from './evidenceStyles';

interface Props {
  papers: PaperResult[];
  answerable: boolean;
  onSelect: (ref: number) => void;
}

interface Point {
  x: number;
  y: number;
  r: number;
  ref: number;
  paper: PaperResult;
}

// Stance lanes, top to bottom
const STANCE_LANES = ['contradicts', 'no_effect', 'mixed', 'supports'] as const;
// Topic queries have no stance, so lanes group designs by strength instead
const DESIGN_LANES: { label: string; designs: StudyDesign[] }[] = [
  { label: 'Other', designs: ['review', 'other', 'case_report'] },
  { label: 'Lab', designs: ['animal', 'in_vitro'] },
  { label: 'Observational', designs: ['cohort', 'case_control', 'cross_sectional', 'observational'] },
  { label: 'Trials', designs: ['rct', 'clinical_trial'] },
  { label: 'Synthesis', designs: ['meta_analysis', 'systematic_review'] },
];

// Deterministic jitter so dots in the same year and lane don't stack exactly
function jitter(ref: number, spread: number): number {
  const h = Math.sin(ref * 12.9898) * 43758.5453;
  return ((h - Math.floor(h)) - 0.5) * spread;
}

function radius(n?: number | null): number {
  if (!n) return 4;
  return Math.min(14, 4 + Math.log10(n) * 2.6);
}

const tick = { fontFamily: 'var(--font-mono)', fontSize: 10, fill: 'var(--text-muted)' };

function Dot(props: { cx?: number; cy?: number; payload?: Point; onSelect: (ref: number) => void }) {
  const { cx, cy, payload, onSelect } = props;
  if (cx == null || cy == null || !payload) return null;
  const ev = payload.paper.evidence!;
  const color = ORGANISM_COLOR[ev.organism];
  const hollow = isPreprint(payload.paper);
  return (
    <circle
      cx={cx}
      cy={cy}
      r={payload.r}
      fill={hollow ? '#fff' : color}
      fillOpacity={hollow ? 1 : 0.75}
      stroke={color}
      strokeWidth={hollow ? 1.8 : 1}
      style={{ cursor: 'pointer' }}
      onClick={() => onSelect(payload.ref)}
    />
  );
}

function TooltipBody({ active, payload }: { active?: boolean; payload?: Array<{ payload: Point }> }) {
  if (!active || !payload?.length) return null;
  const { paper, ref } = payload[0].payload;
  const ev = paper.evidence!;
  return (
    <div style={{
      background: '#fff', border: '1px solid var(--border-default)', borderRadius: 4,
      padding: '8px 10px', maxWidth: 300, boxShadow: '0 6px 18px rgba(28,36,48,.12)',
    }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', marginBottom: 3 }}>
        [{ref}] {paper.publication_date?.slice(0, 4)} · {DESIGN_LABEL[ev.design]} · {ORGANISM_LABEL[ev.organism]}
        {ev.sample_size ? ` · n = ${ev.sample_size.toLocaleString()}` : ''}
        {isPreprint(paper) ? ' · preprint' : ''}
      </div>
      <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-navy)', lineHeight: 1.35, marginBottom: 4 }}>
        {paper.title}
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.45 }}>
        <strong>{STANCE_LABEL[ev.stance]}.</strong> {ev.key_finding}
      </div>
    </div>
  );
}

function TimelineInner({ papers, answerable, onSelect }: Props) {
  const lanes = answerable ? STANCE_LANES.map((s) => STANCE_LABEL[s]) : DESIGN_LANES.map((l) => l.label);

  const points: Point[] = papers.flatMap((p) => {
    const ev = p.evidence;
    if (!ev || !p.publication_date || p.ref == null) return [];
    const lane = answerable
      ? STANCE_LANES.indexOf(ev.stance as (typeof STANCE_LANES)[number])
      : DESIGN_LANES.findIndex((l) => l.designs.includes(ev.design));
    if (lane < 0) return [];
    const year = Number(p.publication_date.slice(0, 4));
    return [{ x: year + jitter(p.ref, 0.5), y: lane + jitter(p.ref * 7, 0.45), r: radius(ev.sample_size), ref: p.ref, paper: p }];
  });

  if (points.length < 2) return null;

  const years = points.map((p) => Math.round(p.x));
  const minYear = Math.min(...years) - 1;
  const maxYear = Math.max(...years) + 1;

  return (
    <div style={{
      border: '1px solid var(--border-default)', borderRadius: 6, background: '#fafaf8',
      padding: '14px 18px 10px', marginBottom: 24,
    }}>
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase',
        color: 'var(--text-muted)', marginBottom: 8,
      }}>
        Findings over time
      </div>
      <ResponsiveContainer width="100%" height={56 + lanes.length * 34}>
        <ScatterChart margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border-default)" strokeDasharray="3 3" />
          <XAxis
            type="number" dataKey="x" domain={[minYear, maxYear]} allowDecimals={false}
            tickFormatter={(v: number) => String(Math.round(v))} tick={tick} axisLine={false} tickLine={false}
          />
          <YAxis
            type="number" dataKey="y" domain={[-0.6, lanes.length - 0.4]} ticks={lanes.map((_, i) => i)}
            tickFormatter={(v: number) => lanes[v] ?? ''} tick={tick} axisLine={false} tickLine={false} width={92}
          />
          <Tooltip content={<TooltipBody />} cursor={false} />
          <Scatter data={points} shape={(props: object) => <Dot {...props} onSelect={onSelect} />} isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
      <div style={{
        display: 'flex', gap: 14, flexWrap: 'wrap', fontFamily: 'var(--font-mono)', fontSize: 10,
        color: 'var(--text-muted)', marginTop: 4,
      }}>
        {(['human', 'animal', 'in_vitro'] as const).map((o) => (
          <span key={o} style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: ORGANISM_COLOR[o], opacity: 0.75 }} />
            {ORGANISM_LABEL[o]}
          </span>
        ))}
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', border: '1.5px solid var(--text-muted)' }} />
          Preprint
        </span>
        <span>Larger dot = larger study</span>
        <span>Click a dot to jump to the paper</span>
      </div>
    </div>
  );
}

// A rendering error in the chart shouldn't take the results page down
export function FindingsTimeline(props: Props) {
  return (
    <ErrorBoundary fallback={null}>
      <TimelineInner {...props} />
    </ErrorBoundary>
  );
}
