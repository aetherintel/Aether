import { useState, useEffect, useCallback } from 'react';
import { SessionSetupService } from '../services/sessionSetup';
import type {
  Session,
  CurrentSetup,
  SetupStep,
  StartSetupResponse,
  VerifyCodeResponse,
  VerifyPasswordResponse,
  ListSessionsResponse,
  UseSessionSetupReturn
} from '../types/sessionSetup';

export const useSessionSetup = (): UseSessionSetupReturn => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [setupStep, setSetupStep] = useState<SetupStep>('initial');
  const [setupId, setSetupId] = useState<string | null>(null);
  const [currentSetup, setCurrentSetup] = useState<CurrentSetup | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadSessions = useCallback(async (): Promise<void> => {
    try {
      setIsLoading(true);
      const response: ListSessionsResponse = await SessionSetupService.listSessions();
      setSessions(response.sessions || []);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load sessions';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Sessions beim Mount laden
  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const startSetup = async (phone: string, sessionName: string): Promise<StartSetupResponse> => {
    try {
      setError(null);
      setIsLoading(true);
      
      const response: StartSetupResponse = await SessionSetupService.startSetup(phone, sessionName);
      setSetupId(response.setup_id);
      setCurrentSetup({
        phone,
        sessionName,
        message: response.message
      });
      setSetupStep('code_sent');
      
      return response;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to start setup';
      setError(errorMessage);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const verifyCode = async (code: string): Promise<VerifyCodeResponse> => {
    if (!setupId) {
      throw new Error('No setup ID available');
    }

    try {
      setError(null);
      setIsLoading(true);
      
      const response: VerifyCodeResponse = await SessionSetupService.verifyCode(setupId, code);
      
      if (response.success) {
        setSetupStep('completed');
        setCurrentSetup(prev => prev ? { ...prev, user: response.user } : null);
        await loadSessions(); // Sessions neu laden
      } else if (response.requires_password) {
        setSetupStep('password_required');
      }
      
      return response;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to verify code';
      setError(errorMessage);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const verifyPassword = async (password: string): Promise<VerifyPasswordResponse> => {
    if (!setupId) {
      throw new Error('No setup ID available');
    }

    try {
      setError(null);
      setIsLoading(true);
      
      const response: VerifyPasswordResponse = await SessionSetupService.verifyPassword(setupId, password);
      
      if (response.success) {
        setSetupStep('completed');
        setCurrentSetup(prev => prev ? { ...prev, user: response.user } : null);
        await loadSessions(); // Sessions neu laden
      }
      
      return response;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to verify password';
      setError(errorMessage);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const deleteSession = async (sessionName: string): Promise<void> => {
    try {
      setError(null);
      setIsLoading(true);
      
      await SessionSetupService.deleteSession(sessionName);
      await loadSessions(); // Sessions neu laden
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete session';
      setError(errorMessage);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const cancelSetup = async (): Promise<void> => {
    try {
      if (setupId) {
        await SessionSetupService.cancelSetup(setupId);
      }
    } catch (err) {
      console.error('Failed to cancel setup:', err);
    } finally {
      resetSetup();
    }
  };

  const resetSetup = (): void => {
    setSetupStep('initial');
    setSetupId(null);
    setCurrentSetup(null);
    setError(null);
  };

  return {
    // State
    sessions,
    isLoading,
    setupStep,
    currentSetup,
    error,
    
    // Actions
    startSetup,
    verifyCode,
    verifyPassword,
    deleteSession,
    cancelSetup,
    resetSetup,
    loadSessions
  };
};