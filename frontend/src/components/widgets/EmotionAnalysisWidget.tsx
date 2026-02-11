// src/components/widgets/EmotionAnalysisWidget.tsx
import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  Text,
  Group,
  Stack,
  Skeleton,
  Alert,
  ActionIcon,
  Tooltip,
  RingProgress,
  Badge,
} from '@mantine/core';
import {
  IconMoodSmile,
  IconRefresh,
  IconAlertCircle,
  IconMoodHappy,
  IconMoodSad,
  IconMoodAngry,
  IconMoodNeutral,
  IconMoodCry,
  IconActivity,
  IconAlertTriangle,
  IconUsers,
  IconTrophy,
  IconFlame,
  IconSpeakerphone,
  IconPlayerPause,
  IconEyeOff,
  IconRocket,
  IconSun,
  IconInfoCircle,
  IconArrowsShuffle,
  IconHeartBroken,
} from '@tabler/icons-react';
import { WidgetComponentProps } from '@/types/widgets.types';
import { authFetch } from '@/utils/authFetch';

const apiUrl = import.meta.env.VITE_API_URL;

interface EmotionData {
  emotion: string;
  count: number;
  percentage: number;
  icon: React.ComponentType<any>;
  color: string;
}

const emotionConfig: Record<string, { icon: React.ComponentType<any>; color: string }> = {
  positive: { icon: IconMoodHappy, color: 'green' },
  negative: { icon: IconMoodSad, color: 'red' },
  neutral: { icon: IconMoodNeutral, color: 'gray' },
  angry: { icon: IconMoodAngry, color: 'orange' },
  sad: { icon: IconMoodCry, color: 'blue' },
  // German mappings
  'Wut / Aggression': { icon: IconMoodAngry, color: 'red' },
  'Hass / Feindbild': { icon: IconMoodAngry, color: 'dark' },
  'Empörung / Entrüstung': { icon: IconAlertCircle, color: 'orange' },
  'Angst / Bedrohungsempfinden': { icon: IconMoodCry, color: 'violet' },
  'Panik / Hysterie': { icon: IconAlertTriangle, color: 'red' },
  'Verzweiflung / Hoffnungslosigkeit': { icon: IconMoodSad, color: 'gray' },
  'Trauer / Mitgefühl': { icon: IconHeartBroken, color: 'blue' },
  'Solidarität / Zusammenhalt': { icon: IconUsers, color: 'teal' },
  'Stolz / Selbstermächtigung': { icon: IconTrophy, color: 'cyan' },
  'Freude / Zufriedenheit': { icon: IconMoodHappy, color: 'green' },
  'Ironie / Sarkasmus': { icon: IconMoodSmile, color: 'grape' },
  'Aggressive Motivation / Aufpeitschend': { icon: IconFlame, color: 'orange' },
  'Feindliche Mobilisierung': { icon: IconSpeakerphone, color: 'red' },
  'Resignation / Rückzug': { icon: IconPlayerPause, color: 'gray' },
  'Misstrauen / Paranoia': { icon: IconEyeOff, color: 'yellow' },
  'Euphorie / Begeisterung': { icon: IconRocket, color: 'lime' },
  'Zynismus / Verachtung': { icon: IconMoodNeutral, color: 'gray' },
  'Mobilisierende Hoffnung': { icon: IconSun, color: 'cyan' },
  'Neutral / Informationsorientiert': { icon: IconInfoCircle, color: 'blue' },
  'Ambivalent / Gemischt': { icon: IconArrowsShuffle, color: 'grape' },
};

