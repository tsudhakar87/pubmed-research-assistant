import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { clearQueryHistory, deleteAccount, setReturningUser } from '../services/api';

interface Props {
  onClose: () => void;
}

type MenuState = 'menu' | 'confirm-clear' | 'confirm-delete';

const DELETE_PHRASE = 'DELETE';

const mono = { fontFamily: 'var(--font-mono)' } as const;

export function UserMenu({ onClose }: Props) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [state, setState] = useState<MenuState>('menu');
  const [confirmText, setConfirmText] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  // A clear/delete request is in flight; the confirm screen stays up, disabled
  const [working, setWorking] = useState(false);

  // Escape closes, except mid-request
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && !working) onClose();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, working]);

  function go(next: MenuState) {
    setError('');
    setNotice('');
    setConfirmText('');
    setState(next);
  }

  function handleSignOut() {
    signOut();
    onClose();
    navigate('/login', { replace: true });
  }

  async function handleClearHistory() {
    setWorking(true);
    setError('');
    try {
      const { deleted_queries } = await clearQueryHistory();
      setNotice(
        deleted_queries === 1 ? '1 query deleted.' : `${deleted_queries} queries deleted.`,
      );
      setState('menu');
      navigate('/');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not clear history');
    } finally {
      setWorking(false);
    }
  }

  async function handleDeleteAccount() {
    setWorking(true);
    setError('');
    try {
      await deleteAccount();
      setReturningUser(false);
      signOut();
      onClose();
      navigate('/login', { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not delete account');
      setWorking(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Account"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(28,36,48,.45)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 28,
        zIndex: 1000,
      }}
      onClick={(e) => { if (e.target === e.currentTarget && !working) onClose(); }}
    >
      <div style={{
        width: 400,
        maxWidth: '100%',
        background: '#fff',
        border: '1px solid var(--border-default)',
        borderRadius: 6,
        boxShadow: '0 24px 60px rgba(28,36,48,.35)',
      }}>
        {/* Header */}
        <div style={{
          borderLeft: '3px solid var(--text-teal)',
          background: 'var(--bg-teal)',
          borderRadius: '6px 6px 0 0',
          padding: '16px 18px',
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 12,
        }}>
          <div style={{ minWidth: 0 }}>
            <span style={{
              ...mono,
              fontSize: 10,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--text-teal-dark)',
              fontWeight: 600,
              display: 'block',
              marginBottom: 4,
            }}>
              Account
            </span>
            <div style={{ fontFamily: 'var(--font-serif)', fontStyle: 'italic', fontSize: 19, color: 'var(--text-navy)' }}>
              {user?.name ?? 'Signed in'}
            </div>
            <div style={{ ...mono, fontSize: 11, color: 'var(--text-secondary)', marginTop: 2, overflowWrap: 'anywhere' }}>
              {user?.email}
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={working}
            aria-label="Close"
            style={{ ...mono, fontSize: 13, color: 'var(--text-teal-dark)', background: 'transparent', border: 'none', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>

        <div style={{ padding: '14px 18px 18px' }}>
          {state === 'menu' && (
            <>
              {notice && (
                <div style={{ ...mono, fontSize: 11, color: 'var(--text-teal-dark)', marginBottom: 10 }}>{notice}</div>
              )}
              <MenuItem label="Sign out" description="End this session on this device" onClick={handleSignOut} />
              <MenuItem
                label="Clear all query history"
                description="Delete every saved query and its results"
                onClick={() => go('confirm-clear')}
              />
              <MenuItem
                label="Delete account"
                description="Remove your account and all your data"
                destructive
                onClick={() => go('confirm-delete')}
                last
              />
            </>
          )}

          {state === 'confirm-clear' && (
            <Confirm
              title="Clear all query history?"
              body="Every saved query and its results will be permanently deleted. This cannot be undone."
              confirmLabel={working ? 'Clearing…' : 'Clear history'}
              disabled={working}
              error={error}
              onConfirm={handleClearHistory}
              onCancel={() => go('menu')}
            />
          )}

          {state === 'confirm-delete' && (
            <Confirm
              title="Delete your account?"
              body="Your account, query history and saved results will be permanently deleted. This cannot be undone."
              confirmLabel={working ? 'Deleting…' : 'Delete account'}
              disabled={working || confirmText !== DELETE_PHRASE}
              error={error}
              onConfirm={handleDeleteAccount}
              onCancel={() => go('menu')}
            >
              <label style={{ display: 'block', ...mono, fontSize: 10.5, color: 'var(--text-secondary)', marginBottom: 6 }}>
                Type <strong style={{ color: 'var(--text-amber)' }}>{DELETE_PHRASE}</strong> to confirm
              </label>
              <input
                autoFocus
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                disabled={working}
                aria-label={`Type ${DELETE_PHRASE} to confirm`}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && confirmText === DELETE_PHRASE && !working) void handleDeleteAccount();
                }}
                style={{
                  width: '100%',
                  boxSizing: 'border-box',
                  ...mono,
                  fontSize: 13,
                  padding: '7px 9px',
                  border: '1px solid var(--border-default)',
                  borderRadius: 3,
                  marginBottom: 14,
                }}
              />
            </Confirm>
          )}
        </div>
      </div>
    </div>
  );
}

function MenuItem({ label, description, onClick, destructive, last }: {
  label: string;
  description: string;
  onClick: () => void;
  destructive?: boolean;
  last?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'block',
        width: '100%',
        textAlign: 'left',
        background: 'transparent',
        border: 'none',
        borderBottom: last ? 'none' : '1px solid var(--border-default)',
        padding: '11px 2px',
        cursor: 'pointer',
      }}
    >
      <div style={{ fontSize: 14, color: destructive ? 'var(--text-amber)' : 'var(--text-navy)' }}>{label}</div>
      <div style={{ ...mono, fontSize: 10.5, color: 'var(--text-muted)', marginTop: 2 }}>{description}</div>
    </button>
  );
}

function Confirm({ title, body, confirmLabel, disabled, error, onConfirm, onCancel, children }: {
  title: string;
  body: string;
  confirmLabel: string;
  disabled: boolean;
  error: string;
  onConfirm: () => void;
  onCancel: () => void;
  children?: React.ReactNode;
}) {
  return (
    <div>
      <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-navy)', margin: '4px 0 6px' }}>{title}</div>
      <div style={{ fontSize: 13, lineHeight: 1.55, color: 'var(--text-secondary)', marginBottom: 14 }}>{body}</div>
      {children}
      {error && (
        <div style={{ ...mono, fontSize: 11, color: 'var(--text-amber)', marginBottom: 12 }}>{error}</div>
      )}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button
          onClick={onCancel}
          style={{
            ...mono, fontSize: 11, fontWeight: 600, padding: '6px 12px', borderRadius: 3,
            border: '1px solid var(--border-default)', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer',
          }}
        >
          Cancel
        </button>
        <button
          onClick={onConfirm}
          disabled={disabled}
          style={{
            ...mono, fontSize: 11, fontWeight: 600, padding: '6px 12px', borderRadius: 3,
            border: '1px solid var(--border-amber)', background: 'var(--bg-amber)', color: 'var(--text-amber)',
            cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.55 : 1,
          }}
        >
          {confirmLabel}
        </button>
      </div>
    </div>
  );
}
