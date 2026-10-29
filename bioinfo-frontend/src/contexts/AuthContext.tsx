import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { ApiError, authGoogle, getMe, setUnauthorizedHandler } from '../services/api';
import type { AuthResponse } from '../types/api.types';

interface AuthContextValue {
  user: AuthResponse['user'] | null;
  token: string | null;
  loading: boolean;
  signInWithGoogle: (idToken: string) => Promise<void>;
  signOut: () => void;
}

// Decode the (unverified) JWT payload so the UI can keep working when /auth/me
// is temporarily unreachable. The backend still verifies the token on every call.
function userFromToken(token: string): AuthResponse['user'] | null {
  try {
    const b64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(atob(b64)) as { sub?: string; email?: string; name?: string; exp?: number };
    if (!payload.sub || !payload.email) return null;
    if (payload.exp && payload.exp * 1000 < Date.now()) return null;
    return { id: payload.sub, email: payload.email, name: payload.name ?? undefined };
  } catch {
    return null;
  }
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthResponse['user'] | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const signOut = useCallback(() => {
    localStorage.removeItem('access_token');
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(signOut);
    return () => setUnauthorizedHandler(null);
  }, [signOut]);

  // Restore session from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem('access_token');
    if (stored) {
      setToken(stored);
      getMe()
        .then((u) => setUser(u))
        .catch((e) => {
          // Only a 401 means the token is bad. A network error or 5xx (e.g. a
          // Cloud Run cold start) shouldn't log the user out.
          if (e instanceof ApiError && e.status === 401) {
            signOut();
          } else {
            const u = userFromToken(stored);
            if (u) setUser(u);
            else signOut();
          }
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [signOut]);

  const signInWithGoogle = useCallback(async (idToken: string) => {
    const res = await authGoogle(idToken);
    localStorage.setItem('access_token', res.access_token);
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, loading, signInWithGoogle, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
