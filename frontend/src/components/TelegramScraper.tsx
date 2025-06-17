import React, { useState, useEffect } from 'react';
import {
  Container,
  Paper,
  Title,
  TextInput,
  Select,
  Switch,
  Button,
  Group,
  Stack,
  Alert,
  Loader,
  Badge,
  Text,
  Card
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconPlayerPlay,
  IconExclamationCircle,
  IconActivity,
} from '@tabler/icons-react';

const API_BASE = 'http://localhost:8000';

// Types
interface UserInfo {
  id: number;
  username: string | null;
  first_name: string;
  last_name: string;
}

interface TelegramSession {
  name: string;
  file: string;
  active: boolean;
  user_info?: UserInfo;
  user?: UserInfo;
}

interface SessionsResponse {
  sessions: TelegramSession[];
}

interface ContainerInfo {
  id: string;
  name: string;
  image: string | null;
  status: string;
  labels: Record<string, string>;
  created: string;
}

interface SelectOption {
  value: string;
  label: string;
}

interface ScrapePayload {
  channels?: string[];
  channel?: string;
  tg_session: string;
  recursive?: boolean;
  neo4j?: boolean;
}

type ScraperMode = 'scrape' | 'full' | 'live' | 'similar';

const TelegramScraper: React.FC = () => {
  const [sessions, setSessions] = useState<TelegramSession[]>([]);
  const [activeSessions, setActiveSessions] = useState<TelegramSession[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [status, setStatus] = useState<ContainerInfo[]>([]);
  
  // Form state
  const [channel, setChannel] = useState<string>('');
  const [mode, setMode] = useState<ScraperMode>('scrape');
  const [recursive, setRecursive] = useState<boolean>(true);
  const [neo4j, setNeo4j] = useState<boolean>(true);
  const [selectedSession, setSelectedSession] = useState<string>('');

  const modes: SelectOption[] = [
    { value: 'scrape', label: 'Basic Scrape' },
    { value: 'full', label: 'Full Scrape' },
    { value: 'live', label: 'Live Scrape' },
    { value: 'similar', label: 'Similar Channels' }
  ];

  // Fetch sessions on component mount
  useEffect(() => {
    fetchSessions();
    fetchStatus();
  }, []);

  const fetchSessions = async (): Promise<void> => {
    try {
      const response = await fetch(`${API_BASE}/telegram-auth/sessions`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
        }
      });
      
      if (!response.ok) {throw new Error('Failed to fetch sessions');}
      
      const data: SessionsResponse = await response.json();
      setSessions(data.sessions || []);
      
      // Filter active sessions
      const active = data.sessions?.filter(session => session.active) || [];
      setActiveSessions(active);
      
      // Auto-select first active session
      if (active.length > 0) {
        setSelectedSession(active[0].name);
      }
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to fetch Telegram sessions',
        color: 'red'
      });
      console.error('Error fetching sessions:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStatus = async (): Promise<void> => {
    try {
      const response = await fetch(`${API_BASE}/auth/telegram/status`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
        }
      });
      
      if (!response.ok) {throw new Error('Failed to fetch status');}
      
      const data: ContainerInfo[] = await response.json();
      setStatus(data || []);
    } catch (error) {
      console.error('Error fetching status:', error);
    }
  };

  const handleSubmit = async (): Promise<void> => {
    if (!channel.trim()) {
      notifications.show({
        title: 'Validation Error',
        message: 'Please enter a channel name',
        color: 'red'
      });
      return;
    }

    if (!selectedSession) {
      notifications.show({
        title: 'Validation Error',
        message: 'No active session available',
        color: 'red'
      });
      return;
    }

    setSubmitting(true);

    try {
      let endpoint = '';
      let payload: ScrapePayload = { tg_session: selectedSession };

      switch (mode) {
        case 'scrape':
          endpoint = `${API_BASE}/auth/telegram/scrape`;
          payload = {
            channels: [channel.trim()],
            tg_session: selectedSession
          };
          break;
        case 'full':
          endpoint = `${API_BASE}/auth/telegram/full`;
          payload = {
            channel: channel.trim(),
            tg_session: selectedSession,
            recursive,
            neo4j
          };
          break;
        case 'live':
          endpoint = `${API_BASE}/auth/telegram/live`;
          payload = {
            channels: [channel.trim()],
            tg_session: selectedSession
          };
          break;
        case 'similar':
          endpoint = `${API_BASE}/auth/telegram/similar`;
          payload = {
            channel: channel.trim(),
            tg_session: selectedSession
          };
          break;
      }

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Request failed');
      }

      const result = await response.json();
      
      notifications.show({
        title: 'Success',
        message: result.message || 'Scraper started successfully',
        color: 'green'
      });

      // Refresh status after starting scraper
      setTimeout(fetchStatus, 1000);
      
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to start scraper';
      notifications.show({
        title: 'Error',
        message: errorMessage,
        color: 'red'
      });
      console.error('Error starting scraper:', error);
    } finally {
      setSubmitting(false);
    }
  };

  const getSessionOptions = (): SelectOption[] => {
    return activeSessions.map(session => ({
      value: session.name,
      label: `${session.name} (${session.user?.first_name || session.user_info?.first_name || 'Unknown'} ${session.user?.last_name || session.user_info?.last_name || ''})`
    }));
  };

  const getUserDisplayName = (session: TelegramSession): string => {
    const user = session.user || session.user_info;
    if (!user) {return 'Unknown User';}
    return `${user.first_name} ${user.last_name}`.trim();
  };

  if (loading) {
    return (
      <Container size="md" py="xl">
        <Group justify="center">
          <Loader size="lg" />
          <Text>Loading sessions...</Text>
        </Group>
      </Container>
    );
  }

  return (
    <>
      <Stack gap="lg">
        {activeSessions.length === 0 && (
          <Alert icon={<IconExclamationCircle size="1rem" />} color="yellow">
            No active Telegram sessions found. Please authenticate first.
          </Alert>
        )}

        <Paper p="lg" withBorder>
          <Stack gap="md">
            <Title order={3}>Start Scraper</Title>
            
            <TextInput
              label="Channel"
              placeholder="Enter channel name or username"
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
              required
            />

            <Select
              label="Scraper Mode"
              value={mode}
              onChange={(value: string | null) => setMode(value as ScraperMode)}
              data={modes}
              required
            />

            <Select
              label="Telegram Session"
              value={selectedSession}
              onChange={(value: string | null) => setSelectedSession(value || '')}
              data={getSessionOptions()}
              disabled={activeSessions.length === 0}
              required
            />

            {mode === 'full' && (
              <Stack gap="xs">
                <Switch
                  label="Recursive scraping"
                  description="Include related channels and references"
                  checked={recursive}
                  onChange={(e) => setRecursive(e.currentTarget.checked)}
                />
                <Switch
                  label="Store in Neo4j"
                  description="Save results to graph database"
                  checked={neo4j}
                  onChange={(e) => setNeo4j(e.currentTarget.checked)}
                />
              </Stack>
            )}

            <Group justify="flex-end">
              <Button
                leftSection={<IconPlayerPlay size="1rem" />}
                onClick={handleSubmit}
                loading={submitting}
                disabled={activeSessions.length === 0}
              >
                Start Scraper
              </Button>
            </Group>
          </Stack>
        </Paper>

        {status.length > 0 && (
          <Paper p="lg" withBorder>
            <Stack gap="md">
              <Group align="center" gap="xs">
                <IconActivity size="1.2rem" />
                <Title order={3}>Scrape Containers</Title>
              </Group>
              
              <Stack gap="sm">
                {status.map((container, index) => (
                  <Card key={container.id || index} padding="sm" withBorder>
                    <Group justify="space-between" align="flex-start">
                      <Stack gap="xs" style={{ flex: 1 }}>
                        <Group align="center" gap="xs">
                          <Text fw={500}>{container.name} [{container.labels.CHANNELS}]</Text>
                          <Badge 
                            color={container.status === 'running' ? 'green' : 'gray'}
                            variant="light"
                          >
                            {container.status}
                          </Badge>
                        </Group>
                        <Text size="sm" c="dimmed">
                          {container.image}
                        </Text>
                        <Text size="xs" c="dimmed">
                          ID: {container.id?.substring(0, 12)}
                        </Text>
                      </Stack>
                    </Group>
                  </Card>
                ))}
              </Stack>
            </Stack>
          </Paper>
        )}

        {sessions.length > 0 && (
          <Paper p="lg" withBorder>
            <Stack gap="md">
              <Title order={3}>Available Sessions</Title>
              <Stack gap="sm">
                {sessions.map((session, index) => (
                  <Group key={index} justify="space-between">
                    <Stack gap="xs">
                      <Text fw={500}>{session.name}</Text>
                      <Text size="sm" c="dimmed">
                        {getUserDisplayName(session)}
                      </Text>
                    </Stack>
                    <Badge color={session.active ? 'green' : 'gray'} variant="light">
                      {session.active ? 'Active' : 'Inactive'}
                    </Badge>
                  </Group>
                ))}
              </Stack>
            </Stack>
          </Paper>
        )}
      </Stack>
    </>
  );
};

export default TelegramScraper;