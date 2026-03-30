// src/components/widgets/TopPostsWidget.tsx
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
  Anchor,
  Skeleton,
  Alert,
  ActionIcon,
  Tooltip,
  Button,
} from '@mantine/core';
import {
  IconMessageCircle,
  IconThumbUp,
  IconEye,
  IconExternalLink,
  IconRefresh,
  IconAlertCircle,
} from '@tabler/icons-react';
import { WidgetComponentProps } from '@/types/widgets.types';
import { authFetch } from '@/utils/authFetch';
import { formatRelativeTime, formatNumber } from '@/components/MessagesTab/utils';
import classes from './TopPostsWidget.module.css';

const apiUrl = import.meta.env.VITE_API_URL;

interface Author {
  id: string;
  name: string;
  username?: string;
}

interface Message {
  message_id: string;
  channel_id: string;
  original_text: string;
  translated_text?: string;
  text: string;
  date: string;
  channel_title?: string;
  author?: Author;
  views?: number;
  forwards?: number;
  replies?: number;
}

interface ChannelInfo {
  channel_id: string;
  title?: string;
  username?: string;
}

// Fetch messages from API
const fetchTopPosts = async (config: any): Promise<Message[]> => {
  const base = apiUrl ?? 'http://localhost:8000/api';
  const limit = config.filters?.limit || 5;
  const channelIds = config.filters?.channelIds || [];
  const keywords = config.filters?.keywords || '';

  // If no channels are selected, return empty array
  if (!channelIds || channelIds.length === 0) {
    return [];
  }

  try {
    // Fetch channel information first
    const channelInfoMap = new Map<string, ChannelInfo>();
    try {
      const channelsRes = await authFetch(`${base}/messages/channels`);
      const channelsData = await channelsRes.json();

      channelsData.forEach((channel: any) => {
        channelInfoMap.set(channel.channel_id, {
          channel_id: channel.channel_id,
          title: channel.title || channel.username || channel.channel_id,
          username: channel.username,
        });
      });
    } catch (error) {
      console.error('Error fetching channel information:', error);
    }

    // Fetch messages from each selected channel
    const resultsPerChannel = await Promise.all(
      channelIds.map(async (channelId: string) => {
        try {
          const url = new URL(`${base}/messages/channels/${channelId}/messages`);
          url.searchParams.set('limit', String(limit * 2)); // Fetch more to have options for filtering
          
          if (keywords && keywords.trim()) {
            url.searchParams.set('q', keywords.trim());
          }

          const res = await authFetch(url.toString());
          const data = await res.json();

          return {
            channelId,
            messages: data.map((msg: any) => ({
              ...msg,
              channel_id: channelId,
              channel_title: channelInfoMap.get(channelId)?.title || channelId,
            })),
          };
        } catch (error) {
          console.error(`Error fetching messages for channel ${channelId}:`, error);
          return { channelId, messages: [] };
        }
      })
    );

    // Combine and sort messages
    let allMessages: Message[] = [];

    if (resultsPerChannel.length === 1) {
      // Single channel: just take top messages
      allMessages = resultsPerChannel[0].messages
        .sort((a: any, b: any) => new Date(b.date).getTime() - new Date(a.date).getTime())
        .slice(0, limit);
    } else if (resultsPerChannel.length > 1) {
      // Multiple channels: interleave messages from different channels
      const maxPerChannel = Math.ceil(limit / resultsPerChannel.length);
      
      resultsPerChannel.forEach((result) => {
        const sorted = result.messages
          .sort((a: any, b: any) => new Date(b.date).getTime() - new Date(a.date).getTime())
          .slice(0, maxPerChannel);
        allMessages.push(...sorted);
      });

      // Sort combined messages by date and take top N
      allMessages = allMessages
        .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
        .slice(0, limit);
    }

    return allMessages;
  } catch (error) {
    console.error('Error in fetchTopPosts:', error);
    throw error;
  }
};

