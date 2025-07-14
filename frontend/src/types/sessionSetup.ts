export interface User {
  id: string;
  first_name: string;
  last_name: string;
  username?: string;
}

export interface Session {
  name: string;
  active: boolean;
  user?: User;
  error?: string;
}

export interface CurrentSetup {
  phone: string;
  sessionName: string;
  message: string;
  user?: User;
}

// Setup step types
export type SetupStep = 'initial' | 'code_sent' | 'password_required' | 'completed';

// API Response types
export interface StartSetupResponse {
  setup_id: string;
  message: string;
}

export interface VerifyCodeResponse {
  success: boolean;
  requires_password?: boolean;
  user?: User;
}

export interface VerifyPasswordResponse {
  success: boolean;
  user?: User;
}

export interface ListSessionsResponse {
  sessions: Session[];
}

// Additional API Response types
export interface DeleteSessionResponse {
  success: boolean;
  message?: string;
}

export interface CancelSetupResponse {
  success: boolean;
  message?: string;
}

// Error response type
export interface ApiErrorResponse {
  detail: string;
}

// Hook return type
export interface UseSessionSetupReturn {
  // State
  sessions: Session[];
  isLoading: boolean;
  setupStep: SetupStep;
  currentSetup: CurrentSetup | null;
  error: string | null;

  // Actions
  startSetup: (phone: string, sessionName: string) => Promise<StartSetupResponse>;
  verifyCode: (code: string) => Promise<VerifyCodeResponse>;
  verifyPassword: (password: string) => Promise<VerifyPasswordResponse>;
  deleteSession: (sessionName: string) => Promise<void>;
  cancelSetup: () => Promise<void>;
  resetSetup: () => void;
  loadSessions: () => Promise<void>;
}
