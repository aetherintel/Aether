import React, { useState, useEffect, useRef } from 'react';
import {
    Autocomplete, ActionIcon, Stack, Paper, Text, Loader, Button,
    Group, Box, ScrollArea, Table, Avatar, Select, Modal, Code, Card, SimpleGrid, Badge, Collapse
} from '@mantine/core';
import { IconSend, IconDatabaseImport, IconRobot, IconUser, IconSettings, IconX, IconThumbUp, IconThumbDown, IconCode, IconChevronDown, IconChevronRight } from '@tabler/icons-react';
import { agentService, AgentResponse, CommandSuggestion } from '../../services/agentService';
import { GraphRAGWidget } from '../Dashboard/GraphRAGWidget';
import { notifications } from '@mantine/notifications';
import { PieChart, BarChart } from '@mantine/charts';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion, AnimatePresence } from 'framer-motion';
import { MapContainer, TileLayer, Marker, Popup, useMap, LayersControl, LayerGroup } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { OSINT_ICONS, OSINT_LABELS } from '@/utils/osintIcons';
import { authFetch } from '@/utils/authFetch';

const AGENT_ESRI_KEY = import.meta.env.VITE_ESRI_API_KEY ?? '';
const agentApiUrl = import.meta.env.VITE_API_URL;

// Fix Leaflet default marker icons
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const FitMapBounds: React.FC<{ points: Array<{ lat: number; lng: number }> }> = ({ points }) => {
    const map = useMap();
    useEffect(() => {
        if (points.length > 0) {
            const bounds = L.latLngBounds(points.map(p => [p.lat, p.lng]));
            map.fitBounds(bounds, { padding: [40, 40] });
        }
    }, [points, map]);
    return null;
};

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

function loadMessagesFromStorage(): ChatMessage[] {
    try {
        const raw = sessionStorage.getItem(CHAT_STORAGE_KEY);
        if (!raw) return [];
        const parsed: ChatMessage[] = JSON.parse(raw);
        // Re-hydrate Date objects
        return parsed.map(m => ({ ...m, timestamp: new Date(m.timestamp) }));
    } catch {
        return [];
    }
}

function saveMessagesToStorage(msgs: ChatMessage[]) {
    try {
        sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(msgs));
    } catch {
        // sessionStorage full or unavailable — silently ignore
    }
}

