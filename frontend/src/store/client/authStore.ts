import { create } from 'zustand';

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  expiresAt: number | null; // Unix timestamp ms
  isAuthenticated: boolean;
  sessionExpired: boolean;
  login: (accessToken: string, refreshToken?: string, expiresIn?: number) => void;
  logout: () => void;
  setToken: (accessToken: string, expiresIn?: number) => void;
  setSessionExpired: (expired: boolean) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('token'),
  refreshToken: localStorage.getItem('refreshToken'),
  expiresAt: localStorage.getItem('tokenExpiresAt') ? Number(localStorage.getItem('tokenExpiresAt')) : null,
  isAuthenticated: !!localStorage.getItem('token'),
  sessionExpired: false,

  login: (accessToken: string, refreshToken?: string, expiresIn?: number) => {
    const expiresAt = expiresIn ? Date.now() + expiresIn * 1000 : null;
    localStorage.setItem('token', accessToken);
    if (refreshToken) localStorage.setItem('refreshToken', refreshToken);
    if (expiresAt) localStorage.setItem('tokenExpiresAt', String(expiresAt));
    set({ token: accessToken, refreshToken: refreshToken ?? null, expiresAt, isAuthenticated: true, sessionExpired: false });
  },

  setToken: (accessToken: string, expiresIn?: number) => {
    const expiresAt = expiresIn ? Date.now() + expiresIn * 1000 : null;
    localStorage.setItem('token', accessToken);
    if (expiresAt) localStorage.setItem('tokenExpiresAt', String(expiresAt));
    set({ token: accessToken, expiresAt });
  },

  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('tokenExpiresAt');
    set({ token: null, refreshToken: null, expiresAt: null, isAuthenticated: false, sessionExpired: false });
  },

  setSessionExpired: (expired: boolean) => {
    set({ sessionExpired: expired });
  },
}));
