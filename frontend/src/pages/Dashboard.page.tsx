import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import { useEffect } from 'react';
import { DashboardCaseWidget } from '@/components/DashboardCaseWidget/DashboardCaseWidget';
import { Stack, Grid } from '@mantine/core';

export function Dashboard() {
  useEffect(() => {
    document.title = 'Dashboard - Æther';
  }, []);
  
  return (
    <>
      <BreadcrumbsBar />
      <Grid gutter="md">
        {/* Linke Spalte für Hauptwidgets */}
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Stack spacing="lg">
            <DashboardCaseWidget />
            {/* Weitere Hauptwidgets hier */}
          </Stack>
        </Grid.Col>

        {/* Rechte Spalte für kleinere Widgets */}
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Stack spacing="lg">
            {/* Kleinere Widgets hier */}
          </Stack>
        </Grid.Col>
      </Grid>
    </>
  );
}
