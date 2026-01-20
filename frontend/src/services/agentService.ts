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

export interface DashboardResponse {
  summary: string;
  visualization: {
    type: 'graph' | 'table';
    data: any;
  };
  cypher?: string;
}

export const agentService = {
  async queryDashboard(query: string): Promise<DashboardResponse> {
    const token = localStorage.getItem('token');
    if (!token) throw new Error('Not authenticated');

    const response = await fetch(`${API_URL}/text2cypher/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ question: query }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Query failed');
    }

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
