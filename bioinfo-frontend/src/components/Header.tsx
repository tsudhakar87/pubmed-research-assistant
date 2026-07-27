import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

export function Header() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const initials = user?.name
    ? user.name.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase()
    : user?.email?.slice(0, 2).toUpperCase() ?? '?';

  return (
    <div style={{
      padding: '26px 34px 20px',
      borderBottom: '1.5px solid #1c2430',
      display: 'flex',
      alignItems: 'flex-end',
      justifyContent: 'space-between',
      gap: 14,
      background: '#fff',
    }}>
      <div
        style={{ display: 'flex', flexDirection: 'column', gap: 6, cursor: 'pointer' }}
        onClick={() => navigate('/')}
      >
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10.5,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          color: '#155c51',
          fontWeight: 600,
        }}>
          Literature Synthesis & Comparison Tool
        </div>
        <div style={{
          fontFamily: 'var(--font-serif)',
          fontStyle: 'italic',
          fontWeight: 600,
          fontSize: 32,
          letterSpacing: '-0.01em',
          color: '#1c2430',
          lineHeight: 1,
        }}>
          pub<span style={{ color: '#1f7a6c', fontStyle: 'normal' }}>/</span>med assistant
        </div>
      </div>

      {user && (
        <button
          onClick={signOut}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '6px 12px 6px 6px',
            border: '1px solid #dbd6c8',
            borderRadius: 20,
            fontSize: 12.5,
            color: '#5c6470',
            background: 'transparent',
            cursor: 'pointer',
          }}
          title="Sign out"
        >
          <div style={{
            width: 22,
            height: 22,
            borderRadius: '50%',
            background: '#1f7a6c',
            color: '#fff',
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            {initials}
          </div>
          <span>signed in</span>
        </button>
      )}
    </div>
  );
}
