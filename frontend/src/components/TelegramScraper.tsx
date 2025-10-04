import React, { useEffect, useState } from 'react';
import {
  IconActivity,
  IconExclamationCircle,
  IconPlayerPause,
  IconPlayerPlay,
  IconRefresh,
  IconTrash,
} from '@tabler/icons-react';
import {
  Alert,
  Badge,
  Button,
  Card,
  Container,
  Group,
  Loader,
  Paper,
  Select,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { authFetch } from '@/utils/authFetch';

const apiUrl = import.meta.env.VITE_API_URL;

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
  case_id?: string;
  owner_id?: string;
  channels?: string;
  mode?: string;
  session?: string;
  runtime?: string;
}

// Update your component props interface if needed
interface TelegramScraperProps {
  case_id?: number;
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
  case_id?: number;
}

type ScraperMode = 'full' | 'live';
interface TelegramScraperProps {
  case_id?: number;
}

const TelegramScraper: React.FC<TelegramScraperProps> = ({ case_id }) => {
  const [sessions, setSessions] = useState<TelegramSession[]>([]);
  const [activeSessions, setActiveSessions] = useState<TelegramSession[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [status, setStatus] = useState<ContainerInfo[]>([]);
  const [controlLoading, setControlLoading] = useState<Record<string, boolean>>({});

  // Form state
  const [channel, setChannel] = useState<string>('');
  const [mode, setMode] = useState<ScraperMode>('full');
  const [recursive, setRecursive] = useState<boolean>(true);
  const [neo4j] = useState<boolean>(true);
  const [selectedSession, setSelectedSession] = useState<string>('');

  const modes: SelectOption[] = [
    { value: 'full', label: 'Full Scrape' },
    { value: 'live', label: 'Live Scrape' },
  ];

  // Fetch sessions on component mount
  useEffect(() => {
    fetchSessions();
    fetchStatus();
  }, []);

  const fetchSessions = async (): Promise<void> => {
    try {
      const base = apiUrl ?? 'http://localhost:8000/api';
      const response = await authFetch(`${base}/telegram-auth/sessions`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch sessions');
      }

      const data: SessionsResponse = await response.json();
      setSessions(data.sessions || []);

      // Filter active sessions
      const active = data.sessions?.filter((session) => session.active) || [];
      setActiveSessions(active);

      // Auto-select first active session
      if (active.length > 0) {
        setSelectedSession(active[0].name);
      }
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to fetch Telegram sessions',
        color: 'red',
      });
      console.error('Error fetching sessions:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleContainerControl = async (
    containerId: string,
    action: 'start' | 'remove'
  ): Promise<void> => {
    setControlLoading((prev: any) => ({ ...prev, [containerId]: true }));

    try {
      const base = apiUrl ?? 'http://localhost:8000/api';
      const endpoint = `${base}/auth/telegram/container/${containerId}/${action}`;
      const method = action === 'remove' ? 'DELETE' : 'POST';

      const response = await authFetch(endpoint, {
        method,
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
        },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Failed to ${action} container`);
      }

      const result = await response.json();

      notifications.show({
        title: 'Success',
        message: result.message,
        color: 'green',
      });

      // Refresh status after action
      setTimeout(fetchStatus, 1000);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : `Failed to ${action} container`;
      notifications.show({
        title: 'Error',
        message: errorMessage,
        color: 'red',
      });
      console.error(`Error ${action}ing container:`, error);
    } finally {
      setControlLoading((prev: any) => ({ ...prev, [containerId]: false }));
    }
  };

  // Helper function to get appropriate button props based on container status
  const getContainerActions = (container: ContainerInfo) => {
    const isRunning = container.status === 'running';
    const isExited = container.status === 'exited';
    const loading = controlLoading[container.id];

    return {
      canStart: isExited && !loading,
      canStop: isRunning && !loading,
      canRestart: (isRunning || isExited) && !loading,
      canRemove: !loading,
      loading,
    };
  };

  // Status mapping: RQ -> Container-ähnlich
const mapJobStatus = (status: string): string => {
  switch (status) {
    case 'queued': return 'created';  // Wartend
    case 'started': return 'running'; // Läuft
    case 'finished': return 'exited'; // Fertig
    case 'failed': return 'exited';   // Fehlgeschlagen
    default: return status;
  }
};

// TelegramScraper.tsx

useEffect(() => {
  fetchSessions();
  fetchStatus();
  
  // Auto-refresh alle 10 Sekunden wenn Jobs laufen
  const interval = setInterval(() => {
    fetchStatus();
  }, 10000); // 10 Sekunden
  
  return () => clearInterval(interval);
}, [case_id]);

const fetchStatus = async (): Promise<void> => {
  try {
    const response = await authFetch(`${apiUrl}/auth/telegram/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ case_id: case_id || null }),
    });
    
    if (!response.ok) throw new Error('Failed to fetch status');
    
    const data = await response.json();
    
    const mappedContainers = data.containers.map((job: any) => ({
      ...job,
      status: mapJobStatus(job.status),
      // Zeige zusätzlich wie lange der Job läuft
      runtime: job.started_at ? 
        formatRuntime(new Date(job.started_at)) : null
    }));
    
    setStatus(mappedContainers);
  } catch (error) {
    console.error('Error fetching status:', error);
  }
};

