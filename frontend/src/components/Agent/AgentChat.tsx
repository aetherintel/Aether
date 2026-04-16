import React, { useState, useEffect, useRef } from 'react';
import {
    Autocomplete, ActionIcon, Stack, Paper, Text, Loader, Button,
    Group, Box, ScrollArea, Table, Avatar, Select, Modal, Code, Card, SimpleGrid, Badge, Collapse
} from '@mantine/core';
import { IconSend, IconDatabaseImport, IconRobot, IconUser, IconX, IconThumbUp, IconThumbDown, IconCode, IconChevronDown } from '@tabler/icons-react';
import { agentService, AgentResponse, CommandSuggestion } from '../../services/agentService';
import { GraphRAGWidget } from '../Dashboard/GraphRAGWidget';
import { notifications } from '@mantine/notifications';
import { PieChart, BarChart } from '@mantine/charts';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion, AnimatePresence } from 'framer-motion';
import { authFetch } from '@/utils/authFetch';
import { LocationMap, MapPoint } from '@/components/map/LocationMap';

interface AgentChatProps {
  embedded?: boolean;
}

interface ChatMessage {
    id: string;
    sender: 'user' | 'agent';
    text: string;
    widgetType?: 'graph' | 'table' | 'pie' | 'bar' | 'kpi' | 'location_map' | 'emotion_analysis' | 'top_influencers';
    widgetData?: any;
    metadata?: any;
    timestamp: Date;
}

const CHAT_STORAGE_KEY = 'aether_agent_chat_history';
const MAX_MESSAGES = 15; // Graphs and maps are heavy — keep DOM small

function loadMessagesFromStorage(): ChatMessage[] {
    try {
        const raw = sessionStorage.getItem(CHAT_STORAGE_KEY);
        if (!raw) return [];
        const parsed: ChatMessage[] = JSON.parse(raw);
        // Re-hydrate Date objects and enforce cap on load
        const hydrated = parsed.map(m => ({ ...m, timestamp: new Date(m.timestamp) }));
        return hydrated.length > MAX_MESSAGES ? hydrated.slice(hydrated.length - MAX_MESSAGES) : hydrated;
    } catch {
        return [];
    }
}

function saveMessagesToStorage(msgs: ChatMessage[]) {
    try {
        // Always cap before saving to prevent storage from growing unbounded
        const toSave = msgs.length > MAX_MESSAGES ? msgs.slice(msgs.length - MAX_MESSAGES) : msgs;
        sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(toSave));
    } catch {
        // sessionStorage full or unavailable — silently ignore
    }
}

