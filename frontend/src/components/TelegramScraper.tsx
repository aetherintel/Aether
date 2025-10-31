import React, { useEffect, useState } from 'react';
import {
  IconActivity,
  IconExclamationCircle,
  IconPlayerPlay,
  IconRefresh,
  IconTrash,
  IconPhoto,
  IconVolume,
  IconLanguage,
  IconMoodSmile,
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
  Checkbox,
  Divider,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { authFetch } from '@/utils/authFetch';
import GroupedJobs from './GroupedJobs/GroupedJobs';

const apiUrl = import.meta.env.VITE_API_URL;

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

interface ContainerInfo {
  id: string;
  name: string;
  image: string;
  status: string;
  labels: {
    queue?: string;
    channels?: string;
    mode?: string;
    case_id?: string;
  };
  queue?: string;
  channels?: string;
  mode?: string;
  case_id?: string | number;
  session?: string;
  runtime?: string;
  created?: string;
}

interface TelegramScraperProps {
  case_id?: number;
}

type ScraperMode = 'full' | 'live';

const mapJobStatus = (status: string): string => {
  const statusMap: Record<string, string> = {
    queued: 'pending',
    pending: 'pending',
    started: 'running',
    running: 'running',
    finished: 'exited',
    exited: 'exited',
    failed: 'failed',
  };
  return statusMap[status] || status;
};

const getStatusColor = (status: string): string => {
  switch (status) {
    case 'running':
    case 'started':
      return 'green';
    case 'pending':
    case 'queued':
      return 'yellow';
    case 'exited':
    case 'finished':
      return 'gray';
    case 'failed':
      return 'red';
    default:
      return 'blue';
  }
};

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
  const [selectedSession, setSelectedSession] = useState<string>('');

  // Worker options
  const [enableTranslation, setEnableTranslation] = useState<boolean>(true);
  const [enableImageAnalysis, setEnableImageAnalysis] = useState<boolean>(true);
  const [enableAudioTranscription, setEnableAudioTranscription] = useState<boolean>(true);
  const [enableEmotionAnalysis, setEnableEmotionAnalysis] = useState<boolean>(false);
  const [enableLabelClassifier, setEnableLabelClassifier] = useState<boolean>(false);
  const [enableGeolocationExtraction, setEnableGeolocationExtraction] = useState<boolean>(false);

  useEffect(() => {
    fetchSessions();
    fetchStatus();

    const interval = setInterval(() => {
      fetchStatus();
    }, 10000);

    return () => clearInterval(interval);
  }, [case_id]);

  const fetchSessions = async (): Promise<void> => {
    try {
      const response = await authFetch(`${apiUrl}/telegram-auth/sessions`);

      if (!response.ok) {
        throw new Error('Failed to fetch sessions');
      }

      const data = await response.json();
      setSessions(data.sessions || []);

      const active = data.sessions?.filter((s: TelegramSession) => s.active) || [];
      setActiveSessions(active);

      if (active.length > 0 && !selectedSession) {
        setSelectedSession(active[0].name);
      }
    } catch (error) {
      console.error('Error fetching sessions:', error);
      notifications.show({
        title: 'Error',
        message: 'Failed to fetch Telegram sessions',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  const fetchStatus = async (): Promise<void> => {
    try {
      const response = await authFetch(`${apiUrl}/auth/telegram/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ case_id: case_id || null }),
      });

      if (!response.ok) {
        throw new Error('Failed to fetch status');
      }

      const data = await response.json();
      const mappedContainers = data.containers.map((job: any) => ({
        ...job,
        status: mapJobStatus(job.status),
      }));

      setStatus(mappedContainers);
    } catch (error) {
      console.error('Error fetching status:', error);
    }
  };

  const handleJobControl = async (
    jobId: string,
    action: 'remove' | 'requeue'
  ): Promise<void> => {
    setControlLoading((prev) => ({ ...prev, [jobId]: true }));

    try {
      let endpoint = '';
      let method = 'POST';

      if (action === 'remove') {
        endpoint = `${apiUrl}/auth/telegram/job/${jobId}`;
        method = 'DELETE';
      } else if (action === 'requeue') {
        endpoint = `${apiUrl}/auth/telegram/job/${jobId}/requeue`;
        method = 'POST';
      }

      const response = await authFetch(endpoint, { method });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Operation failed');
      }

      notifications.show({
        title: 'Success',
        message: `Job ${action === 'remove' ? 'removed' : 'requeued'} successfully`,
        color: 'green',
      });

      await fetchStatus();
    } catch (error: any) {
      notifications.show({
        title: 'Error',
        message: error.message || `Failed to ${action} job`,
        color: 'red',
      });
    } finally {
      setControlLoading((prev) => ({ ...prev, [jobId]: false }));
    }
  };

  const addChannelToCase = async (caseId: number, channelUsername: string) => {
    try {
      const response = await authFetch(`${apiUrl}/casefiles/${caseId}/add-channels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify([channelUsername]),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to add channel to case');
      }

      notifications.show({
        title: 'Channel added',
        message: `Added ${channelUsername} to case ${caseId}`,
        color: 'green',
      });
    } catch (error: any) {
      console.error('Error adding channel to case:', error);
      notifications.show({
        title: 'Warning',
        message: `Scraper started, but failed to add channel to case: ${error.message}`,
        color: 'yellow',
      });
    }
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
      let payload: any = {};

      switch (mode) {
        case 'full':
          endpoint = `${apiUrl}/auth/telegram/full`;
          payload = {
            channel: channel.trim(),
            tg_session: selectedSession,
            recursive,
            neo4j: true,
            case_id: case_id || undefined,
            enable_translation: enableTranslation,
            enable_image_analysis: enableImageAnalysis,
            enable_audio_transcription: enableAudioTranscription,
            enable_emotion_analysis: enableEmotionAnalysis,
            enable_label_classifier: enableLabelClassifier,
            enable_geolocation_extraction: enableGeolocationExtraction,
          };
          break;
        case 'live':
          endpoint = `${apiUrl}/auth/telegram/live`;
          payload = {
            channels: [channel.trim()],
            tg_session: selectedSession,
            case_id: case_id || undefined,
            enable_translation: enableTranslation,
            enable_image_analysis: enableImageAnalysis,
            enable_audio_transcription: enableAudioTranscription,
            enable_emotion_analysis: enableEmotionAnalysis,
            enable_label_classifier: enableLabelClassifier,
          };
          break;
      }

      const response = await authFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Request failed');
      }

      notifications.show({
        title: 'Success',
        message: case_id
          ? `Scraper started for case ${case_id}`
          : 'Scraper started successfully',
        color: 'green',
      });

      if (case_id) {
        await addChannelToCase(case_id, channel.trim());
      }

      setChannel('');
      setTimeout(fetchStatus, 1000);
    } catch (error: any) {
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to start scraper',
        color: 'red',
      });
    } finally {
      setSubmitting(false);
    }
  };

  const getSessionOptions = () => {
    return activeSessions.map((session) => {
      const user = session.user || session.user_info;
      const name = user ? `${user.first_name} ${user.last_name}`.trim() : 'Unknown';
      return {
        value: session.name,
        label: `${session.name} (${name})`,
      };
    });
  };

  const getUserDisplayName = (session: TelegramSession): string => {
    const user = session.user || session.user_info;
    if (!user) return 'Unknown User';
    return `${user.first_name} ${user.last_name}`.trim();
  };

  const canRemoveJob = (status: string): boolean => {
    return ['exited', 'failed', 'pending'].includes(status);
  };

  const canRequeueJob = (status: string): boolean => {
    return status === 'failed';
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
            onChange={(value) => setMode(value as ScraperMode)}
            data={[
              { value: 'full', label: 'Full Scrape' },
              { value: 'live', label: 'Live Scrape' },
            ]}
            required
          />

          <Select
            label="Telegram Session"
            value={selectedSession}
            onChange={(value) => setSelectedSession(value || '')}
            data={getSessionOptions()}
            disabled={activeSessions.length === 0}
            required
          />

          {mode === 'full' && (
            <Switch
              label="Autofollow scraping"
              description="Include related channels and references"
              checked={recursive}
              onChange={(e) => setRecursive(e.currentTarget.checked)}
            />
          )}

          <Divider label="Worker Options" labelPosition="center" />

          <Stack gap="xs">
            <Checkbox
              label={
                <Group gap="xs">
                  <IconLanguage size={16} />
                  <Text size="sm">Enable Translation</Text>
                </Group>
              }
              description="Automatically translate messages to German"
              checked={enableTranslation}
              onChange={(e) => setEnableTranslation(e.currentTarget.checked)}
            />

            <Checkbox
              label={
                <Group gap="xs">
                  <IconPhoto size={16} />
                  <Text size="sm">Enable Image Analysis</Text>
                </Group>
              }
              description="Extract text from images using OCR"
              checked={enableImageAnalysis}
              onChange={(e) => setEnableImageAnalysis(e.currentTarget.checked)}
            />

            <Checkbox
              label={
                <Group gap="xs">
                  <IconVolume size={16} />
                  <Text size="sm">Enable Audio Transcription</Text>
                </Group>
              }
              description="Transcribe audio and video files"
              checked={enableAudioTranscription}
              onChange={(e) => setEnableAudioTranscription(e.currentTarget.checked)}
            />

            <Checkbox
              label={
                <Group gap="xs">
                  <IconMoodSmile size={16} />
                  <Text size="sm">Enable Emotion Analysis</Text>
                </Group>
              }
              description="Analyze sentiment and emotions in messages"
              checked={enableEmotionAnalysis}
              onChange={(e) => setEnableEmotionAnalysis(e.currentTarget.checked)}
            />
            <Checkbox
              label={
                <Group gap="xs">
                  <IconActivity size={16} />
                  <Text size="sm">Enable Label Classifier</Text>
                </Group>
              }
              description="Classify messages using label classifier"
              checked={enableLabelClassifier}
              onChange={(e) => setEnableLabelClassifier(e.currentTarget.checked)}
            />
            <Checkbox
              label={
                <Group gap="xs">
                  <IconExclamationCircle size={16} />
                  <Text size="sm">Enable Geolocation Extraction</Text>
                </Group>
              }
              description="Extract geolocation data from messages"
              checked={enableGeolocationExtraction}
              onChange={(e) => setEnableGeolocationExtraction(e.currentTarget.checked)}
            />
          </Stack>

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
        <GroupedJobs
          status={status}
          controlLoading={controlLoading}
          onJobControl={handleJobControl}
          canRemoveJob={canRemoveJob}
          canRequeueJob={canRequeueJob}
        />
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
  );
};

export default TelegramScraper;