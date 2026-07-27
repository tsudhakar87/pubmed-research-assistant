interface Props {
  summary: string | null;
  loading?: boolean;
  sourcesCount?: number;
}

export function AISynthesis({ summary, loading, sourcesCount }: Props) {
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
        marginBottom: loading ? 10 : 8,
      }}>
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
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          color: '#9aa1ab',
        }}>
          {loading ? 'gemini-2.5-flash · generating…' : `gemini-2.5-flash · ${sourcesCount ?? 0} sources`}
        </span>
      </div>

      {loading ? (
        <>
          <div className="skeleton" style={{ height: 12, width: '96%', marginBottom: 8 }} />
          <div className="skeleton" style={{ height: 12, width: '88%', marginBottom: 8 }} />
          <div className="skeleton" style={{ height: 12, width: '64%' }} />
        </>
      ) : (
        <div style={{ fontSize: 14.5, lineHeight: 1.65, color: '#1c2430', whiteSpace: 'pre-wrap' }}>
          {summary}
        </div>
      )}
    </div>
  );
}