// Helper: Runtime anzeigen
const formatRuntime = (startTime: Date): string => {
  const now = new Date();
  const diff = now.getTime() - startTime.getTime();
  const hours = Math.floor(diff / 3600000);
  const minutes = Math.floor((diff % 3600000) / 60000);
  return `${hours}h ${minutes}m`;
};

  const handleSubmit = async (): Promise<void> => {
    if (!channel.trim()) {
      notifications.show({
        title: 'Validation Error',
        message: 'Please enter a channel name',
        color: 'red',
      });
      return;
    }

    if (!selectedSession) {
      notifications.show({
        title: 'Validation Error',
        message: 'No active session available',
        color: 'red',
      });
      return;
    }

    setSubmitting(true);

    try {
      let endpoint = '';
      let payload: ScrapePayload = { tg_session: selectedSession };
      const base = apiUrl ?? 'http://localhost:8000/api';

      switch (mode) {
        case 'full':
          endpoint = `${base}/auth/telegram/full`;
          payload = {
            channel: channel.trim(),
            tg_session: selectedSession,
            recursive,
            neo4j,
            case_id: case_id ? case_id : undefined,
          };
          break;
        case 'live':
          endpoint = `${base}/auth/telegram/live`;
          payload = {
            channels: [channel.trim()],
            tg_session: selectedSession,
            case_id: case_id ? case_id : undefined,
          };
          break;
      }
      const addChannelToCase = async (caseId: number, channelUsername: string) => {
        try {
          const base = apiUrl ?? 'http://localhost:8000/api';
          const response = await authFetch(`${base}/casefiles/${caseId}/add-channels`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
            },
            body: JSON.stringify([channelUsername]), // Send as array of channel usernames
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to add channel to case');
          }

          const result = await response.json();
          console.log(`Added channel ${channelUsername} to case ${caseId}:`, result);

          notifications.show({
            title: 'Channel added to case',
            message: `Successfully added ${channelUsername} to case ${caseId}`,
            color: 'green',
          });

          return result;
        } catch (error) {
          console.error('Error adding channel to case:', error);
          notifications.show({
            title: 'Error',
            message: `Failed to add channel to case: ${(error as Error).message}`,
            color: 'red',
          });
          throw error;
        }
      };
      const response = await authFetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Request failed');
      }

      await response.json();

      if (case_id) {
        try {
          await addChannelToCase(case_id, channel.trim());
        } catch (addChannelError) {
          // Log the error but don't fail the entire operation
          console.warn(
            'Failed to add channel to case, but scraping started successfully:',
            addChannelError
          );
        }
      }
      notifications.show({
        title: 'Success',
        message: case_id
          ? `Scraper started for case ${case_id}. Click "Check for New Channels" after scraping completes.`
          : 'Scraper started successfully',
        color: 'green',
      });

      // Refresh status after starting scraper
      setTimeout(fetchStatus, 1000);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to start scraper';
      notifications.show({
        title: 'Error',
        message: errorMessage,
        color: 'red',
      });
      console.error('Error starting scraper:', error);
    } finally {
      setSubmitting(false);
    }
  };

  const getSessionOptions = (): SelectOption[] => {
    return activeSessions.map((session) => ({
      value: session.name,
      label: `${session.name} (${session.user?.first_name || session.user_info?.first_name || 'Unknown'} ${session.user?.last_name || session.user_info?.last_name || ''})`,
    }));
  };

  const getUserDisplayName = (session: TelegramSession): string => {
    const user = session.user || session.user_info;
    if (!user) {
      return 'Unknown User';
    }
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
                  label="Autofollow scraping"
                  description="Include related channels and references"
                  checked={recursive}
                  onChange={(e) => setRecursive(e.currentTarget.checked)}
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
                {status.map((container: ContainerInfo, index: number) => {
                  interface ContainerActions {
                    canStart: boolean;
                    canStop: boolean;
                    canRemove: boolean;
                    loading: boolean;
                  }
                  const actions: ContainerActions = getContainerActions(container);

                  return (
                    <Card key={container.id || index} padding="sm" withBorder>
                      <Group justify="space-between" align="flex-start">
                        <Stack gap="xs" style={{ flex: 1 }}>
                          <Group align="center" gap="xs">
                            <Text fw={500}>
                              [{container.labels?.CHANNELS || container.channels}]
                            </Text>
                            <Badge color={container.status === 'running'
                              ? 'green'
                              : container.status === 'exited'
                                ? 'gray'
                                : 'yellow'} variant="light">
                              {container.status}
                            </Badge>
                            {container.runtime && (
                              <Text size="xs" c="dimmed">
                                Running: {container.runtime}
                              </Text>
                            )}
                          </Group>
                          <Text size="sm" c="dimmed">
                            {container.image}
                          </Text>
                          <Text size="xs" c="dimmed">
                            ID: {container.id?.substring(0, 12)}
                          </Text>
                          {container.case_id && (
                            <Text size="xs" c="blue">
                              Case: {container.case_id}
                            </Text>
                          )}
                        </Stack>

                        <Stack gap="xs" align="flex-end">

                          <Button
                            size="xs"
                            variant="light"
                            color="red"
                            leftSection={<IconTrash size="0.75rem" />}
                            onClick={() => handleContainerControl(container.id, 'remove')}
                            loading={actions.loading}
                          >
                            Remove
                          </Button>
                        </Stack>
                      </Group>
                    </Card>
                  );
                })}
              </Stack>
            </Stack>
          </Paper>
        )}

        {sessions.length > 0 && (
          <Paper p="lg" withBorder>
            <Stack gap="md">
              <Title order={3}>Available Sessions</Title>
              <Stack gap="sm">
                {sessions.map((session: TelegramSession, index: any) => (
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
