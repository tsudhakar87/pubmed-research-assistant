import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { TrendPoint } from '../types/api.types';
import { ErrorBoundary } from './ErrorBoundary';

interface Props {
  data: TrendPoint[];
}

const tick = { fontFamily: 'var(--font-mono)', fontSize: 10, fill: 'var(--text-muted)' };

function formatCount(n: number): string {
  if (n >= 10_000) return `${Math.round(n / 1000)}k`;
  if (n >= 1_000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

function TrendChartInner({ data }: Props) {
  const total = data.reduce((s, d) => s + d.count, 0);
  const first = data[0]?.year;
  const last = data[data.length - 1]?.year;

  return (
    <div style={{
      background: '#fafaf8',
      border: '1px solid var(--border-default)',
      borderRadius: 6,
      padding: '14px 18px 10px',
      marginBottom: 24,
    }}>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        color: 'var(--text-muted)',
        marginBottom: 12,
        display: 'flex',
        gap: 8,
        flexWrap: 'wrap',
      }}>
        Publication trend · PubMed
        <span style={{ color: 'var(--text-secondary)' }}>
          · {total.toLocaleString()} papers {first}–{last}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={148}>
        <BarChart data={data} barCategoryGap="30%" margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-default)" vertical={false} />
          <XAxis dataKey="year" tick={tick} axisLine={false} tickLine={false} />
          <YAxis tick={tick} axisLine={false} tickLine={false} allowDecimals={false} width={36} tickFormatter={formatCount} />
          <Tooltip
            cursor={{ fill: 'var(--bg-muted)' }}
            contentStyle={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              border: '1px solid var(--border-default)',
              borderRadius: 4,
            }}
            formatter={(value) => [Number(value).toLocaleString(), 'papers']}
            labelFormatter={(year) => {
              const point = data.find((d) => d.year === Number(year));
              return point?.partial ? `${year} (year to date)` : String(year);
            }}
          />
          <Bar dataKey="count" radius={[3, 3, 0, 0]} isAnimationActive={false}>
            {data.map((d) => (
              // The current year is incomplete, so it's drawn lighter
              <Cell key={d.year} fill={d.partial ? 'var(--border-teal)' : 'var(--text-teal-dark)'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// A chart rendering error shouldn't take the results page down with it
export function TrendChart(props: Props) {
  return (
    <ErrorBoundary fallback={null}>
      <TrendChartInner {...props} />
    </ErrorBoundary>
  );
}
