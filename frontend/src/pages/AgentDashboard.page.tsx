import { useEffect } from 'react';
import { Stack, Title } from '@mantine/core';
import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import { AgentChat } from '@/components/Agent/AgentChat';

export function AgentDashboard() {
  useEffect(() => {
    document.title = 'Agent Dashboard - Æther';
  }, []);

  return (
    <Stack h="100%" gap="md">
      <BreadcrumbsBar />
      <Title order={2}>Conversation Agent</Title>
      <AgentChat />
    </Stack>
  );
}
