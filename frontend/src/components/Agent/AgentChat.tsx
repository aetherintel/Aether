import React, { useState, useEffect, useRef } from 'react';
import { 
    Autocomplete, ActionIcon, Stack, Paper, Text, Loader, Button, 
    Group, Box, ScrollArea, Table, Avatar, Select, Modal, Code, Card, SimpleGrid
} from '@mantine/core';
import { IconSend, IconDatabaseImport, IconRobot, IconUser, IconSettings, IconX } from '@tabler/icons-react';
import { agentService, AgentResponse, CommandSuggestion } from '../../services/agentService';
import { GraphRAGWidget } from '../Dashboard/GraphRAGWidget';
import { notifications } from '@mantine/notifications';
import { PieChart, BarChart } from '@mantine/charts';

interface AgentChatProps {
  embedded?: boolean;
}

interface ChatMessage {
    id: string;
    sender: 'user' | 'agent';
    text: string;
    widgetType?: 'graph' | 'table' | 'pie' | 'bar' | 'kpi';
    widgetData?: any;
    metadata?: any;
    timestamp: Date;
}

export const AgentChat: React.FC<AgentChatProps> = ({ embedded = false }) => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [systemPrompts, setSystemPrompts] = useState<Record<string, string>>({});
  const [activePromptKey, setActivePromptKey] = useState<string>("default");
  const [suggestions, setSuggestions] = useState<CommandSuggestion[]>([]);
  const [activeRequestId, setActiveRequestId] = useState<string | null>(null);
  
  const scrollViewport = useRef<HTMLDivElement>(null);

  useEffect(() => {
      loadSystemPrompts();
      loadSuggestions();
      // Add initial greeting
      setMessages([{
          id: 'init',
          sender: 'agent',
          text: 'Hello! I am your Aether Agent. You can ask me to visualize data, summarize cases, or run analysis. Type `/help` for commands.',
          timestamp: new Date()
      }]);
  }, []);

  useEffect(() => {
      scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
      if (scrollViewport.current) {
          scrollViewport.current.scrollTo({ top: scrollViewport.current.scrollHeight, behavior: 'smooth' });
      }
  };

  const loadSystemPrompts = async () => {
      try {
          const prompts = await agentService.getSystemPrompts();
          setSystemPrompts(prompts);
      } catch (e) {
          console.error("Failed to load prompts", e);
      }
  };

  const loadSuggestions = async () => {
      try {
          const s = await agentService.getSuggestions();
          setSuggestions(s);
      } catch (e) {
          console.error("Failed to load suggestions", e);
      }
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    
    // Generate a unique request ID
    const requestId = Date.now().toString() + Math.random().toString(36).substring(7);
    setActiveRequestId(requestId);

    const userMsg: ChatMessage = {
        id: Date.now().toString(),
        sender: 'user',
        text: query,
        timestamp: new Date()
    };
    
    setMessages(prev => [...prev, userMsg]);
    setQuery('');
    setLoading(true);

    try {
        // Collect history (last 10 messages)
        const history = messages.slice(-10).map(m => `${m.sender}: ${m.text}`);
        
        const response: AgentResponse = await agentService.queryAgent(
            userMsg.text, 
            history, 
            activePromptKey,
            requestId
        );
        
        const agentMsg: ChatMessage = {
            id: (Date.now() + 1).toString(),
            sender: 'agent',
            text: response.message,
            widgetType: response.widget_type as any, // Cast to match extended type
            widgetData: response.widget_data,
            metadata: response.metadata,
            timestamp: new Date()
        };
        
        setMessages(prev => [...prev, agentMsg]);
        
    } catch (error: any) {
      console.error(error);
      
      if (error.message === 'Request cancelled') {
          setMessages(prev => [...prev, {
              id: Date.now().toString(),
              sender: 'agent',
              text: 'Request cancelled.',
              timestamp: new Date()
          }]);
      } else {
          notifications.show({ color: 'red', message: 'Failed to process query' });
          setMessages(prev => [...prev, {
              id: Date.now().toString(),
              sender: 'agent',
              text: 'I encountered an error processing your request.',
              timestamp: new Date()
          }]);
      }
    } finally {
      setLoading(false);
      setActiveRequestId(null);
    }
  };

  const handleCancel = async () => {
      if (activeRequestId) {
          try {
            await agentService.cancelRequest(activeRequestId);
            // UI update handled in catch block of handleSearch
          } catch (e) {
              console.error("Cancel failed", e);
          }
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
      if (!data || data.length === 0) return <Text size="sm">No data to display</Text>;
      const keys = Object.keys(data[0]);
      
      return (
          <ScrollArea h={300}>
            <Table stickyHeader striped highlightOnHover>
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

  const transformPieData = (data: any[]) => {
    if(!data || !data.length) return [];
    const keys = Object.keys(data[0]);
    // Try to find numeric and string keys
    const numKey = keys.find(k => typeof data[0][k] === 'number');
    const strKey = keys.find(k => typeof data[0][k] === 'string');
    
    if(!numKey || !strKey) return []; // Fallback if detection fails
    
    const colors = ['blue', 'teal', 'grape', 'orange', 'red', 'cyan', 'green', 'indigo', 'pink', 'lime'];
    
    return data.map((d, i) => ({
        name: String(d[strKey]),
        value: Number(d[numKey]),
        color: colors[i % colors.length]
    }));
  };

  const transformBarData = (data: any[]) => {
      if(!data || !data.length) return { data: [], series: [], dataKey: '' };
      const keys = Object.keys(data[0]);
      const numKey = keys.find(k => typeof data[0][k] === 'number');
      const strKey = keys.find(k => typeof data[0][k] === 'string');
      
      if(!numKey || !strKey) return { data: [], series: [], dataKey: '' };

      // Mantine BarChart expects data array and series array
      return {
          data: data.map(d => ({ ...d, [strKey]: String(d[strKey]), [numKey]: Number(d[numKey]) })),
          dataKey: strKey,
          series: [{ name: numKey, color: 'blue.6' }] 
      };
  };

  return (
    <Stack gap="md" h="100%">
        {/* Header / Toolbar */}
        <Paper p="xs" shadow="xs" radius="md">
            <Group justify="space-between">
                <Group>
                    <IconRobot size={20} />
                    <Text fw={600}>Agent Chat</Text>
                </Group>
                <Group>
                    <Select 
                        data={Object.keys(systemPrompts).map(k => ({ value: k, label: k }))}
                        value={activePromptKey}
                        onChange={(v) => setActivePromptKey(v || 'default')}
                        size="xs"
                        placeholder="System Prompt"
                        w={150}
                    />
                    <Button variant="light" size="xs" onClick={handleInitialize} leftSection={<IconDatabaseImport size={14}/>}>
                        Re-Index
                    </Button>
                </Group>
            </Group>
        </Paper>

        {/* Chat Area */}
        <Paper flex={1} p="md" radius="md" withBorder bg="var(--mantine-color-body)" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <ScrollArea viewportRef={scrollViewport} style={{ flex: 1 }}>
                <Stack gap="lg" pb="xl">
                    {messages.map((msg) => (
                        <Box key={msg.id} style={{ alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start', maxWidth: '90%' }}>
                            <Group align="flex-start" gap="xs" style={{flexDirection: msg.sender === 'user' ? 'row-reverse' : 'row'}}>
                                <Avatar color={msg.sender === 'user' ? 'blue' : 'green'} radius="xl">
                                    {msg.sender === 'user' ? <IconUser size={18} /> : <IconRobot size={18} />}
                                </Avatar>
                                <Paper withBorder p="sm" radius="md" bg={msg.sender === 'user' ? 'var(--mantine-color-blue-light)' : undefined}>
                                    {/* Text Content */}
                                    <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</Text>
                                    
                                    {/* Widgets */}
                                    {msg.widgetType === 'graph' && (
                                        <Box mt="sm" h={400} w={600} style={{ border: '1px solid var(--mantine-color-default-border)', borderRadius: 'var(--mantine-radius-sm)', position: 'relative' }}>
                                            <GraphRAGWidget data={msg.widgetData} />
                                        </Box>
                                    )}
                                    {msg.widgetType === 'table' && (
                                        <Box mt="sm" w="100%">
                                            {renderTable(msg.widgetData)}
                                        </Box>
                                    )}
                                    
                                    {msg.widgetType === 'pie' && (
                                        <Box mt="sm" h={300} w={400}>
                                            <Text fw={500} size="sm" mb="xs">Distribution</Text>
                                            <PieChart 
                                                data={transformPieData(msg.widgetData)} 
                                                withTooltip 
                                                withLabelsLine 
                                                labelsPosition="outside" 
                                                withLabels 
                                                size={200}
                                            />
                                        </Box>
                                    )}

                                    {msg.widgetType === 'bar' && (
                                        <Box mt="sm" h={300} w={500}>
                                             <Text fw={500} size="sm" mb="xs">Trend Analysis</Text>
                                             {(() => {
                                                 const { data, dataKey, series } = transformBarData(msg.widgetData);
                                                 return (
                                                    <BarChart
                                                        h={250}
                                                        data={data}
                                                        dataKey={dataKey}
                                                        series={series}
                                                        tickLine="y"
                                                    />
                                                 );
                                             })()}
                                        </Box>
                                    )}
                                    
                                    {msg.widgetType === 'kpi' && msg.widgetData && msg.widgetData.length > 0 && (
                                        <Card withBorder radius="md" mt="sm">
                                            <Group justify="space-between">
                                                <Text size="xs" c="dimmed" fw={700} tt="uppercase">
                                                    {Object.keys(msg.widgetData[0])[0]}
                                                </Text>
                                            </Group>
                                            <Group align="flex-end" gap="xs" mt={25}>
                                                <Text style={{ fontSize: '2rem', fontWeight: 700, lineHeight: 1 }}>
                                                    {Object.values(msg.widgetData[0])[0] as React.ReactNode}
                                                </Text>
                                            </Group>
                                        </Card>
                                    )}

                                    {/* Metadata / Cypher Debug */}
                                    {msg.metadata?.cypher && (
                                        <Box mt="xs">
                                            <Text size="xs" c="dimmed" fw={500}>Generated Cypher:</Text>
                                            <Code block>{msg.metadata.cypher}</Code>
                                        </Box>
                                    )}
                                </Paper>
                            </Group>
                        </Box>
                    ))}
                    {loading && (
                        <Group>
                            <Avatar color="green" radius="xl"><IconRobot size={18} /></Avatar>
                            <Loader size="sm" type="dots" />
                        </Group>
                    )}
                </Stack>
            </ScrollArea>
        </Paper>

        {/* Input Area */}
        <Paper p="xs" withBorder radius="md">
            <Autocomplete
                placeholder="Type a message or command (e.g., /visualize query, /summarize)..."
                value={query}
                onChange={setQuery}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                rightSection={
                    loading ? (
                        <ActionIcon onClick={handleCancel} variant="filled" color="red" title="Cancel Request">
                             <IconX size={16} />
                        </ActionIcon>
                    ) : (
                        <ActionIcon onClick={handleSearch} variant="filled" color="blue">
                            <IconSend size={16} />
                        </ActionIcon>
                    )
                }
                data={(() => {
                    const grouped = (suggestions || []).reduce((acc, s) => {
                        if (!acc[s.category]) acc[s.category] = [];
                        acc[s.category].push({ value: s.query, label: s.label });
                        return acc;
                    }, {} as Record<string, { value: string, label: string }[]>);
                    
                    return Object.entries(grouped).map(([group, items]) => ({ group, items }));
                })()}
                limit={20}
            />
        </Paper>
    </Stack>
  );
};
