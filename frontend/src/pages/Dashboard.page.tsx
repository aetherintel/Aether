// src/pages/Dashboard.page.tsx
import { useEffect } from 'react';
import { Container, Title, Text, Group, Button } from '@mantine/core';
import { IconLayoutDashboard, IconHelp } from '@tabler/icons-react';
import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import { WidgetGrid } from '@/components/WidgetGrid/WidgetGrid';
import { AgentQueryInterface } from '@/components/Dashboard/AgentQueryInterface';
import { useWidgetStore } from '@/store/client/widgetStore';
import classes from './Dashboard.module.css';

export function Dashboard() {
  const { layouts, activeLayoutId, setActiveLayout } = useWidgetStore();

  useEffect(() => {
    document.title = 'Dashboard - Æther';
    
    // Set default active layout if not set
    if (!activeLayoutId && layouts.length > 0) {
      setActiveLayout(layouts[0].id);
    }
  }, [activeLayoutId, layouts, setActiveLayout]);

  return (
    <Container fluid className={classes.container}>
      <BreadcrumbsBar />
      
      {/* Dashboard Header */}
      <Group justify="space-between" mb="lg">
        <div>
          <Group gap="xs" mb="xs">
            <IconLayoutDashboard size={24} />
            <Title order={2}>Dashboard</Title>
          </Group>
          <Text size="sm" c="dimmed">
            Monitor and analyze your Telegram channels with customizable widgets
          </Text>
        </div>
        
        <Button
          variant="subtle"
          leftSection={<IconHelp size={16} />}
          onClick={() => {
            // TODO: Open help modal or documentation
            console.log('Open help documentation');
          }}
        >
          Help
        </Button>
      </Group>


      {/* Widget Grid */}
      <WidgetGrid category="dashboard" />
    </Container>
  );
}