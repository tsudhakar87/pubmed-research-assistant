import { useState } from 'react';

interface Props {
  summary: string | null;
  loading?: boolean;
  sourcesCount?: number;
  onRegenerate?: () => Promise<void>;
}

export function AISynthesis({ summary, loading, sourcesCount, onRegenerate }: Props) {
  const [collapsed, setCollapsed] = useState(false);
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
                onClick={() => setCollapsed((c) => !c)}
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
            {summary}
          </div>
        )
      )}
    </div>
  );
}
