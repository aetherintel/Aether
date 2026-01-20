import { useEffect } from 'react';
import { Stack, Title } from '@mantine/core';
import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import { AgentQueryInterface } from '@/components/Dashboard/AgentQueryInterface';

export function AgentDashboard() {
  useEffect(() => {
    document.title = 'Agent Dashboard - Æther';
  }, []);

  return (
    <Stack h="100%" gap="md">
      <BreadcrumbsBar />
      <Title order={2}>Investigation Agent</Title>
      <AgentQueryInterface />
    </Stack>
  );
}
