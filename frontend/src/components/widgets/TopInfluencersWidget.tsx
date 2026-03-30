// src/components/widgets/TopInfluencersWidget.tsx
import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  Text,
  Group,
  Badge,
  Stack,
  ScrollArea,
  Avatar,
  Skeleton,
  Alert,
  ActionIcon,
  Tooltip,
  Progress,
} from '@mantine/core';
import {
  IconUsers,
  IconRefresh,
  IconAlertCircle,
  IconTrendingUp,
  IconMessage,
} from '@tabler/icons-react';
import { WidgetComponentProps } from '@/types/widgets.types';
import { authFetch } from '@/utils/authFetch';
import { formatNumber } from '@/components/MessagesTab/utils';

const apiUrl = import.meta.env.VITE_API_URL;

interface Influencer {
  id: string;
  name: string;
  username?: string;
  message_count: number;
  total_views: number;
  total_forwards: number;
  avg_engagement: number;
  channels: string[];
}

const fetchTopInfluencers = async (config: any): Promise<Influencer[]> => {
  const base = apiUrl ?? 'http://localhost:8000/api';
  const limit = config.filters?.limit || 5;
  const channelIds = config.filters?.channelIds || [];

  if (!channelIds || channelIds.length === 0) return [];

  try {
    const results = await Promise.all(
      channelIds.map(async (channelId: string) => {
        const url = new URL(`${base}/messages/channels/${channelId}/messages`);
        url.searchParams.set('limit', '1000');
        
        const res = await authFetch(url.toString());
        const messages = await res.json();

        const authorMap = new Map<string, any>();
        
        messages.forEach((msg: any) => {
          if (!msg.author) return;
          
          const authorId = msg.author.id;
          if (!authorMap.has(authorId)) {
            authorMap.set(authorId, {
              id: authorId,
              name: msg.author.name,
              username: msg.author.username,
              message_count: 0,
              total_views: 0,
              total_forwards: 0,
              channels: new Set([channelId]),
            });
          }
          
          const author = authorMap.get(authorId);
          author.message_count++;
          author.total_views += msg.views || 0;
          author.total_forwards += msg.forwards || 0;
          author.channels.add(channelId);
        });

        return Array.from(authorMap.values());
      })
    );

    const allInfluencers = results.flat();
    const merged = new Map<string, Influencer>();

    allInfluencers.forEach((inf) => {
      if (merged.has(inf.id)) {
        const existing = merged.get(inf.id)!;
        existing.message_count += inf.message_count;
        existing.total_views += inf.total_views;
        existing.total_forwards += inf.total_forwards;
        inf.channels.forEach((ch: string) => existing.channels.push(ch));
      } else {
        merged.set(inf.id, {
          ...inf,
          channels: Array.from(inf.channels),
          avg_engagement: 0,
        });
      }
    });

    const influencers = Array.from(merged.values()).map((inf) => ({
      ...inf,
      avg_engagement: inf.message_count > 0 
        ? (inf.total_views + inf.total_forwards * 2) / inf.message_count 
        : 0,
    }));

    return influencers
      .sort((a, b) => b.avg_engagement - a.avg_engagement)
      .slice(0, limit);
  } catch (error) {
    console.error('Error in fetchTopInfluencers:', error);
    throw error;
  }
};

export const TopInfluencersWidget: React.FC<WidgetComponentProps> = ({
  widget,
  onUpdate,
  onRemove,
  isEditing,
}) => {
  const [influencers, setInfluencers] = useState<Influencer[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const loadInfluencers = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        const data = await fetchTopInfluencers(widget.config);
        setInfluencers(data);
      } catch (err) {
        setError(err as Error);
      } finally {
        setIsLoading(false);
      }
    };

    loadInfluencers();

    const refreshInterval = widget.config.refreshInterval;
    if (refreshInterval && refreshInterval > 0) {
      const intervalId = setInterval(loadInfluencers, refreshInterval);
      return () => clearInterval(intervalId);
    }
  }, [widget.config, refreshKey]);


  if (isLoading) {
    return (
      <Stack gap="sm">
        {Array.from({ length: widget.config.filters?.limit || 5 }, (_, i) => (
          <Skeleton key={i} height={100} radius="md" />
        ))}
      </Stack>
    );
  }

  if (error) {
    return (
      <Alert icon={<IconAlertCircle size={16} />} color="red" title="Error loading influencers">
        <Text size="sm">{error.message}</Text>
      </Alert>
    );
  }

  if (!influencers || influencers.length === 0) {
    return (
      <Box style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '200px' }}>
        <IconUsers size={32} stroke={1.5} style={{ opacity: 0.5 }} />
        <Text size="sm" c="dimmed" mt="sm">No influencers found</Text>
      </Box>
    );
  }

  const maxEngagement = Math.max(...influencers.map(i => i.avg_engagement));

  return (
    <Box style={{ position: 'relative' }}>
      <Group justify="flex-end" mb="xs">
        <Tooltip label="Refresh">
          <ActionIcon variant="subtle" size="sm" onClick={() => setRefreshKey(p => p + 1)}>
            <IconRefresh size={16} />
          </ActionIcon>
        </Tooltip>
      </Group>

      <ScrollArea h="calc(100% - 40px)" scrollbarSize={6}>
        <Stack gap="sm">
          {influencers.map((influencer, index) => (
            <Card key={influencer.id} withBorder radius="md" padding="sm">
              <Group justify="space-between" mb="xs">
                <Group gap="xs">
                  <Badge size="sm" variant="dot" color="blue">#{index + 1}</Badge>
                  <Avatar size="md" radius="xl">{influencer.name[0]}</Avatar>
                  <div>
                    <Text size="sm" fw={500}>{influencer.name}</Text>
                    {influencer.username && (
                      <Text size="xs" c="dimmed">@{influencer.username}</Text>
                    )}
                  </div>
                </Group>
                <Badge size="sm" variant="light" leftSection={<IconTrendingUp size={12} />}>
                  {formatNumber(influencer.avg_engagement)}
                </Badge>
              </Group>

              <Progress 
                value={(influencer.avg_engagement / maxEngagement) * 100} 
                size="xs" 
                mb="xs"
                color="blue"
              />

              <Group gap="lg">
                <Group gap={4}>
                  <IconMessage size={14} />
                  <Text size="xs">{influencer.message_count} posts</Text>
                </Group>
                <Text size="xs" c="dimmed">
                  {influencer.channels.length} channel{influencer.channels.length > 1 ? 's' : ''}
                </Text>
              </Group>
            </Card>
          ))}
        </Stack>
      </ScrollArea>
    </Box>
  );
};