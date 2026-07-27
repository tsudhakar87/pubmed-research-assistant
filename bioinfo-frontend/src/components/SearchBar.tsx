interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: (query: string) => void;
  loading?: boolean;
}

export function SearchBar({ value, onChange, onSubmit, loading }: Props) {
  function handleSubmit() {
    const q = value.trim();
    if (q && !loading) onSubmit(q);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') handleSubmit();
  }

  return (
    <div>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 10.5,
        letterSpacing: '0.1em',
        textTransform: 'uppercase' as const,
        color: '#9aa1ab',
        marginBottom: 9,
      }}>
        Ask a research question
      </div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        border: '1.5px solid #1c2430',
        borderRadius: 6,
        padding: '12px 14px',
        background: '#fff',
      }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9aa1ab" strokeWidth="2">
          <circle cx="11" cy="11" r="7" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder='Ask anything — e.g. "does semaglutide reduce cardiovascular risk?"'
          disabled={loading}
          style={{
            flex: 1,
            border: 'none',
            outline: 'none',
            fontFamily: 'var(--font-serif)',
            fontSize: 17,
            color: value ? '#1c2430' : '#9aa1ab',
            background: 'transparent',
          }}
        />
        <button
          onClick={handleSubmit}
          disabled={loading || !value.trim()}
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11.5,
            fontWeight: 600,
            letterSpacing: '0.04em',
            textTransform: 'uppercase' as const,
            background: loading ? '#5c6470' : '#1c2430',
            color: '#fff',
            padding: '9px 16px',
            borderRadius: 4,
            border: 'none',
            cursor: loading ? 'not-allowed' : 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          {loading ? '···' : 'Ask →'}
        </button>
      </div>
    </div>
  );
}
