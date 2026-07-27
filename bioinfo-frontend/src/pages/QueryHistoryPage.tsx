import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getQueryHistory } from '../services/api';
import { Header } from '../components/Header';
import type { HistoryItem } from '../types/api.types';

function groupByDate(items: HistoryItem[]): Record<string, HistoryItem[]> {
  const groups: Record<string, HistoryItem[]> = {};
  const now = new Date();
  const today = now.toDateString();
  const yesterday = new Date(now.getTime() - 86400000).toDateString();

  for (const item of items) {
    const d = new Date(item.created_at);
    const ds = d.toDateString();
    let label: string;
    if (ds === today) label = 'Today';
    else if (ds === yesterday) label = 'Yesterday';
    else {
      const days = Math.round((now.getTime() - d.getTime()) / 86400000);
      label = `${days} days ago`;
    }
    if (!groups[label]) groups[label] = [];
    groups[label].push(item);
  }
  return groups;
}

export function QueryHistoryPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [filtered, setFiltered] = useState<HistoryItem[]>([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getQueryHistory()
      .then((res) => {
        setItems(res.queries);
        setFiltered(res.queries);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  function handleFilter(q: string) {
    setFilter(q);
    setFiltered(items.filter((i) => i.original_query.toLowerCase().includes(q.toLowerCase())));
  }

  const groups = groupByDate(filtered);

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', background: '#fff', border: '1px solid #dbd6c8', borderRadius: 3, boxShadow: '0 1px 2px rgba(28,36,48,.04), 0 18px 40px rgba(28,36,48,.08)', minHeight: '100vh' }}>
      <Header />

      <div style={{ padding: '22px 34px 12px' }}>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10.5,
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          color: '#9aa1ab',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          marginBottom: 9,
        }}>
          Query History{' '}
          <span style={{ color: '#5c6470', fontWeight: 600 }}>· {items.length} total</span>
          <div style={{ flex: 1, height: 1, background: '#dbd6c8' }} />
        </div>
        <input
          value={filter}
          onChange={(e) => handleFilter(e.target.value)}
          placeholder="Filter past queries…"
          style={{
            width: '100%',
            border: '1.5px solid #1c2430',
            borderRadius: 6,
            padding: '10px 13px',
            fontFamily: 'var(--font-sans)',
            fontSize: 13.5,
            color: '#1c2430',
            outline: 'none',
          }}
        />
      </div>

      <div style={{ padding: '6px 34px 30px' }}>
        {loading && (
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: '#9aa1ab', padding: '20px 0' }}>
            Loading…
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <div style={{ fontFamily: 'var(--font-serif)', fontStyle: 'italic', fontSize: 16, color: '#9aa1ab', padding: '20px 0' }}>
            No queries found.
          </div>
        )}

        {Object.entries(groups).map(([label, group]) => (
          <div key={label}>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: '#9aa1ab',
              margin: '20px 0 4px',
            }}>
              {label}
            </div>

            {group.map((item) => (
              <div
                key={item.query_id}
                style={{
                  padding: '14px 0',
                  borderBottom: '1px solid #dbd6c8',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 16,
                }}
              >
                <div>
                  <div style={{
                    fontFamily: 'var(--font-serif)',
                    fontSize: 15.5,
                    color: '#1c2430',
                  }}>
                    {item.original_query}
                  </div>
                  <div style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10.5,
                    color: '#9aa1ab',
                    marginTop: 5,
                  }}>
                    {new Date(item.created_at).toLocaleString()} · {item.total_results} results
                    {item.has_ai_summary && ' · gemini-2.5-pro'}
                  </div>
                </div>
                <div
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10.5,
                    fontWeight: 600,
                    letterSpacing: '0.04em',
                    textTransform: 'uppercase',
                    color: '#1f7a6c',
                    whiteSpace: 'nowrap',
                    cursor: 'pointer',
                  }}
                  onClick={() => navigate(`/?reopen=${item.query_id}`)}
                >
                  reopen →
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