const fetchEmotions = async (config: any): Promise<EmotionData[]> => {
  const base = apiUrl ?? 'http://localhost:8000/api';
  const channelIds = config.filters?.channelIds || [];
  const limit = config.filters?.limit || 5;

  if (!channelIds || channelIds.length === 0) return [];

  try {
    const results = await Promise.all(
      channelIds.map(async (channelId: string) => {
        const url = new URL(`${base}/messages/channels/${channelId}/emotions`);
        const res = await authFetch(url.toString());
        if (!res.ok) {
            console.warn(`Failed to fetch emotions for channel ${channelId}`);
            return [];
        }
        return await res.json();
      })
    );

    const allEmotions = results.flat();
    const emotionCounts = new Map<string, number>();

    allEmotions.forEach((item: any) => {
      const emotion = item.emotion || 'neutral';
      const count = item.count || 0;
      emotionCounts.set(emotion, (emotionCounts.get(emotion) || 0) + count);
    });

    const total = Array.from(emotionCounts.values()).reduce((a, b) => a + b, 0);
    
    if (total === 0) return [];

    const emotions: EmotionData[] = Array.from(emotionCounts.entries())
      .map(([emotion, count]) => ({
        emotion,
        count,
        percentage: (count / total) * 100,
        icon: emotionConfig[emotion]?.icon || IconMoodNeutral,
        color: emotionConfig[emotion]?.color || 'gray',
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, limit);

    return emotions;
  } catch (error) {
    console.error('Error in fetchEmotions:', error);
    throw error;
  }
};

export const EmotionAnalysisWidget: React.FC<WidgetComponentProps> = ({
  widget,
  onUpdate,
  onRemove,
  isEditing,
}) => {
  const [emotions, setEmotions] = useState<EmotionData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const loadEmotions = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        const data = await fetchEmotions(widget.config);
        setEmotions(data);
      } catch (err) {
        setError(err as Error);
      } finally {
        setIsLoading(false);
      }
    };

    loadEmotions();

    const refreshInterval = widget.config.refreshInterval;
    if (refreshInterval && refreshInterval > 0) {
      const intervalId = setInterval(loadEmotions, refreshInterval);
      return () => clearInterval(intervalId);
    }
  }, [widget.config, refreshKey]);

  if (isLoading) {
    return <Skeleton height={300} radius="md" />;
  }

  if (error) {
    return (
      <Alert icon={<IconAlertCircle size={16} />} color="red" title="Error loading emotions">
        <Text size="sm">{error.message}</Text>
      </Alert>
    );
  }

  if (!emotions || emotions.length === 0) {
    return (
      <Box style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '200px' }}>
        <IconMoodSmile size={32} stroke={1.5} style={{ opacity: 0.5 }} />
        <Text size="sm" c="dimmed" mt="sm">No emotion data found</Text>
      </Box>
    );
  }

  const topEmotion = emotions[0];
  const Icon = topEmotion.icon;

  return (
    <Box style={{ position: 'relative' }}>
      <Group justify="flex-end" mb="xs">
        <Tooltip label="Refresh">
          <ActionIcon variant="subtle" size="sm" onClick={() => setRefreshKey(p => p + 1)}>
            <IconRefresh size={16} />
          </ActionIcon>
        </Tooltip>
      </Group>

      <Group align="center" gap="xl">
        <RingProgress
          size={180}
          thickness={16}
          sections={emotions.map(e => ({
            value: e.percentage,
            color: e.color,
          }))}
          label={
            <Box style={{ textAlign: 'center' }}>
              <Icon size={32} />
              <Text size="xs" c="dimmed" mt={4}>
                Dominant
              </Text>
            </Box>
          }
        />

        <Stack gap="xs" style={{ flex: 1 }}>
          {emotions.map((emotion, index) => {
            const EmotionIcon = emotion.icon;
            return (
              <Card key={emotion.emotion} withBorder padding="xs">
                <Group justify="space-between">
                  <Group gap="xs">
                    <Badge size="sm" variant="dot" color={emotion.color}>
                      #{index + 1}
                    </Badge>
                    <EmotionIcon size={16} />
                    <Text size="sm" tt="capitalize">{emotion.emotion}</Text>
                  </Group>
                  <Badge size="sm" color={emotion.color}>
                    {emotion.percentage.toFixed(1)}%
                  </Badge>
                </Group>
              </Card>
            );
          })}
        </Stack>
      </Group>
    </Box>
  );
};