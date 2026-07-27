import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { authGoogle, getMe } from '../services/api';
import type { AuthResponse } from '../types/api.types';

interface AuthContextValue {
  user: AuthResponse['user'] | null;
  token: string | null;
  loading: boolean;
  signInWithGoogle: (idToken: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthResponse['user'] | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore session from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem('access_token');
    if (stored) {
      setToken(stored);
      getMe()
        .then((u) => setUser(u))
        .catch(() => {
          localStorage.removeItem('access_token');
          setToken(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const signInWithGoogle = useCallback(async (idToken: string) => {
    const res = await authGoogle(idToken);
    localStorage.setItem('access_token', res.access_token);
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const signOut = useCallback(() => {
    localStorage.removeItem('access_token');
    setToken(null);
    setUser(null);
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
