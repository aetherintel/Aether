import { useEffect } from 'react';
import { AgentChat } from '@/components/Agent/AgentChat';

export function AgentDashboard() {
  useEffect(() => {
    document.title = 'Agent Dashboard - Æther';
  }, []);

  return <AgentChat />;
}
