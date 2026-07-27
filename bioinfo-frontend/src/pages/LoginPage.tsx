import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const GOOGLE_CLIENT_ID = (import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined) ?? '';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: object) => void;
          renderButton: (el: HTMLElement, config: object) => void;
          prompt: () => void;
        };
      };
    };
  }
}

export function LoginPage() {
  const { signInWithGoogle, user } = useAuth();
  const navigate = useNavigate();
  const googleBtnRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user) navigate('/', { replace: true });
  }, [user]);

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;

    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.onload = () => {
      window.google?.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: async (response: { credential: string }) => {
          setLoading(true);
          try {
            await signInWithGoogle(response.credential);
            navigate('/', { replace: true });
          } catch (e) {
            setError(e instanceof Error ? e.message : 'Sign-in failed');
          } finally {
            setLoading(false);
          }
        },
      });
      if (googleBtnRef.current) {
        window.google?.accounts.id.renderButton(googleBtnRef.current, {
          theme: 'outline',
          size: 'large',
          width: 336,
          text: 'signin_with',
        });
      }
    };
    document.head.appendChild(script);
    return () => { document.head.removeChild(script); };
  }, []);

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      padding: '60px 24px',
      background: 'var(--bg-canvas)',
      backgroundImage: 'linear-gradient(var(--border-default) 1px, transparent 1px)',
      backgroundSize: '100% 32px',
    }}>
      <div style={{
        width: 400,
        background: '#fff',
        border: '1px solid #dbd6c8',
        borderRadius: 3,
        boxShadow: '0 1px 2px rgba(28,36,48,.04), 0 18px 40px rgba(28,36,48,.08)',
      }}>
        {/* Brand header */}
        <div style={{
          padding: '30px 32px 24px',
          borderBottom: '1.5px solid #1c2430',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 6,
          textAlign: 'center',
        }}>
          <div style={{
            fontFamily: 'var(--font-serif)',
            fontStyle: 'italic',
            fontWeight: 600,
            fontSize: 30,
            letterSpacing: '-0.01em',
            color: '#1c2430',
            lineHeight: 1,
          }}>
            pub<span style={{ color: '#1f7a6c', fontStyle: 'normal' }}>/</span>med assistant
          </div>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10.5,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color: '#155c51',
            fontWeight: 600,
          }}>
            Literature Synthesis
          </div>
        </div>

        {/* Sign-in body */}
        <div style={{ padding: '28px 32px 30px' }}>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10.5,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color: '#9aa1ab',
            marginBottom: 24,
            textAlign: 'center',
          }}>
            Sign in to continue
          </div>

          {GOOGLE_CLIENT_ID ? (
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 18 }}>
              <div ref={googleBtnRef} />
            </div>
          ) : (
            <div style={{
              padding: '12px 14px',
              border: '1.5px solid #1c2430',
              borderRadius: 6,
              marginBottom: 18,
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: '#9aa1ab',
              textAlign: 'center',
            }}>
              Configure VITE_GOOGLE_CLIENT_ID to enable Google sign-in
            </div>
          )}

          {error && (
            <div style={{ color: '#8a5c1a', fontFamily: 'var(--font-mono)', fontSize: 11, marginBottom: 12, textAlign: 'center' }}>
              {error}
            </div>
          )}

          {loading && (
            <div style={{ textAlign: 'center', color: '#9aa1ab', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
              Signing in…
            </div>
          )}

          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            color: '#9aa1ab',
            textAlign: 'center',
            paddingTop: 14,
            borderTop: '1px dashed #dbd6c8',
            marginTop: 8,
          }}>
            Session secured via signed JWT · expires in 24h
          </div>
        </div>
      </div>
    </div>
  );
}
