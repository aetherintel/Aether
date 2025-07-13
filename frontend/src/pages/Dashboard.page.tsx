import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import { CaseFileList } from '@/components/CaseFileList/CaseFileList';
import { useEffect } from 'react';
import { Grid } from '@mantine/core';
import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import { DashboardCaseWidget } from '@/components/DashboardCaseWidget/DashboardCaseWidget';
import { TopMessagesWidget } from '@/components/TopMessagesWidget/TopMessagesWidget';
import { TopUserWidget } from '@/components/TopUserWidget/TopUserWidget';

export function Dashboard() {
  useEffect(() => {
    document.title = 'Dashboard - Æther';
  }, []);

  return (
    <>
      <BreadcrumbsBar />
      <Grid gutter="md">
        <Grid.Col span={{ base: 12, sm: 4, lg: 3 }}>
          <DashboardCaseWidget />
        </Grid.Col>
        <Grid.Col span={{ base: 12, sm: 4, lg: 4.5 }}>
          <TopMessagesWidget />
        </Grid.Col>
        <Grid.Col span={{ base: 12, sm: 4, lg: 4.5 }}>
          <TopUserWidget />
        </Grid.Col>
      </Grid>
      <CaseFileList archived={false} />
    </>
  );
}
