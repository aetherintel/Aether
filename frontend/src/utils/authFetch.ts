// utils/authFetch.ts
// Wraps fetch with:
// 1. Proactive token refresh (30s before expiry)
// 2. Automatic retry after refresh on 401
// 3. Global session-expired signal on unrecoverable 401/403

import { useAuthStore } from '@/store/client/authStore';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api';

// How many ms before expiry to proactively refresh
const REFRESH_BUFFER_MS = 60_000; // 60 seconds

let refreshPromise: Promise<string | null> | null = null;

async function tryRefreshToken(): Promise<string | null> {
  // Deduplicate concurrent refresh attempts
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    const { refreshToken, setToken, setSessionExpired, logout } = useAuthStore.getState();
    if (!refreshToken) {
      setSessionExpired(true);
      return null;
    }

    try {
      const res = await fetch(`${API_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!res.ok) {
        logout();
        setSessionExpired(true);
        return null;
      }

      const data = await res.json();
      const newToken = data.access_token;
      const newRefresh = data.refresh_token;
      const expiresIn = data.expires_in;

      // Update store with new tokens
      const { login } = useAuthStore.getState();
      login(newToken, newRefresh ?? refreshToken, expiresIn);
      setToken(newToken, expiresIn);

      return newToken;
    } catch {
      logout();
      setSessionExpired(true);
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

function isTokenExpiredSoon(): boolean {
  const { expiresAt } = useAuthStore.getState();
  if (!expiresAt) return false;
  return Date.now() >= expiresAt - REFRESH_BUFFER_MS;
}

export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  let token = useAuthStore.getState().token ?? localStorage.getItem('token');

  // 1. Proactively refresh if token expires soon
  if (token && isTokenExpiredSoon()) {
    const refreshed = await tryRefreshToken();
    if (refreshed) token = refreshed;
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: token ? `Bearer ${token}` : '',
    },
  });

  // 2. On 401: try one token refresh, then retry the original request
  if (response.status === 401) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      return fetch(url, {
        ...options,
        headers: {
          ...options.headers,
          Authorization: `Bearer ${refreshed}`,
        },
      });
    }
    // refresh failed → session expired modal will show
    return response;
  }

  // 3. On 403: mark session expired (token invalid, not just expired)
  if (response.status === 403) {
    useAuthStore.getState().setSessionExpired(true);
    return response;
  }

  return response;
}
