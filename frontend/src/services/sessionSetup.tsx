import { authFetch } from '@/utils/authFetch';
import type {
  ApiErrorResponse,
  CancelSetupResponse,
  DeleteSessionResponse,
  ListSessionsResponse,
  StartSetupResponse,
  VerifyCodeResponse,
  VerifyPasswordResponse,
} from '../types/sessionSetup';

const apiUrl = import.meta.env.VITE_API_URL;

/**
 * Service class for handling Telegram session setup API calls
 */
export class SessionSetupService {
  /**
   * Helper method to handle API responses and errors
   */
  private static async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      let errorMessage = 'API request failed';

      try {
        const errorData: ApiErrorResponse = await response.json();
        errorMessage = errorData.detail || `HTTP ${response.status}: ${response.statusText}`;
      } catch {
        errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      }

      throw new Error(errorMessage);
    }

    return response.json() as Promise<T>;
  }

  /**
   * Fetch all available sessions
   */
  static async listSessions(): Promise<ListSessionsResponse> {
    const base = apiUrl ?? 'http://localhost:8000/api';
    const response = await authFetch(`${base}/telegram-auth/sessions`);
    return this.handleResponse<ListSessionsResponse>(response);
  }

  /**
   * Start the session setup process
   */
  static async startSetup(
    phone: string,
    sessionName: string = 'default'
  ): Promise<StartSetupResponse> {
    const base = apiUrl ?? 'http://localhost:8000/api';
    const response = await authFetch(`${base}/telegram-auth/setup/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone,
        session_name: sessionName,
      }),
    });

    return this.handleResponse<StartSetupResponse>(response);
  }

  /**
   * Verify the 2FA code received during setup
   */
  static async verifyCode(setupId: string, code: string): Promise<VerifyCodeResponse> {
    const base = apiUrl ?? 'http://localhost:8000/api';
    const response = await authFetch(`${base}/telegram-auth/setup/verify-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        setup_id: setupId,
        code,
      }),
    });

    return this.handleResponse<VerifyCodeResponse>(response);
  }

  /**
   * Verify the 2FA password during setup
   */
  static async verifyPassword(setupId: string, password: string): Promise<VerifyPasswordResponse> {
    const base = apiUrl ?? 'http://localhost:8000/api';
    const response = await authFetch(`${base}/telegram-auth/setup/verify-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        setup_id: setupId,
        password,
      }),
    });

    return this.handleResponse<VerifyPasswordResponse>(response);
  }

  /**
   * Delete an existing session
   */
  static async deleteSession(sessionName: string): Promise<DeleteSessionResponse> {
    const base = apiUrl ?? 'http://localhost:8000/api';
    const response = await authFetch(
      `${base}/telegram-auth/sessions/${encodeURIComponent(sessionName)}`,
      {
        method: 'DELETE',
      }
    );

    return this.handleResponse<DeleteSessionResponse>(response);
  }

  /**
   * Cancel an ongoing setup process
   */
  static async cancelSetup(setupId: string): Promise<CancelSetupResponse> {
    const base = apiUrl ?? 'http://localhost:8000/api';
    const response = await authFetch(
      `${base}/telegram-auth/setup/cancel/${encodeURIComponent(setupId)}`,
      {
        method: 'POST',
      }
    );

    return this.handleResponse<CancelSetupResponse>(response);
  }
}
