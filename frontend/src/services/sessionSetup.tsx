import { authFetch } from '@/utils/authFetch';
import type {
  ListSessionsResponse,
  StartSetupResponse,
  VerifyCodeResponse,
  VerifyPasswordResponse,
  DeleteSessionResponse,
  CancelSetupResponse,
  ApiErrorResponse
} from '../types/sessionSetup';

const API_BASE = 'http://localhost:8000/telegram-auth';

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
    const response = await authFetch(`${API_BASE}/sessions`);
    return this.handleResponse<ListSessionsResponse>(response);
  }

  /**
   * Start the session setup process
   */
  static async startSetup(
    phone: string, 
    sessionName: string = 'default'
  ): Promise<StartSetupResponse> {
    const response = await authFetch(`${API_BASE}/setup/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        phone, 
        session_name: sessionName 
      })
    });
    
    return this.handleResponse<StartSetupResponse>(response);
  }

  /**
   * Verify the 2FA code received during setup
   */
  static async verifyCode(
    setupId: string, 
    code: string
  ): Promise<VerifyCodeResponse> {
    const response = await authFetch(`${API_BASE}/setup/verify-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        setup_id: setupId, 
        code 
      })
    });
    
    return this.handleResponse<VerifyCodeResponse>(response);
  }

  /**
   * Verify the 2FA password during setup
   */
  static async verifyPassword(
    setupId: string, 
    password: string
  ): Promise<VerifyPasswordResponse> {
    const response = await authFetch(`${API_BASE}/setup/verify-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        setup_id: setupId, 
        password 
      })
    });
    
    return this.handleResponse<VerifyPasswordResponse>(response);
  }

  /**
   * Delete an existing session
   */
  static async deleteSession(sessionName: string): Promise<DeleteSessionResponse> {
    const response = await authFetch(`${API_BASE}/sessions/${encodeURIComponent(sessionName)}`, {
      method: 'DELETE'
    });
    
    return this.handleResponse<DeleteSessionResponse>(response);
  }

  /**
   * Cancel an ongoing setup process
   */
  static async cancelSetup(setupId: string): Promise<CancelSetupResponse> {
    const response = await authFetch(`${API_BASE}/setup/cancel/${encodeURIComponent(setupId)}`, {
      method: 'POST'
    });
    
    return this.handleResponse<CancelSetupResponse>(response);
  }
}