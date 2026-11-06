import { useState } from 'react';

interface Props {
  summary: string | null;
  loading?: boolean;
  sourcesCount?: number;
  onRegenerate?: () => Promise<void>;
  // Called with a paper's ref number when a [n] citation is clicked
  onCite?: (ref: number) => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}

const CITATION = /\[(\d+(?:\s*,\s*\d+)*)\]/g;

// Turns "[2, 5]" in the summary into buttons that jump to those papers
function withCitations(text: string, onCite?: (ref: number) => void): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(CITATION)) {
    out.push(text.slice(last, m.index));
    const refs = m[1].split(',').map((n) => Number(n.trim()));
    out.push(
      <span key={m.index} style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5, whiteSpace: 'nowrap' }}>
        [
        {refs.map((ref, i) => (
          <span key={ref}>
            {i > 0 && ', '}
            {onCite ? (
              <button
                onClick={() => onCite(ref)}
                style={{
                  font: 'inherit', color: 'var(--text-teal)', background: 'none', border: 'none',
                  padding: 0, cursor: 'pointer', textDecoration: 'underline dotted',
                }}
              >
                {ref}
              </button>
            ) : ref}
          </span>
        ))}
        ]
      </span>,
    );
    last = (m.index ?? 0) + m[0].length;
  }
  out.push(text.slice(last));
  return out;
}

export function AISynthesis({ summary, loading, sourcesCount, onRegenerate, onCite, collapsed, onToggleCollapsed }: Props) {
  const [regenerating, setRegenerating] = useState(false);

  async function handleRegenerate() {
    if (!onRegenerate) return;
    setRegenerating(true);
    try {
      await onRegenerate();
    } finally {
      setRegenerating(false);
    }
  }

  return (
    <div style={{
      borderLeft: '3px solid #1f7a6c',
      background: '#e1efec',
      borderRadius: '0 6px 6px 0',
      padding: '16px 18px',
      marginBottom: 26,
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: collapsed ? 0 : (loading ? 10 : 8),
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            letterSpacing: '0.08em',
            textTransform: 'uppercase' as const,
            color: '#155c51',
            fontWeight: 600,
          }}>
            AI Synthesis
          </span>
          {!loading && (
            <>
              <button
                onClick={() => onToggleCollapsed()}
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 10,
                  color: '#1f7a6c',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                {collapsed ? 'show' : 'hide'}
              </button>
              {onRegenerate && (
                <button
                  onClick={handleRegenerate}
                  disabled={regenerating}
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10,
                    color: regenerating ? '#9aa1ab' : '#1f7a6c',
                    background: 'transparent',
                    border: 'none',
                    cursor: regenerating ? 'not-allowed' : 'pointer',
                    padding: 0,
                  }}
                >
                  {regenerating ? 'regenerating…' : 'regenerate'}
                </button>
              )}
            </>
          )}
        </div>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#9aa1ab' }}>
          {loading ? 'gemini-3.8-flash · generating…' : `gemini-3.8-flash · ${sourcesCount ?? 0} sources`}
        </span>
      </div>

      {!collapsed && (
        loading ? (
          <>
            <div className="skeleton" style={{ height: 12, width: '96%', marginBottom: 8 }} />
            <div className="skeleton" style={{ height: 12, width: '88%', marginBottom: 8 }} />
            <div className="skeleton" style={{ height: 12, width: '64%' }} />
          </>
        ) : (
          <div style={{ fontSize: 14.5, lineHeight: 1.65, color: '#1c2430', whiteSpace: 'pre-wrap' }}>
            {summary ? withCitations(summary, onCite) : summary}
          </div>
        )
      )}
    </div>
  );
}
