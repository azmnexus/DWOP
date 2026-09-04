/**
 * Auth token management utilities.
 * Uses localStorage for JWT storage (stateless backend, no refresh endpoint).
 */

const TOKEN_KEY = 'dwop_access_token';
const USER_KEY = 'dwop_user';

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isAuthenticated(): boolean {
  const token = getToken();
  if (!token) return false;

  // Basic JWT expiry check (decode payload without verification)
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const exp = payload.exp;
    if (!exp) return false;
    return Date.now() < exp * 1000;
  } catch {
    return false;
  }
}

export function getStoredUser(): import('@/types').UserRead | null {
  if (typeof window === 'undefined') return null;
  const data = localStorage.getItem(USER_KEY);
  if (!data) return null;
  try {
    return JSON.parse(data);
  } catch {
    return null;
  }
}

export function setStoredUser(user: import('@/types').UserRead): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getUserRoleFromToken(): string | null {
  const token = getToken();
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.role || null;
  } catch {
    return null;
  }
}

export function hasRole(requiredRoles: string[]): boolean {
  const role = getUserRoleFromToken();
  if (!role) return false;
  return requiredRoles.includes(role);
}

export function canWrite(): boolean {
  return hasRole(['ADMIN', 'MANAGER']);
}

export function isAdmin(): boolean {
  return hasRole(['ADMIN']);
}
