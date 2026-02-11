const API_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

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
    const token = localStorage.getItem('token');
    if (!token) throw new Error('Not authenticated');

    const response = await fetch(`${API_URL}/agent/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ 
          message,
          history,
          system_prompt_key,
          request_id
      }),
    });

    if (!response.ok) {
      if (response.status === 499) {
          throw new Error('Request cancelled');
      }
      const error = await response.json();
      throw new Error(error.detail || 'Query failed');
    }

    return response.json();
  },

  async cancelRequest(request_id: string): Promise<void> {
      const token = localStorage.getItem('token');
      if (!token) return;

      await fetch(`${API_URL}/agent/cancel/${request_id}`, {
          method: 'POST',
          headers: {
              Authorization: `Bearer ${token}`
          }
      });
  },

  async getSystemPrompts(): Promise<Record<string, string>> {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/agent/prompts`, {
          headers: { Authorization: `Bearer ${token}` }
      });
      if (!response.ok) {
        // Fallback or empty if failed
        return {};
      }
      return response.json();
  },

  async getSuggestions(): Promise<CommandSuggestion[]> {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/agent/suggestions`, {
          headers: { Authorization: `Bearer ${token}` }
      });
      if (!response.ok) return [];
      return response.json();
  },

  async initializeIndex(): Promise<void> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/dashboard/initialize`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
     if (!response.ok) {
      throw new Error('Initialization failed');
    }
  }
};
