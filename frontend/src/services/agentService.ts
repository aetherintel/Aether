import { authFetch } from '@/utils/authFetch';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export interface GraphNode {
  id: string;
  label: string;
  name?: string;
  text?: string;
  val?: number;
}

export interface GraphLink {
  source: string;
  target: string;
}

export interface AgentResponse {
  message: string;
  widget_type?: 'graph' | 'table' | 'pie' | 'bar' | 'kpi';
  widget_data?: any;
  metadata?: {
      cypher?: string;
      question?: string;
  };
}

export interface CommandSuggestion {
    category: string;
    label: string;
    query: string;
}

export const agentService = {
  // ... existing methods ...
  async queryAgent(message: string, history: string[] = [], system_prompt_key: string = "default", request_id?: string): Promise<AgentResponse> {
    const response = await authFetch(`${API_URL}/agent/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history, system_prompt_key, request_id }),
    });

    if (!response.ok) {
      if (response.status === 499) throw new Error('Request cancelled');
      const error = await response.json();
      throw new Error(error.detail || 'Query failed');
    }

    return response.json();
  },

  async cancelRequest(request_id: string): Promise<void> {
      await authFetch(`${API_URL}/agent/cancel/${request_id}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
      });
  },

  async submitFeedback(question: string, cypher: string, rating: number): Promise<boolean> {
      try {
          const response = await authFetch(`${API_URL}/agent/feedback`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ question, cypher, rating }),
          });
          return response.ok;
      } catch (e) {
          console.error("Feedback failed", e);
          return false;
      }
  },

  async getSystemPrompts(): Promise<Record<string, string>> {
      const response = await authFetch(`${API_URL}/agent/prompts`);
      if (!response.ok) return {};
      return response.json();
  },

  async getSuggestions(): Promise<CommandSuggestion[]> {
      const response = await authFetch(`${API_URL}/agent/suggestions`);
      if (!response.ok) return [];
      return response.json();
  },

  async initializeIndex(): Promise<void> {
    const response = await authFetch(`${API_URL}/dashboard/initialize`, { method: 'POST' });
    if (!response.ok) throw new Error('Initialization failed');
  }
};
