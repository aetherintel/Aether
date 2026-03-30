import React, { useEffect, useState } from 'react';
import {
  IconActivity,
  IconExclamationCircle,
  IconPlayerPlay,
  IconPhoto,
  IconVolume,
  IconMoodSmile,
} from '@tabler/icons-react';
import {
  Alert,
  Button,
  Container,
  Group,
  Loader,
  Paper,
  Select,
  MultiSelect,
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

interface TelegramScraperProps {
  case_id?: number;
}

type ScraperMode = 'full' | 'live';

const TelegramScraper: React.FC<TelegramScraperProps> = ({ case_id }) => {
  const [activeSessions, setActiveSessions] = useState<TelegramSession[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);

  // Form state
  const [channel, setChannel] = useState<string>('');
  const [mode, setMode] = useState<ScraperMode>('full');
  const [recursive, setRecursive] = useState<boolean>(true);
  const [selectedSession, setSelectedSession] = useState<string>('');

  // Worker options
  const [enableImageAnalysis, setEnableImageAnalysis] = useState<boolean>(true);
  const [enableAudioTranscription, setEnableAudioTranscription] = useState<boolean>(true);
  const [enableEmotionAnalysis, setEnableEmotionAnalysis] = useState<boolean>(false);
  const [enableLabelClassifier, setEnableLabelClassifier] = useState<boolean>(false);
  const [enableGeolocationExtraction, setEnableGeolocationExtraction] = useState<boolean>(false);
  const [ocrLanguages, setOcrLanguages] = useState<string[]>(['latin']);

  useEffect(() => {
    fetchSessions();
  }, [case_id]);

  const fetchSessions = async (): Promise<void> => {
    try {
      const response = await authFetch(`${apiUrl}/telegram-auth/sessions`);

      if (!response.ok) {
        throw new Error('Failed to fetch sessions');
      }

      const data = await response.json();
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
          endpoint = `${apiUrl}/scrape`;
          payload = {
            channel: channel.trim(),
            tg_session: selectedSession,
            recursive,
            neo4j: true,
            case_id: case_id || undefined,
            enable_translation: true,
            enable_image_analysis: enableImageAnalysis,
            enable_audio_transcription: enableAudioTranscription,
            enable_emotion_analysis: enableEmotionAnalysis,
            enable_label_classifier: enableLabelClassifier,
            enable_geolocation_extraction: enableGeolocationExtraction,
            ocr_languages: ocrLanguages,
          };
          break;
        case 'live':
          endpoint = `${apiUrl}/scrape`;
          payload = {
            channel: [channel.trim()],
            tg_session: selectedSession,
            case_id: case_id || undefined,
            enable_translation: true,
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
                  <IconPhoto size={16} />
                  <Text size="sm">Enable Image Analysis</Text>
                </Group>
              }
              description="Extract text from images using OCR"
              checked={enableImageAnalysis}
              onChange={(e) => setEnableImageAnalysis(e.currentTarget.checked)}
            />

            <MultiSelect
              placeholder="OCR Languages"
              data={[
                { value: 'latin', label: 'Latin (En, De, Tr)' },
                { value: 'cyrillic', label: 'Cyrillic (Ru)' },
                { value: 'arabic', label: 'Arabic' },
              ]}
              value={ocrLanguages}
              onChange={setOcrLanguages}
              disabled={!enableImageAnalysis}
              clearable
              searchable
              ml="lg"
              mt="xs"
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

    </Stack>
  );
};

export default TelegramScraper;