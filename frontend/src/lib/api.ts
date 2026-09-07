/**
 * API client with authentication and error normalization.
 * Never exposes raw backend errors, stack traces, or internal details to the user.
 */
import { getToken, removeToken } from '@/lib/auth';
import type { ApiError } from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

/**
 * Normalized error class for API failures.
 */
export class ApiRequestError extends Error {
  status: number;
  userMessage: string;

  constructor(status: number, userMessage: string) {
    super(userMessage);
    this.name = 'ApiRequestError';
    this.status = status;
    this.userMessage = userMessage;
  }
}

/**
 * Translate HTTP status codes to user-friendly messages.
 */
function getDefaultErrorMessage(status: number): string {
  switch (status) {
    case 400: return 'The request contains invalid data. Please check your input and try again.';
    case 401: return 'Your session has expired. Please sign in again.';
    case 403: return 'You do not have permission to perform this action.';
    case 404: return 'The requested resource was not found.';
    case 409: return 'A conflict occurred. This record may already exist.';
    case 422: return 'Please check your input — some fields contain invalid values.';
    case 429: return 'Too many requests. Please wait a moment and try again.';
    case 500: return 'An unexpected error occurred. Please try again later.';
    case 502: return 'The service is temporarily unavailable. Please try again shortly.';
    case 503: return 'The service is currently undergoing maintenance. Please try again later.';
    default: return 'An unexpected error occurred. Please try again.';
  }
}

/**
 * Extract a safe, user-facing error message from the backend response.
 * Never returns raw stack traces, database errors, or internal paths.
 */
async function extractErrorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const detail = body?.detail;

    if (typeof detail === 'string') {
      // Only show backend detail if it's a short, user-safe message
      // (not a Python exception, stack trace, or internal path)
      const isSafe =
        detail.length < 200 &&
        !detail.includes('Traceback') &&
        !detail.includes('File "') &&
        !detail.includes('sqlalchemy') &&
        !detail.includes('psycopg2') &&
        !detail.includes('/app/') &&
        !detail.includes('\\app\\');

      if (isSafe) return detail;
    }
  } catch {
    // Response body not JSON — use default
  }

  return getDefaultErrorMessage(res.status);
}

/**
 * Core fetch wrapper with authentication and error handling.
 */
export async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let res: Response;

  try {
    res = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });
  } catch {
    throw new ApiRequestError(0, 'Unable to connect to the server. Please check your connection and try again.');
  }

  if (!res.ok) {
    // Handle 401 — session expired, clear token and redirect
    if (res.status === 401 && token) {
      removeToken();
      if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
    }

    const message = await extractErrorMessage(res);
    throw new ApiRequestError(res.status, message);
  }

  // Handle 204 No Content
  if (res.status === 204) {
    return undefined as T;
  }

  return res.json();
}

/**
 * Convenience methods
 */
export const api = {
  get: <T>(endpoint: string) =>
    fetchApi<T>(endpoint, { method: 'GET' }),

  post: <T>(endpoint: string, data?: unknown) =>
    fetchApi<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    }),

  put: <T>(endpoint: string, data: unknown) =>
    fetchApi<T>(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  patch: <T>(endpoint: string, data: unknown) =>
    fetchApi<T>(endpoint, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  delete: <T>(endpoint: string) =>
    fetchApi<T>(endpoint, { method: 'DELETE' }),
};
