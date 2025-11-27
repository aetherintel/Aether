import { Table, Button, Text, Paper, Anchor, Group, Title, Select, MultiSelect, Stack, ActionIcon } from '@mantine/core';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { IconDownload, IconFileAnalytics, IconSettings, IconDeviceFloppy } from '@tabler/icons-react';
import { useState, useEffect } from 'react';
import { notifications } from '@mantine/notifications';
import { authFetch } from '@/utils/authFetch';

interface Report {
  filename: string;
  size: number;
  created: string;
  url: string;
}

interface ReportsTabProps {
  caseId: string;
  initialConfig?: {
    report_frequency: string;
    report_sections: string[];
  };
}

const fetchReports = async (caseId: string) => {
  const response = await authFetch(`/api/reports/list/${caseId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch reports');
  }
  return response.json();
};

export default function ReportsTab({ caseId, initialConfig }: ReportsTabProps) {
  const queryClient = useQueryClient();
  const [frequency, setFrequency] = useState(initialConfig?.report_frequency || 'daily');
  const [sections, setSections] = useState<string[]>(initialConfig?.report_sections || ['stats', 'charts', 'messages']);

  // Sync state if props change (e.g. initial load)
  useEffect(() => {
    if (initialConfig) {
      setFrequency(initialConfig.report_frequency);
      setSections(initialConfig.report_sections);
    }
  }, [initialConfig]);

  const { data: reports, isLoading, error } = useQuery<Report[]>({
    queryKey: ['reports', caseId],
    queryFn: () => fetchReports(caseId),
    enabled: !!caseId
  });

  const updateConfigMutation = useMutation({
    mutationFn: async (values: { report_frequency: string; report_sections: string[] }) => {
      const res = await authFetch(`/api/casefiles/${caseId}/report-config`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });
      if (!res.ok) throw new Error('Failed to update config');
      return res.json();
    },
    onSuccess: () => {
      notifications.show({
        title: 'Success',
        message: 'Report configuration updated',
        color: 'green',
      });
      queryClient.invalidateQueries({ queryKey: ['caseFile', caseId] });
    },
    onError: () => {
      notifications.show({
        title: 'Error',
        message: 'Failed to update configuration',
        color: 'red',
      });
    },
  });

  const generateReportMutation = useMutation({
    mutationFn: async () => {
      const res = await authFetch(`/api/reports/generate/${caseId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          period: frequency,
          sections: sections,
        }),
      });
      if (!res.ok) throw new Error('Failed to generate report');
      return res.json();
    },
    onSuccess: () => {
      notifications.show({
        title: 'Success',
        message: 'Report generated successfully',
        color: 'green',
      });
      queryClient.invalidateQueries({ queryKey: ['reports', caseId] });
    },
    onError: () => {
      notifications.show({
        title: 'Error',
        message: 'Failed to generate report',
        color: 'red',
      });
    },
  });

  const handleSaveConfig = () => {
    updateConfigMutation.mutate({
      report_frequency: frequency,
      report_sections: sections,
    });
  };

  if (isLoading) return <Text>Loading reports...</Text>;
  if (error) return <Text c="red">Error loading reports</Text>;

  const rows = reports?.map((report) => (
    <Table.Tr key={report.filename}>
      <Table.Td>{report.filename}</Table.Td>
      <Table.Td>{new Date(report.created).toLocaleString()}</Table.Td>
      <Table.Td>{(report.size / 1024).toFixed(2)} KB</Table.Td>
      <Table.Td>
        <Anchor href={report.url} target="_blank" download>
          <Button leftSection={<IconDownload size={14} />} variant="light" size="xs">
            Download
          </Button>
        </Anchor>
      </Table.Td>
    </Table.Tr>
  ));

  return (
    <Stack gap="lg">
      <Paper shadow="xs" p="md" withBorder>
        <Group justify="space-between" mb="md">
          <Group>
            <IconSettings size={24} />
            <Title order={4}>Configuration</Title>
          </Group>
          <Group>
            <Button 
              variant="default"
              onClick={() => generateReportMutation.mutate()}
              loading={generateReportMutation.isPending}
            >
              Generate Report Now
            </Button>
            <Button 
              leftSection={<IconDeviceFloppy size={16} />} 
              onClick={handleSaveConfig}
              loading={updateConfigMutation.isPending}
            >
              Save Configuration
            </Button>
          </Group>
        </Group>
        
        <Group grow align="flex-start">
          <Select
            label="Frequency"
            description="How often to generate reports"
            data={[
              { value: 'daily', label: 'Daily (Midnight)' },
              { value: 'weekly', label: 'Weekly (Monday)' },
              { value: 'monthly', label: 'Monthly (1st)' },
              { value: 'none', label: 'Disabled' },
            ]}
            value={frequency}
            onChange={(val) => setFrequency(val || 'daily')}
          />
          <MultiSelect
            label="Content"
            description="Sections to include in the report"
            data={[
              { value: 'stats', label: 'Statistics' },
              { value: 'charts', label: 'Charts' },
              { value: 'messages', label: 'Message Log' },
            ]}
            value={sections}
            onChange={setSections}
          />
        </Group>
      </Paper>

      <Paper shadow="xs" p="md" withBorder>
        <Group mb="md">
          <IconFileAnalytics size={24} />
          <Title order={4}>Generated Reports</Title>
        </Group>
        
        {reports && reports.length > 0 ? (
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Filename</Table.Th>
                <Table.Th>Created At</Table.Th>
                <Table.Th>Size</Table.Th>
                <Table.Th>Action</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>{rows}</Table.Tbody>
          </Table>
        ) : (
          <Text c="dimmed" ta="center" py="xl">
            No reports available. Reports are generated automatically based on the configuration above.
          </Text>
        )}
      </Paper>
    </Stack>
  );
}