export const AgentChat: React.FC<AgentChatProps> = ({ embedded = false }) => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
      const stored = loadMessagesFromStorage();
      if (stored.length > 0) return stored;
      return [{
          id: 'init',
          sender: 'agent',
          text: '👋 **Hello!** I am your **Aether Agent**. \n\nYou can ask me to `visualize data`, `summarize cases`, or run analysis.\n\nType `/help` for commands.',
          timestamp: new Date()
      }];
  });

  const [suggestions, setSuggestions] = useState<CommandSuggestion[]>([]);
  const [activeRequestId, setActiveRequestId] = useState<string | null>(null);
  const [expandedCypher, setExpandedCypher] = useState<Set<string>>(new Set());
  const [slowQuery, setSlowQuery] = useState(false);
  const [agentOsintData, setAgentOsintData] = useState<Record<string, Record<string, any[]>>>({});
  const [loadingAgentOsint, setLoadingAgentOsint] = useState<Record<string, boolean>>({});

  const loadAgentOsintLayers = async (msgId: string, lat: number, lng: number) => {
    setLoadingAgentOsint(prev => ({ ...prev, [msgId]: true }));
    try {
      const base = agentApiUrl ?? 'http://localhost:8000/api';
      const res = await authFetch(
        `${base}/geo/osint-layers?lat=${lat}&lng=${lng}&radius=500&layers=cameras,atm,bank,police,military,power,water,alpr`
      );
      const data = await res.json();
      setAgentOsintData(prev => ({ ...prev, [msgId]: data }));
    } catch (err) {
      console.error('Failed to load OSINT layers for agent chat:', err);
    } finally {
      setLoadingAgentOsint(prev => ({ ...prev, [msgId]: false }));
    }
  };
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
    
    setMessages(prev => [...prev, userMsg]);
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
    <Stack gap="md" h="100%">
        {/* Header / Toolbar */}
        <Paper p="xs" shadow="xs" radius="md">
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
        <Paper flex={1} p="md" radius="md" withBorder bg="var(--mantine-color-gray-0)" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <ScrollArea viewportRef={scrollViewport} style={{ flex: 1 }}>
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
                                onLayoutAnimationComplete={() => console.log("MSG DEBUG:", msg)}
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

                                        {/* 🎯 Location Map Widget - Interactive Leaflet map with Satellite + OSINT */}
                                        {msg.widgetType === 'location_map' && msg.widgetData && msg.widgetData.length > 0 && (() => {
                                            const validPoints = msg.widgetData.filter((d: any) =>
                                                (d.lat ?? d.latitude) != null && (d.lng ?? d.longitude) != null
                                            );
                                            const msgOsint = agentOsintData[msg.id] ?? {};
                                            const isLoadingOsint = loadingAgentOsint[msg.id] ?? false;
                                            const firstPoint = validPoints[0];
                                            const satelliteUrl = AGENT_ESRI_KEY
                                                ? `https://ibasemaps-api.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}?token=${AGENT_ESRI_KEY}`
                                                : null;
                                            return (
                                                <Box mt="md">
                                                    <Group justify="space-between" mb="xs">
                                                        <Text fw={500} size="sm" c="dimmed">📍 {validPoints.length} locations</Text>
                                                        {firstPoint && (
                                                            <Button
                                                                size="xs"
                                                                variant="light"
                                                                loading={isLoadingOsint}
                                                                leftSection={<IconSettings size={14} />}
                                                                onClick={() => loadAgentOsintLayers(
                                                                    msg.id,
                                                                    firstPoint.lat ?? firstPoint.latitude,
                                                                    firstPoint.lng ?? firstPoint.longitude
                                                                )}
                                                            >
                                                                OSINT Layer laden
                                                            </Button>
                                                        )}
                                                    </Group>
                                                    <Box style={{ height: 420, borderRadius: 8, overflow: 'hidden', border: '1px solid #374151' }}>
                                                        <MapContainer
                                                            center={[51.1657, 10.4515]}
                                                            zoom={5}
                                                            style={{ height: '100%', width: '100%' }}
                                                        >
                                                            <LayersControl position="topright">
                                                                <LayersControl.BaseLayer checked name="OpenStreetMap">
                                                                    <TileLayer
                                                                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                                                                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                                                                    />
                                                                </LayersControl.BaseLayer>
                                                                {satelliteUrl && (
                                                                    <LayersControl.BaseLayer name="Satellite (ArcGIS)">
                                                                        <TileLayer
                                                                            url={satelliteUrl}
                                                                            attribution='Tiles &copy; Esri &mdash; Maxar, Earthstar Geographics'
                                                                            maxZoom={19}
                                                                        />
                                                                    </LayersControl.BaseLayer>
                                                                )}
                                                                {Object.entries(msgOsint).map(([layer, items]: [string, any[]]) =>
                                                                    items && items.length > 0 ? (
                                                                        <LayersControl.Overlay key={layer} checked name={OSINT_LABELS[layer] ?? layer}>
                                                                            <LayerGroup>
                                                                                {items.map((item: any) =>
                                                                                    item.lat != null && item.lng != null ? (
                                                                                        <Marker
                                                                                            key={item.id}
                                                                                            position={[item.lat, item.lng]}
                                                                                            icon={OSINT_ICONS[layer]}
                                                                                        >
                                                                                            <Popup>
                                                                                                <div style={{ fontFamily: 'system-ui, sans-serif' }}>
                                                                                                    <div style={{ fontWeight: 700 }}>{OSINT_LABELS[layer] ?? layer}</div>
                                                                                                    {item.name && <div>{item.name}</div>}
                                                                                                    {item.operator && <div style={{ fontSize: '0.75rem', color: '#888' }}>{item.operator}</div>}
                                                                                                </div>
                                                                                            </Popup>
                                                                                        </Marker>
                                                                                    ) : null
                                                                                )}
                                                                            </LayerGroup>
                                                                        </LayersControl.Overlay>
                                                                    ) : null
                                                                )}
                                                            </LayersControl>
                                                            <FitMapBounds points={validPoints.map((d: any) => ({ lat: d.lat ?? d.latitude, lng: d.lng ?? d.longitude }))} />
                                                            <MarkerClusterGroup>
                                                                {validPoints.map((item: any, idx: number) => {
                                                                    const lat = item.lat ?? item.latitude;
                                                                    const lng = item.lng ?? item.longitude;
                                                                    const mentions = item.mention_count ?? 1;
                                                                    const radius = Math.min(Math.max(8 + Math.sqrt(mentions) * 2, 10), 36);
                                                                    const hue = Math.max(0, 120 - mentions * 4);
                                                                    const circleIcon = L.divIcon({
                                                                        className: '',
                                                                        html: `<div style="width:${radius*2}px;height:${radius*2}px;border-radius:50%;background:hsl(${hue},80%,50%);border:2px solid white;opacity:0.85;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:bold;color:white;box-shadow:0 1px 4px rgba(0,0,0,0.4)">${mentions > 1 ? mentions : ''}</div>`,
                                                                        iconSize: [radius * 2, radius * 2],
                                                                        iconAnchor: [radius, radius],
                                                                    });
                                                                    const sampleMsgs: Array<{text: string; date?: string}> = item.sample_messages || [];
                                                                    return (
                                                                        <Marker key={idx} position={[lat, lng]} icon={circleIcon}>
                                                                            <Popup minWidth={260} maxWidth={320}>
                                                                                <div style={{ fontFamily: 'system-ui, sans-serif' }}>
                                                                                    <div style={{ fontWeight: 700, fontSize: '0.95rem', marginBottom: 2 }}>
                                                                                        📍 {item.canonical_name || 'Unknown'}
                                                                                    </div>
                                                                                    {item.country && (
                                                                                        <div style={{ fontSize: '0.75rem', color: '#888', marginBottom: 6 }}>
                                                                                            🌍 {item.country}
                                                                                        </div>
                                                                                    )}
                                                                                    <div style={{ display: 'inline-block', background: `hsl(${hue},80%,45%)`, color: 'white', borderRadius: 10, padding: '2px 10px', fontSize: '0.72rem', fontWeight: 700, marginBottom: sampleMsgs.length ? 8 : 0 }}>
                                                                                        {mentions} {mentions === 1 ? 'mention' : 'mentions'}
                                                                                    </div>
                                                                                    {sampleMsgs.length > 0 && (
                                                                                        <div style={{ borderTop: '1px solid #e9ecef', paddingTop: 6 }}>
                                                                                            <div style={{ fontSize: '0.68rem', color: '#aaa', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 5 }}>
                                                                                                Recent messages
                                                                                            </div>
                                                                                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 180, overflowY: 'auto' }}>
                                                                                                {sampleMsgs.map((smsg, mi) => (
                                                                                                    <div key={mi} style={{ background: '#f8f9fa', borderRadius: 6, padding: '5px 8px', borderLeft: '3px solid #4dabf7' }}>
                                                                                                        <div style={{ fontSize: '0.76rem', color: '#333', lineHeight: 1.4 }}>
                                                                                                            {smsg.text && smsg.text.length > 140 ? smsg.text.substring(0, 140) + '…' : (smsg.text || '—')}
                                                                                                        </div>
                                                                                                        {smsg.date && (
                                                                                                            <div style={{ fontSize: '0.65rem', color: '#bbb', marginTop: 3 }}>
                                                                                                                {new Date(smsg.date).toLocaleDateString('de-DE', { day: '2-digit', month: 'short', year: 'numeric' })}
                                                                                                            </div>
                                                                                                        )}
                                                                                                    </div>
                                                                                                ))}
                                                                                            </div>
                                                                                        </div>
                                                                                    )}
                                                                                </div>
                                                                            </Popup>
                                                                        </Marker>
                                                                    );
                                                                })}
                                                            </MarkerClusterGroup>
                                                        </MapContainer>
                                                    </Box>
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
