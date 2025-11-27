import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  Group,
  Select,
  Slider,
  Stack,
  Stepper,
  Text,
  Textarea,
  TextInput,
  Checkbox,
  Divider,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { 
  IconPhoto, 
  IconVolume, 
  IconMoodSmile, 
  IconActivity, 
  IconExclamationCircle 
} from '@tabler/icons-react';
import { authFetch } from '@/utils/authFetch';
import { TgChannelMultiSelect } from '../TgChannelMultiSelect';

const apiUrl = import.meta.env.VITE_API_URL;

interface CaseFileFormValues {
  title: string;
  description: string;
  category: string;
  postCount: number;
  tgchannels: string[];
  topics: string[];
  terms: string[];
  duration: number;
  tg_session: string;
  // AI Worker Flags
  enable_translation: boolean;
  enable_image_analysis: boolean;
  enable_audio_transcription: boolean;
  enable_emotion_analysis: boolean;
  enable_label_classifier: boolean;
  enable_geolocation_extraction: boolean;
}

interface SessionInfo {
  name: string;
  active: boolean;
  user?: {
    first_name?: string;
    last_name?: string;
  };
  user_info?: {
    first_name?: string;
    last_name?: string;
  };
}

interface SessionsResponse {
  sessions: SessionInfo[];
}

interface SelectOption {
  value: string;
  label: string;
}

const marks = [
  { value: 0, label: '3 days' },
  { value: 20, label: '1 week' },
  { value: 40, label: '1 month' },
  { value: 60, label: '3 months' },
  { value: 80, label: '6 months' },
  { value: 100, label: '1 year' },
];