export const AgentChat: React.FC<AgentChatProps> = ({ embedded = false }) => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
      const stored = loadMessagesFromStorage(); // already capped at MAX_MESSAGES
      if (stored.length > 0) return stored;
      return [{
          id: 'init',
          sender: 'agent',
          text: '👋 **Hello!** I am your **Aether Agent**.\n\nAsk me anything in natural language, or use slash commands like `/visualize`, `/showmap`, `/summarize`. Type `/help` for a full list.',
          timestamp: new Date()
      }];
  });

  const [suggestions, setSuggestions] = useState<CommandSuggestion[]>([]);
  const [activeRequestId, setActiveRequestId] = useState<string | null>(null);
  const [expandedCypher, setExpandedCypher] = useState<Set<string>>(new Set());
  const [slowQuery, setSlowQuery] = useState(false);
  const slowQueryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const scrollViewport = useRef<HTMLDivElement>(null);

  useEffect(() => {
      loadSuggestions();
  }, []);

  // Persist chat history to sessionStorage whenever messages change
  useEffect(() => {
      saveMessagesToStorage(messages);
  }, [messages]);

  useEffect(() => {
      scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
      if (scrollViewport.current) {
          setTimeout(() => {
              scrollViewport.current?.scrollTo({ top: scrollViewport.current.scrollHeight, behavior: 'smooth' });
          }, 100);
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
    
    setMessages(prev => {
        const next = [...prev, userMsg];
        return next.length > MAX_MESSAGES ? next.slice(next.length - MAX_MESSAGES) : next;
    });
    setQuery('');
    setLoading(true);
    setSlowQuery(false);
    slowQueryTimer.current = setTimeout(() => setSlowQuery(true), 8000);

    try {
        // Collect history (last 10 messages)
        const history = messages.slice(-10).map(m => `${m.sender}: ${m.text}`);
        
        const response: AgentResponse = await agentService.queryAgent(
            userMsg.text, 
            history, 
            "default",
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
        
        setMessages(prev => {
            const next = [...prev, agentMsg];
            return next.length > MAX_MESSAGES ? next.slice(next.length - MAX_MESSAGES) : next;
        });

    } catch (error: any) {
      console.error(error);

      if (error.message === 'Request cancelled') {
          setMessages(prev => {
              const next = [...prev, { id: Date.now().toString(), sender: 'agent' as const, text: 'Request cancelled.', timestamp: new Date() }];
              return next.length > MAX_MESSAGES ? next.slice(next.length - MAX_MESSAGES) : next;
          });
      } else {
          notifications.show({ color: 'red', message: 'Failed to process query' });
          setMessages(prev => {
              const next = [...prev, { id: Date.now().toString(), sender: 'agent' as const, text: 'I encountered an error processing your request.', timestamp: new Date() }];
              return next.length > MAX_MESSAGES ? next.slice(next.length - MAX_MESSAGES) : next;
          });
      }
    } finally {
      setLoading(false);
      setActiveRequestId(null);
      setSlowQuery(false);
      if (slowQueryTimer.current) {
          clearTimeout(slowQueryTimer.current);
          slowQueryTimer.current = null;
      }
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
      
      // Fields we don't want to show the user in a raw table view
      const ignoredKeys = ['owner_id', 'mid', '_id', 'geolocation_status', 'image_analysis_status', 'audio_transcription_status', 'translation_status'];
      const keys = Object.keys(data[0]).filter(k => !ignoredKeys.includes(k));
      
      if (keys.length === 0) return <Text size="sm">No displayable data</Text>;

      return (
          <ScrollArea h={350}>
            <Table stickyHeader striped highlightOnHover>
                <Table.Thead>
                    <Table.Tr>
                        {keys.map(k => <Table.Th key={k}>{k.replace(/_/g, ' ')}</Table.Th>)}
                    </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                    {data.map((row, i) => (
                        <Table.Tr key={i}>
                            {keys.map(k => {
                                const val = row[k];
                                let displayVal: React.ReactNode = String(val);
                                
                                if (val === null || val === undefined) {
                                    displayVal = <Text c="dimmed" fs="italic" size="sm">null</Text>;
                                } else if (typeof val === 'boolean') {
                                    displayVal = <Badge color={val ? 'green' : 'gray'}>{val ? 'Yes' : 'No'}</Badge>;
                                } else if (typeof val === 'object' && val !== null) {
                                    if (Array.isArray(val)) {
                                        displayVal = <Text size="sm">{val.join(', ')}</Text>;
                                    } else {
                                        const objKeys = Object.keys(val);
                                        if (objKeys.length === 0) {
                                            displayVal = <Text size="sm" c="dimmed" fs="italic">Empty</Text>;
                                        } else {
                                            displayVal = (
                                                <Table withTableBorder withColumnBorders>
                                                    <Table.Tbody>
                                                        {objKeys.map(ok => (
                                                            <Table.Tr key={ok}>
                                                                <Table.Td fw={500} style={{ padding: '2px 4px', fontSize: '0.75rem' }}>{ok}</Table.Td>
                                                                <Table.Td style={{ padding: '2px 4px', fontSize: '0.75rem' }}>
                                                                    {typeof val[ok] === 'object' ? JSON.stringify(val[ok]) : String(val[ok])}
                                                                </Table.Td>
                                                            </Table.Tr>
                                                        ))}
                                                    </Table.Tbody>
                                                </Table>
                                            );
                                        }
                                    }
                                } else if (typeof val === 'string' && val.length > 100) {
                                    // Truncate long strings for better table UX
                                    displayVal = <Text size="sm" lineClamp={3} title={val}>{val}</Text>;
                                } else {
                                    displayVal = <Text size="sm">{String(val)}</Text>;
                                }
                                
                                return (
                                    <Table.Td key={k} style={{ maxWidth: 300, verticalAlign: 'top' }}>
                                        {displayVal}
                                    </Table.Td>
                                );
                            })}
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
    <Stack
      gap="md"
      style={{
        height: 'calc(100dvh - 60px - 2 * var(--mantine-spacing-md))',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
        {/* Header / Toolbar */}
        <Paper p="xs" shadow="xs" radius="md" style={{ flexShrink: 0 }}>
            <Group justify="space-between">
                <Group>
                    <IconRobot size={20} />
                    <Text fw={600}>Agent Chat</Text>
                </Group>
                <Group>
                    <Button variant="light" size="xs" onClick={handleInitialize} leftSection={<IconDatabaseImport size={14}/>}>
                        Re-Index
                    </Button>
                </Group>
            </Group>
        </Paper>

        {/* Chat Area */}
        <Paper p="md" radius="md" withBorder bg="var(--mantine-color-gray-0)" style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <ScrollArea viewportRef={scrollViewport} style={{ flex: 1, minHeight: 0 }}>
                <Stack gap="lg" pb="xl">
                    <AnimatePresence initial={false}>
                        {messages.map((msg) => (
                            <motion.div
                                key={msg.id}
                                initial={{ opacity: 0, y: 20, scale: 0.95 }}
                                animate={{ opacity: 1, y: 0, scale: 1 }}
                                transition={{ duration: 0.3 }}
                                style={{ 
                                    alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start', 
                                    maxWidth: '92%',
                                    width: 'fit-content' // Important for alignment
                                }}
                            >
                                <Group align="flex-start" gap="xs" style={{flexDirection: msg.sender === 'user' ? 'row-reverse' : 'row'}}>
                                    <Avatar color={msg.sender === 'user' ? 'blue' : 'green'} radius="xl" size="md">
                                        {msg.sender === 'user' ? <IconUser size={20} /> : <IconRobot size={20} />}
                                    </Avatar>
                                    
                                    <Paper 
                                        withBorder 
                                        p="md" 
                                        radius="lg" 
                                        bg={msg.sender === 'user' ? 'blue.0' : 'white'}
                                        shadow="sm"
                                        style={{ minWidth: 200 }}
                                    >
                                        {/* Markdown Text Content */}
                                        <div className="markdown-body" style={{ fontSize: '0.95rem', lineHeight: 1.6 }}>
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                {msg.text}
                                            </ReactMarkdown>
                                        </div>
                                        
                                        {/* Widgets */}
                                        {msg.widgetType === 'graph' && (
                                            <Box mt="md" h={500} w={700} style={{ border: '1px solid #374151', borderRadius: '8px', overflow: 'hidden' }}>
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
                                                 {(() => {
                                                     const { data, dataKey, series } = transformBarData(msg.widgetData);
                                                     const valueKey = series[0]?.name || '';
                                                     const title = valueKey
                                                         ? `${valueKey.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())} by ${dataKey.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}`
                                                         : 'Results';
                                                     return (
                                                         <>
                                                             <Text fw={500} size="sm" mb="xs">{title}</Text>
                                                             <BarChart
                                                                 h={250}
                                                                 data={data}
                                                                 dataKey={dataKey}
                                                                 series={series}
                                                                 tickLine="y"
                                                             />
                                                         </>
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
                                                        {String(Object.values(msg.widgetData[0])[0])}
                                                    </Text>
                                                </Group>
                                            </Card>
                                        )}

                                        {/* 🎯 Location Map — shared LocationMap component */}
                                        {msg.widgetType === 'location_map' && msg.widgetData && msg.widgetData.length > 0 && (() => {
                                            const points: MapPoint[] = msg.widgetData
                                                .filter((d: any) => (d.lat ?? d.latitude) != null && (d.lng ?? d.longitude) != null)
                                                .map((d: any, i: number) => ({
                                                    id: d.message_id ?? `${i}`,
                                                    lat: d.lat ?? d.latitude,
                                                    lng: d.lng ?? d.longitude,
                                                    canonical_name: d.canonical_name ?? d.name,
                                                    country: d.country,
                                                    mention_count: d.mention_count,
                                                    sample_messages: d.sample_messages,
                                                }));
                                            if (points.length === 0) return null;
                                            return (
                                                <Box mt="md" style={{ minWidth: 520, width: '100%' }}>
                                                    <LocationMap points={points} height={400} />
                                                </Box>
                                            );
                                        })()}

                                        {/* 🎯 Emotion Analysis Widget - Auto-detected for emotion queries */}
                                        {msg.widgetType === 'emotion_analysis' && msg.widgetData && msg.widgetData.length > 0 && (
                                            <Box mt="md">
                                                <Text fw={500} size="sm" mb="xs" c="dimmed">💭 Emotion Analysis</Text>
                                                <Card withBorder radius="md" p="sm">
                                                    <SimpleGrid cols={2} spacing="xs">
                                                        {msg.widgetData.slice(0, 6).map((item: any, idx: number) => {
                                                            const emotion = Object.keys(item)[0];
                                                            const score = Object.values(item)[0];
                                                            const emoji = emotion === 'anger' ? '😠' : 
                                                                          emotion === 'joy' ? '😊' : 
                                                                          emotion === 'fear' ? '😨' : 
                                                                          emotion === 'sadness' ? '😢' : 
                                                                          emotion === 'surprise' ? '😲' : 
                                                                          emotion === 'disgust' ? '🤢' : 
                                                                          emotion === 'love' ? '❤️' : '😐';
                                                            return (
                                                                <Paper key={idx} p="xs" withBorder>
                                                                    <Group>
                                                                        <Text size="xl">{emoji}</Text>
                                                                        <Box>
                                                                            <Text size="sm" fw={500} tt="capitalize">{emotion}</Text>
                                                                            <Text size="xs" c="dimmed">{String(score)}</Text>
                                                                        </Box>
                                                                    </Group>
                                                                </Paper>
                                                            );
                                                        })}
                                                    </SimpleGrid>
                                                </Card>
                                            </Box>
                                        )}

                                        {/* 🎯 Top Influencers Widget - Auto-detected for user activity queries */}
                                        {msg.widgetType === 'top_influencers' && msg.widgetData && msg.widgetData.length > 0 && (
                                            <Box mt="md">
                                                <Text fw={500} size="sm" mb="xs" c="dimmed">🏆 Top Contributors</Text>
                                                <Card withBorder radius="md" p="sm">
                                                    <Stack gap="xs">
                                                        {msg.widgetData.slice(0, 10).map((item: any, idx: number) => (
                                                            <Paper key={idx} p="xs" withBorder>
                                                                <Group justify="space-between">
                                                                    <Group>
                                                                        <Avatar size="sm" color="blue">
                                                                            {idx + 1}
                                                                        </Avatar>
                                                                        <Box>
                                                                            <Text size="sm" fw={500}>
                                                                                {item.username || item.user || item.author || item.name || 'Unknown'}
                                                                            </Text>
                                                                            {item.channel && <Text size="xs" c="dimmed">#{item.channel}</Text>}
                                                                        </Box>
                                                                    </Group>
                                                                    <Badge color="grape">
                                                                        {item.message_count || item.count || item.messages || 0} msgs
                                                                    </Badge>
                                                                </Group>
                                                            </Paper>
                                                        ))}
                                                    </Stack>
                                                </Card>
                                            </Box>
                                        )}

                                        {/* Feedback + collapsible Cypher debug */}
                                        {msg.metadata?.cypher && (
                                            <Box mt="xs">
                                                <Group gap="xs" align="center">
                                                    <Text size="xs" c="dimmed">Rate this result:</Text>
                                                    <ActionIcon
                                                        variant="subtle"
                                                        color="green"
                                                        size="sm"
                                                        onClick={() => {
                                                            agentService.submitFeedback(
                                                                msg.metadata.question || "Unknown",
                                                                msg.metadata.cypher,
                                                                1
                                                            );
                                                            notifications.show({ message: 'Thanks for the feedback!', color: 'green' });
                                                        }}
                                                        title="Good result"
                                                    >
                                                        <IconThumbUp size={14} />
                                                    </ActionIcon>
                                                    <ActionIcon
                                                        variant="subtle"
                                                        color="red"
                                                        size="sm"
                                                        onClick={() => {
                                                            agentService.submitFeedback(
                                                                msg.metadata.question || "Unknown",
                                                                msg.metadata.cypher,
                                                                -1
                                                            );
                                                            notifications.show({ message: 'Feedback recorded', color: 'gray' });
                                                        }}
                                                        title="Bad result"
                                                    >
                                                        <IconThumbDown size={14} />
                                                    </ActionIcon>
                                                    <ActionIcon
                                                        variant="subtle"
                                                        color="gray"
                                                        size="sm"
                                                        onClick={() => setExpandedCypher(prev => {
                                                            const next = new Set(prev);
                                                            next.has(msg.id) ? next.delete(msg.id) : next.add(msg.id);
                                                            return next;
                                                        })}
                                                        title="Show generated query"
                                                    >
                                                        {expandedCypher.has(msg.id) ? <IconChevronDown size={14} /> : <IconCode size={14} />}
                                                    </ActionIcon>
                                                </Group>
                                                <Collapse in={expandedCypher.has(msg.id)}>
                                                    <Box mt="xs">
                                                        <Text size="xs" c="dimmed" fw={500} mb={4}>Generated Query:</Text>
                                                        <Code block style={{ fontSize: '0.72rem' }}>
                                                            {msg.metadata.cypher
                                                                ?.replace(/\b\w+\.owner_id\s*=\s*'[^']*'\s*(AND\s*)?/gi, '')
                                                                .replace(/\bAND\s+RETURN\b/gi, 'RETURN')
                                                                .replace(/WHERE\s+RETURN/gi, 'RETURN')
                                                                .trim()}
                                                        </Code>
                                                    </Box>
                                                </Collapse>
                                            </Box>
                                        )}
                                    </Paper>
                                </Group>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                    
                    {loading && (
                        <Group ml={50} align="center">
                            <Loader size="sm" type="dots" color={slowQuery ? "orange" : "gray"} />
                            <Text size="xs" c={slowQuery ? "orange" : "dimmed"} fs="italic">
                                {slowQuery ? "Still working — complex query, almost there..." : "Analyzing..."}
                            </Text>
                        </Group>
                    )}
                </Stack>
            </ScrollArea>
        </Paper>

        {/* Input — pinned at bottom, always visible */}
        <Paper p="sm" withBorder radius="lg" shadow="sm" style={{ flexShrink: 0 }}>
            <Group gap="xs" align="flex-end">
                <Autocomplete
                    placeholder="Ask anything… e.g. 'Show map of negative emotions' or '/showmap'"
                    value={query}
                    onChange={setQuery}
                    onKeyDown={(e) => e.key === 'Enter' && !loading && handleSearch()}
                    size="md"
                    radius="md"
                    style={{ flex: 1 }}
                    rightSectionWidth={0}
                    data={(suggestions || []).map(s => s.query)}
                    limit={10}
                />
                {loading ? (
                    <ActionIcon
                        onClick={handleCancel}
                        variant="filled"
                        color="red"
                        size="42"
                        radius="md"
                        title="Cancel"
                    >
                        <IconX size={18} />
                    </ActionIcon>
                ) : (
                    <ActionIcon
                        onClick={handleSearch}
                        variant="filled"
                        color="blue"
                        size="42"
                        radius="md"
                        disabled={!query.trim()}
                        title="Send"
                    >
                        <IconSend size={18} />
                    </ActionIcon>
                )}
            </Group>
        </Paper>
    </Stack>
  );
};
