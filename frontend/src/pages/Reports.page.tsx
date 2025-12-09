import { useEffect, useState } from 'react';
import { Container, Title, Text, Group, Paper, Grid, Stack, SimpleGrid, Button, Select, MultiSelect, Table, Anchor, ActionIcon } from '@mantine/core';
import { IconFileAnalytics, IconDownload, IconChartBar, IconUsers, IconMessage, IconTrendingUp, IconSettings, IconDeviceFloppy } from '@tabler/icons-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notifications } from '@mantine/notifications';
import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import { WidgetGrid } from '@/components/WidgetGrid/WidgetGrid';
import { authFetch } from '@/utils/authFetch';
import classes from './Reports.module.css';

interface StatsOverview {
  totalCases: number;
  totalChannels: number;
  totalMessages: number;
  activeScrapers: number;
}

interface Report {
  filename: string;
  size: number;
  created: string;
  url: string;
  case_id: number;
  case_title?: string;
}

/**
 * Fetch general statistics across all cases
 */
const fetchStats = async (): Promise<StatsOverview> => {
  const response = await authFetch('/api/stats/overview');
  if (!response.ok) throw new Error('Failed to fetch stats');
  return response.json();
};

/**
 * Fetch all generated reports
 */
const fetchAllReports = async (): Promise<Report[]> => {
  const response = await authFetch('/api/reports/list');
  if (!response.ok) throw new Error('Failed to fetch reports');
  return response.json();
};

export function Reports() {
  const queryClient = useQueryClient();
  const [selectedCase, setSelectedCase] = useState<string | null>(null);

  useEffect(() => {
    document.title = 'Reports & Analytics - Æther';
  }, []);

  const { data: stats, isLoading: statsLoading } = useQuery<StatsOverview>({
    queryKey: ['stats-overview'],
    queryFn: fetchStats,
  });

  const { data: reports, isLoading: reportsLoading } = useQuery<Report[]>({
    queryKey: ['all-reports'],
    queryFn: fetchAllReports,
    refetchInterval: 30000,
  });

  const filteredReports = selectedCase 
    ? reports?.filter(r => r.case_id.toString() === selectedCase)
    : reports;

  return (
    <Container fluid className={classes.container}>
      <BreadcrumbsBar />
      
      {/* Header */}
      <Group justify="space-between" mb="xl">
        <div>
          <Group gap="xs" mb="xs">
            <IconFileAnalytics size={28} />
            <Title order={2}>Reports & Analytics</Title>
          </Group>
          <Text size="sm" c="dimmed">
            Personalisiertes Dashboard mit Datenübersicht und Report-Downloads
          </Text>
        </div>
      </Group>

      {/* Stats Overview */}
      <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }} mb="xl" spacing="md">
        <Paper withBorder p="md" radius="md" className={classes.statCard}>
          <Group gap="xs">
            <IconChartBar size={24} color="var(--mantine-color-blue-6)" />
            <div>
              <Text size="xs" c="dimmed" tt="uppercase" fw={700}>Cases</Text>
              <Text size="xl" fw={700}>{stats?.totalCases ?? 0}</Text>
            </div>
          </Group>
        </Paper>

        <Paper withBorder p="md" radius="md" className={classes.statCard}>
          <Group gap="xs">
            <IconUsers size={24} color="var(--mantine-color-teal-6)" />
            <div>
              <Text size="xs" c="dimmed" tt="uppercase" fw={700}>Channels</Text>
              <Text size="xl" fw={700}>{stats?.totalChannels ?? 0}</Text>
            </div>
          </Group>
        </Paper>

        <Paper withBorder p="md" radius="md" className={classes.statCard}>
          <Group gap="xs">
            <IconMessage size={24} color="var(--mantine-color-violet-6)" />
            <div>
              <Text size="xs" c="dimmed" tt="uppercase" fw={700}>Messages</Text>
              <Text size="xl" fw={700}>{stats?.totalMessages?.toLocaleString() ?? 0}</Text>
            </div>
          </Group>
        </Paper>

        <Paper withBorder p="md" radius="md" className={classes.statCard}>
          <Group gap="xs">
            <IconTrendingUp size={24} color="var(--mantine-color-green-6)" />
            <div>
              <Text size="xs" c="dimmed" tt="uppercase" fw={700}>Active Scrapers</Text>
              <Text size="xl" fw={700}>{stats?.activeScrapers ?? 0}</Text>
            </div>
          </Group>
        </Paper>
      </SimpleGrid>

      {/* Widget Dashboard */}
      <Paper withBorder p="md" radius="md" mb="xl">
        <Group mb="md">
          <IconChartBar size={20} />
          <Title order={4}>Personalisiertes Dashboard</Title>
        </Group>
        <WidgetGrid category="dashboard" />
      </Paper>

      {/* Reports Section */}
      <Paper withBorder p="md" radius="md">
        <Stack gap="md">
          <Group justify="space-between">
            <Group>
              <IconFileAnalytics size={20} />
              <Title order={4}>Generierte Reports</Title>
            </Group>
            <Select
              placeholder="Filter by case"
              data={reports?.map(r => ({ 
                value: r.case_id.toString(), 
                label: r.case_title || `Case ${r.case_id}` 
              })) || []}
              value={selectedCase}
              onChange={setSelectedCase}
              clearable
              style={{ width: 250 }}
            />
          </Group>

          {filteredReports && filteredReports.length > 0 ? (
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Filename</Table.Th>
                  <Table.Th>Case</Table.Th>
                  <Table.Th>Created</Table.Th>
                  <Table.Th>Size</Table.Th>
                  <Table.Th>Action</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {filteredReports.map((report) => (
                  <Table.Tr key={report.filename}>
                    <Table.Td>{report.filename}</Table.Td>
                    <Table.Td>{report.case_title || `Case ${report.case_id}`}</Table.Td>
                    <Table.Td>{new Date(report.created).toLocaleString()}</Table.Td>
                    <Table.Td>{(report.size / 1024).toFixed(2)} KB</Table.Td>
                    <Table.Td>
                      <Anchor href={report.url} target="_blank" download>
                        <Button 
                          leftSection={<IconDownload size={14} />} 
                          variant="light" 
                          size="xs"
                        >
                          Download
                        </Button>
                      </Anchor>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          ) : (
            <Text c="dimmed" ta="center" py="xl">
              {reportsLoading ? 'Loading reports...' : 'Keine Reports verfügbar'}
            </Text>
          )}
        </Stack>
      </Paper>
    </Container>
  );
}