export const TopPostsWidget: React.FC<WidgetComponentProps> = ({
  widget,
  onUpdate,
  onRemove,
  isEditing,
}) => {
  const [posts, setPosts] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  // Load messages on mount and when config changes
  useEffect(() => {
    const loadMessages = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        const messages = await fetchTopPosts(widget.config);
        setPosts(messages);
      } catch (err) {
        setError(err as Error);
        console.error('Error loading top posts:', err);
      } finally {
        setIsLoading(false);
      }
    };

    loadMessages();

    // Set up refresh interval if configured
    const refreshInterval = widget.config.refreshInterval;
    if (refreshInterval && refreshInterval > 0) {
      const intervalId = setInterval(() => {
        loadMessages();
      }, refreshInterval);

      return () => clearInterval(intervalId);
    }
  }, [widget.config, refreshKey]);

  // Handle manual refresh
  const handleManualRefresh = () => {
    setRefreshKey(prev => prev + 1);
  };

  // Calculate relevance score (simplified version)
  const calculateRelevanceScore = (message: Message): number => {
    // This is a simple relevance calculation
    // You can enhance this based on your needs
    let score = 50; // Base score

    // Boost for having text
    if (message.text && message.text.length > 50) {
      score += 20;
    }

    // Boost for having engagement metrics
    if (message.views) {
      score += Math.min(15, Math.log10(message.views) * 3);
    }
    
    if (message.forwards) {
      score += Math.min(10, message.forwards);
    }

    if (message.replies) {
      score += Math.min(5, message.replies);
    }

    return Math.min(100, score);
  };

  if (isLoading) {
    return (
      <Stack gap="sm">
        {Array.from({ length: widget.config.filters?.limit || 5 }, (_, i) => (
          <Skeleton key={i} height={120} radius="md" />
        ))}
      </Stack>
    );
  }

  if (error) {
    return (
      <Alert
        icon={<IconAlertCircle size={16} />}
        color="red"
        title="Error loading posts"
      >
        <Text size="sm">{error.message}</Text>
        <Button
          size="xs"
          variant="subtle"
          onClick={handleManualRefresh}
          mt="xs"
        >
          Try Again
        </Button>
      </Alert>
    );
  }

  if (!posts || posts.length === 0) {
    return (
      <Box style={{ 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        justifyContent: 'center',
        height: '100%',
        minHeight: '200px'
      }}>
        <IconMessageCircle size={32} stroke={1.5} style={{ opacity: 0.5 }} />
        <Text size="sm" c="dimmed" mt="sm">
          No posts found
        </Text>
        {(!widget.config.filters?.channelIds || widget.config.filters.channelIds.length === 0) && (
          <Text size="xs" c="dimmed" mt="xs">
            Please select channels in widget settings
          </Text>
        )}
      </Box>
    );
  }

  return (
    <Box style={{ position: 'relative' }}>
      {/* Refresh button */}
      <Group justify="flex-end" mb="xs">
        <Tooltip label="Refresh">
          <ActionIcon
            variant="subtle"
            size="sm"
            onClick={handleManualRefresh}
          >
            <IconRefresh size={16} />
          </ActionIcon>
        </Tooltip>
      </Group>

      <ScrollArea h="calc(100% - 40px)" scrollbarSize={6}>
        <Stack gap="sm">
          {posts.map((post, index) => {
            const relevanceScore = calculateRelevanceScore(post);
            const displayText = post.translated_text || post.original_text || post.text || '';
            
            return (
              <Card
                key={`${post.message_id}-${post.channel_id}`}
                withBorder
                radius="md"
                padding="sm"
                style={{ cursor: 'pointer' }}
              >
                {/* Post Header */}
                <Group justify="space-between" mb="xs">
                  <Group gap="xs">
                    <Badge size="sm" variant="dot" color="blue">
                      #{index + 1}
                    </Badge>
                    <Badge size="xs" variant="light">
                      {post.channel_title || post.channel_id}
                    </Badge>
                    <Text size="xs" c="dimmed">
                      {formatRelativeTime(post.date)}
                    </Text>
                  </Group>
                  
                  <Tooltip label="Open in Telegram">
                    <ActionIcon
                      variant="subtle"
                      size="sm"
                      component="a"
                      href={`https://t.me/c/${post.channel_id}/${post.message_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <IconExternalLink size={14} />
                    </ActionIcon>
                  </Tooltip>
                </Group>

                {/* Author (if available) */}
                {post.author && (
                  <Group gap="xs" mb="xs">
                    <Avatar size="sm" radius="xl">
                      {post.author.name ? post.author.name[0] : '?'}
                    </Avatar>
                    <div>
                      <Text size="sm" fw={500}>
                        {post.author.name || 'Unknown'}
                      </Text>
                      {post.author.username && (
                        <Text size="xs" c="dimmed">
                          @{post.author.username}
                        </Text>
                      )}
                    </div>
                  </Group>
                )}

                {/* Content */}
                <Text size="xs" c="dimmed" lineClamp={3} mb="sm">
                  {displayText}
                </Text>

                {/* Metrics */}
                <Group gap="lg">
                  {post.views !== undefined && (
                    <Group gap={4}>
                      <IconEye size={14} />
                      <Text size="xs">{formatNumber(post.views)}</Text>
                    </Group>
                  )}
                  {post.forwards !== undefined && post.forwards > 0 && (
                    <Group gap={4}>
                      <IconThumbUp size={14} />
                      <Text size="xs">{formatNumber(post.forwards)}</Text>
                    </Group>
                  )}
                  {post.replies !== undefined && post.replies > 0 && (
                    <Group gap={4}>
                      <IconMessageCircle size={14} />
                      <Text size="xs">{formatNumber(post.replies)}</Text>
                    </Group>
                  )}
                  <Badge
                    size="sm"
                    variant="filled"
                    color={relevanceScore > 70 ? 'green' : relevanceScore > 40 ? 'yellow' : 'gray'}
                  >
                    {relevanceScore.toFixed(0)}% relevant
                  </Badge>
                </Group>
              </Card>
            );
          })}
        </Stack>
      </ScrollArea>
    </Box>
  );
};