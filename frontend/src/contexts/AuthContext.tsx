'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { UserRead, TokenResponse, LoginRequest } from '@/types';
import { api, ApiRequestError } from '@/lib/api';
import {
  getToken,
  setToken,
  removeToken,
  isAuthenticated,
  getStoredUser,
  setStoredUser,
} from '@/lib/auth';

interface AuthContextValue {
  user: UserRead | null;
  token: string | null;
  isLoading: boolean;
  isLoggedIn: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => void;
  error: string | null;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserRead | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Fetch current user profile from /auth/me using stored token.
   */
  const fetchCurrentUser = useCallback(async () => {
    try {
      const userData = await api.get<UserRead>('/auth/me');
      setUser(userData);
      setStoredUser(userData);
    } catch (err) {
      // Token is invalid or expired — clear auth state
      removeToken();
      setUser(null);
      setTokenState(null);
    }
  }, []);

  /**
   * Initialize auth state from stored token on mount.
   */
  useEffect(() => {
    const initAuth = async () => {
      const storedToken = getToken();
      if (storedToken && isAuthenticated()) {
        setTokenState(storedToken);
        // Try to use cached user first for instant UI, then validate
        const cached = getStoredUser();
        if (cached) {
          setUser(cached);
        }
        await fetchCurrentUser();
      }
      setIsLoading(false);
    };

    initAuth();
  }, [fetchCurrentUser]);

  /**
   * Login with email/password against POST /api/v1/auth/login
   */
  const login = useCallback(async (credentials: LoginRequest) => {
    setError(null);
    setIsLoading(true);

    try {
      const response = await api.post<TokenResponse>('/auth/login', credentials);
      setToken(response.access_token);
      setTokenState(response.access_token);

      // Fetch full user profile
      await fetchCurrentUser();
    } catch (err) {
      const message =
        err instanceof ApiRequestError
          ? err.userMessage
          : 'An unexpected error occurred. Please try again.';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [fetchCurrentUser]);

  /**
   * Logout — clear local token state (no server-side endpoint).
   */
  const logout = useCallback(() => {
    removeToken();
    setUser(null);
    setTokenState(null);
    setError(null);
    if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
  }, []);

  const value: AuthContextValue = {
    user,
    token,
    isLoading,
    isLoggedIn: !!user && !!token,
    login,
    logout,
    error,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