export function CreateCaseFileForm() {
  const [active, setActive] = useState(0);
  const nextStep = () => setActive((current) => (current < 4 ? current + 1 : current));
  const prevStep = () => setActive((current) => (current > 0 ? current - 1 : current));

  const navigate = useNavigate();

  // Session management
  const [, setSessions] = useState<SessionInfo[]>([]);
  const [activeSessions, setActiveSessions] = useState<SessionInfo[]>([]);
  const [sessionLoading, setSessionLoading] = useState(true);

  const form = useForm<CaseFileFormValues>({
    initialValues: {
      title: '',
      description: '',
      category: '',
      postCount: 0,
      tgchannels: [],
      topics: [],
      terms: [],
      duration: 20,
      tg_session: '',
      enable_translation: true,
      enable_image_analysis: true,
      enable_audio_transcription: true,
      enable_emotion_analysis: false,
      enable_label_classifier: false,
      enable_geolocation_extraction: false,
    },
  });

  const [loading, setLoading] = useState(false);

  // Fetch sessions on component mount
  useEffect(() => {
    fetchSessions();
  }, []);

  const fetchSessions = async (): Promise<void> => {
    try {
      const response = await authFetch(
        `${apiUrl ? apiUrl : 'http://localhost:8000/api'}/telegram-auth/sessions`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
          },
        }
      );

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
        form.setFieldValue('tg_session', active[0].name);
      }
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to fetch Telegram sessions',
        color: 'red',
      });
      console.error('Error fetching sessions:', error);
    } finally {
      setSessionLoading(false);
    }
  };

  const getSessionOptions = (): SelectOption[] => {
    return activeSessions.map((session) => ({
      value: session.name,
      label: `${session.name} (${session.user?.first_name || session.user_info?.first_name || 'Unknown'} ${session.user?.last_name || session.user_info?.last_name || ''})`,
    }));
  };

  const handleSubmit = async (values: CaseFileFormValues) => {
    setLoading(true);
    try {
      // Check if channels are selected and session is available
      const willStartScraper = values.tgchannels.length > 0;
      const hasActiveSession = activeSessions.length > 0 && values.tg_session;

      const res = await authFetch(`${apiUrl ? apiUrl : 'http://localhost:8000/api'}/casefiles/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...values,
          scraper_mode: 'full', // Always use full scraper
        }),
      });

      if (!res.ok) {
        throw new Error('Failed to create case file');
      }

      const data = await res.json();

      // Show appropriate notifications based on scraper status
      if (willStartScraper && hasActiveSession) {
        notifications.show({
          title: 'Case Created Successfully!',
          message: `Case "${data.title}" created with ID: ${data.id}. Full scraper started automatically for ${values.tgchannels.length} channel(s).`,
          color: 'green',
        });
      } else if (willStartScraper && !hasActiveSession) {
        notifications.show({
          title: 'Case Created - Scraper Needs Session',
          message: `Case "${data.title}" created with ID: ${data.id}. Please create an active Telegram session first to start full scraping.`,
          color: 'yellow',
        });
      } else {
        notifications.show({
          title: 'Case Created',
          message: `Case "${data.title}" created with ID: ${data.id}. Add channels later to start scraping.`,
          color: 'blue',
        });
      }

      form.reset();
      navigate('/cases');
    } catch (err: any) {
      notifications.show({
        title: 'Error creating Case',
        message: err.message || 'Unknown error',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  const canStartScraper =
    form.values.tgchannels.length > 0 && activeSessions.length > 0 && form.values.tg_session;

  return (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <form
      onSubmit={form.onSubmit(handleSubmit)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' && (e.target as any).tagName !== 'TEXTAREA') {
          e.preventDefault();
        }
      }}
    >
      <Stepper active={active} onStepClick={setActive} mt="xl">
        <Stepper.Step label="Case" description="Basics">
          <Stack>
            <TextInput label="Name of the case" {...form.getInputProps('title')} required />
            <TextInput label="Category of the case" {...form.getInputProps('category')} required />
            <Textarea
              placeholder="Description of the case"
              label="Description of the case"
              autosize
              minRows={3}
              {...form.getInputProps('description')}
            />
          </Stack>
        </Stepper.Step>

        <Stepper.Step label="Telegram Channels" description="Which telegram channels?">
          <Stack>
            <Text mt="md">Telegram channels to start searching from:</Text>
            <TgChannelMultiSelect
              value={form.values.tgchannels}
              onChange={(val) => form.setFieldValue('tgchannels', val)}
            />

            {form.values.tgchannels.length > 0 && (
              <>
                <Text size="sm" mt="md">
                  Telegram Session:
                </Text>
                <Select
                  placeholder={sessionLoading ? 'Loading sessions...' : 'Select a Telegram session'}
                  data={getSessionOptions()}
                  value={form.values.tg_session}
                  onChange={(val) => form.setFieldValue('tg_session', val || '')}
                  disabled={sessionLoading || activeSessions.length === 0}
                  error={
                    form.values.tgchannels.length > 0 && activeSessions.length === 0
                      ? 'No active sessions available. Create one first!'
                      : undefined
                  }
                />

                <Divider label="AI Worker Configuration" labelPosition="center" mt="md" />
                
                <Stack gap="xs">
                  <Checkbox
                    label={
                      <Group gap="xs">
                        <IconPhoto size={16} />
                        <Text size="sm">Enable Image Analysis</Text>
                      </Group>
                    }
                    description="Extract text from images using OCR"
                    {...form.getInputProps('enable_image_analysis', { type: 'checkbox' })}
                  />

                  <Checkbox
                    label={
                      <Group gap="xs">
                        <IconVolume size={16} />
                        <Text size="sm">Enable Audio Transcription</Text>
                      </Group>
                    }
                    description="Transcribe audio and video files"
                    {...form.getInputProps('enable_audio_transcription', { type: 'checkbox' })}
                  />

                  <Checkbox
                    label={
                      <Group gap="xs">
                        <IconMoodSmile size={16} />
                        <Text size="sm">Enable Emotion Analysis</Text>
                      </Group>
                    }
                    description="Analyze sentiment and emotions in messages"
                    {...form.getInputProps('enable_emotion_analysis', { type: 'checkbox' })}
                  />
                  
                  <Checkbox
                    label={
                      <Group gap="xs">
                        <IconActivity size={16} />
                        <Text size="sm">Enable Label Classifier</Text>
                      </Group>
                    }
                    description="Classify messages using label classifier"
                    {...form.getInputProps('enable_label_classifier', { type: 'checkbox' })}
                  />
                  
                  <Checkbox
                    label={
                      <Group gap="xs">
                        <IconExclamationCircle size={16} />
                        <Text size="sm">Enable Geolocation Extraction</Text>
                      </Group>
                    }
                    description="Extract geolocation data from messages"
                    {...form.getInputProps('enable_geolocation_extraction', { type: 'checkbox' })}
                  />
                </Stack>

                {!canStartScraper && form.values.tgchannels.length > 0 && (
                  <Text size="sm" c="orange" mt="sm">
                    ⚠️ Full scraper cannot start automatically - no active Telegram session
                    available
                  </Text>
                )}

                {canStartScraper && (
                  <Text size="sm" c="green" mt="sm">
                    ✅ Full scraper will start automatically when case is created
                  </Text>
                )}
              </>
            )}
          </Stack>
        </Stepper.Step>

        <Stepper.Step label="Settings" description="Case settings">
          <Stack>
            <Text mt="md">How long should this case stay active?</Text>
            <Slider
              {...form.getInputProps('duration')}
              defaultValue={20}
              label={(val: number) => marks.find((mark) => mark.value === val)!.label}
              step={20}
              marks={marks}
              styles={{ markLabel: { display: 'none' } }}
            />
          </Stack>
        </Stepper.Step>

        <Stepper.Completed>Completed, click back button to get to previous step</Stepper.Completed>
      </Stepper>

      <Group justify="end" mt="xl">
        {active > 0 && (
          <Button variant="default" onClick={prevStep}>
            Back
          </Button>
        )}

        {active <= 1 && (
          <Button
            onClick={() => {
              const isValid = form.validate().hasErrors === false;
              if (isValid) {
                nextStep();
              }
            }}
          >
            Next
          </Button>
        )}

        {active === 2 && (
          <Button type="submit" loading={loading}>
            Create Case
          </Button>
        )}
      </Group>
    </form>
  );
}
