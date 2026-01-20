import React, { useState } from 'react';
import { TextInput, ActionIcon, Stack, Paper, Text, Loader, Button, Group, Box, ScrollArea, Table } from '@mantine/core'; // Added Table
import { IconSend, IconDatabaseImport } from '@tabler/icons-react';
import { agentService, DashboardResponse } from '../../services/agentService';
import { GraphRAGWidget } from './GraphRAGWidget';
import { notifications } from '@mantine/notifications';

export interface AgentQueryInterfaceProps {
  embedded?: boolean;
}

export const AgentQueryInterface: React.FC<AgentQueryInterfaceProps> = ({ embedded = false }) => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DashboardResponse | null>(null);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const response = await agentService.queryDashboard(query);
      setResult(response);
    } catch (error) {
      console.error(error);
      notifications.show({ color: 'red', message: 'Failed to process query' });
    } finally {
      setLoading(false);
    }
  };

  const handleInitialize = async () => {
      try {
          await agentService.initializeIndex();
          notifications.show({ color: 'green', message: 'Vector Index Initialized' });
      } catch(e) {
          notifications.show({ color: 'red', message: 'Failed to initialize index' });
      }
  };

  const renderTable = (data: any[]) => {
      if (!data || data.length === 0) return <Text>No data</Text>;
      const keys = Object.keys(data[0]);
      
      return (
          <ScrollArea h={300}>
            <Table stickyHeader>
                <Table.Thead>
                    <Table.Tr>
                        {keys.map(k => <Table.Th key={k}>{k}</Table.Th>)}
                    </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                    {data.map((row, i) => (
                        <Table.Tr key={i}>
                            {keys.map(k => (
                                <Table.Td key={k}>
                                    {typeof row[k] === 'object' ? JSON.stringify(row[k]) : String(row[k])}
                                </Table.Td>
                            ))}
                        </Table.Tr>
                    ))}
                </Table.Tbody>
            </Table>
          </ScrollArea>
      );
  };

  const content = (
      <Stack gap="md" h="100%">
          {/* Input Area */}
          <Paper shadow={embedded ? undefined : "sm"} p={embedded ? 0 : "md"} radius="md" withBorder={!embedded} bg={embedded ? "transparent" : undefined}>
            <Stack gap="xs">
                {!embedded && (
                    <Group justify="space-between">
                        <Text fw={500}>Ask Agent</Text>
                        <Button variant="light" size="xs" leftSection={<IconDatabaseImport size={14}/>} onClick={handleInitialize}>Init Index</Button>
                    </Group>
                )}
                {embedded && (
                     <Group justify="flex-end">
                        <Button variant="subtle" size="compact-xs" leftSection={<IconDatabaseImport size={12}/>} onClick={handleInitialize}>Init</Button>
                     </Group>
                )}
                
                <TextInput
                    placeholder="Ask about messages, emotions..."
                    value={query}
                    onChange={(e) => setQuery(e.currentTarget.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                    rightSection={
                        <ActionIcon loading={loading} onClick={handleSearch} variant="filled" color="blue">
                        <IconSend size={16} />
                        </ActionIcon>
                    }
                />
            </Stack>
          </Paper>

          {loading && <Loader mx="auto" />}
          
          {/* Results Area */}
          {result && (
             <Box style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                 {/* Summary inside a scroll area if text is long */}
                 <Paper p="xs" bg="var(--mantine-color-body)" withBorder mb="xs">
                     <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{result.summary}</Text>
                 </Paper>
                 
                 {/* Visualization */}
                 {result.visualization.type === 'graph' && (
                    <Box style={{ flex: 1, minHeight: embedded ? 0 : 400, border: '1px solid var(--mantine-color-default-border)', borderRadius: 'var(--mantine-radius-md)' }}>
                      <GraphRAGWidget data={result.visualization.data} />
                    </Box>
                 )}
                 {result.visualization.type === 'table' && (
                     <Paper withBorder p="xs" style={{ flex: 1, overflow: 'hidden' }}>
                         {Array.isArray(result.visualization.data) && renderTable(result.visualization.data)}
                     </Paper>
                 )}
             </Box>
          )}
      </Stack>
  );

  if (embedded) {
      return content;
  }

  return (
    <Stack gap="md" mb="xl">
        {content}
    </Stack>
  );
};
