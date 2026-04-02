import { useEffect } from 'react';
import { Stack, Title } from '@mantine/core';
import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import { AgentChat } from '@/components/Agent/AgentChat';

export function AgentDashboard() {
  useEffect(() => {
    document.title = 'Agent Dashboard - Æther';
  }, []);

  return (
    <Stack gap="md" style={{ height: 'calc(var(--app-shell-main-height, 100dvh) - 2 * var(--mantine-spacing-md))', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
      <AgentChat />
    </Stack>
  );
}
