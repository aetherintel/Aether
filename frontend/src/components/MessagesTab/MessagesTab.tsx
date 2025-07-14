import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { IconRefresh, IconSearch } from '@tabler/icons-react';
import {
  ActionIcon,
  Anchor,
  Box,
  Button,
  Checkbox,
  Group,
  Input,
  Loader,
  ScrollArea,
  Table,
  Text,
  Tooltip,
} from '@mantine/core';
import { ImageLightbox } from '@/components/ImageLightbox';
import { authFetch } from '@/utils/authFetch';
import classes from './MessagesTab.module.css';

const apiUrl = import.meta.env.VITE_API_URL;

interface MessagesTabProps {
  selectedTgChannelIds: string[];
  searchQuery: string;
  setSearchQuery: React.Dispatch<React.SetStateAction<string>>;
  onUpdateGraph: (type: string, name: string) => void;
}

const MessagesTab: React.FC<MessagesTabProps> = ({
  selectedTgChannelIds,
  searchQuery,
  setSearchQuery,
  onUpdateGraph,
}) => {
  const LIMIT = 10;
  const scrollRef = useRef<HTMLDivElement>(null);

  const [selectedRows, setSelectedRows] = useState<number[]>([]);
  const [expandedMessages, setExpandedMessages] = useState<Set<string>>(new Set());

  const [messages, setMessages] = useState<any[]>([]);
  const [hasMore, setHasMore] = useState(true);

  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [channelLastDates, setChannelLastDates] = useState<{ [channelId: string]: string | null }>(
    {}
  );

  const toggleMessageExpansion = (messageId: string) => {
    setExpandedMessages((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(messageId)) {
        newSet.delete(messageId);
      } else {
        newSet.add(messageId);
      }
      return newSet;
    });
  };

  // Custom hook to measure if text needs truncation
  const useMeasureText = () => {
    const measureRef = useRef<HTMLDivElement>(null);
    const [needsTruncation, setNeedsTruncation] = useState(false);

    useLayoutEffect(() => {
      if (measureRef.current) {
        const element = measureRef.current;
        const computedStyle = window.getComputedStyle(element);
        const lineHeight = parseFloat(computedStyle.lineHeight);
        const actualHeight = element.scrollHeight;

        // Calculate number of lines (add small tolerance for rounding)
        const lineCount = Math.round(actualHeight / lineHeight);
        setNeedsTruncation(lineCount > 3);
      }
    });

    return { measureRef, needsTruncation };
  };

  // Function to format relative time
  const formatRelativeTime = (dateString: string) => {
    const now = new Date();
    const messageDate = new Date(dateString);
    const diffInSeconds = Math.floor((now.getTime() - messageDate.getTime()) / 1000);

    if (diffInSeconds < 60) {
      return `${diffInSeconds}s ago`;
    } else if (diffInSeconds < 3600) {
      const minutes = Math.floor(diffInSeconds / 60);
      return `${minutes}m ago`;
    } else if (diffInSeconds < 86400) {
      const hours = Math.floor(diffInSeconds / 3600);
      return `${hours}h ago`;
    } else if (diffInSeconds < 2592000) {
      const days = Math.floor(diffInSeconds / 86400);
      return `${days}d ago`;
    }
    return messageDate.toLocaleDateString();
  };

  function highlightText(text: string, query: string) {
    const urlRegex = /https?:\/\/[^\s]+/gi;
    const queryRegex = query ? new RegExp(`(${escapeRegExp(query)})`, 'gi') : null;

    // Split by URLs
    const urlParts = text.split(urlRegex);
    const urls = text.match(urlRegex);

    const result: React.ReactNode[] = [];

    urlParts.forEach((part, i) => {
      // Highlight regular text part (if query is present)
      if (queryRegex) {
        const highlighted = part
          .split(queryRegex)
          .map((p, idx) =>
            queryRegex.test(p) ? <mark key={`highlight-${i}-${idx}`}>{p}</mark> : p
          );
        result.push(...highlighted);
      } else {
        result.push(part);
      }

      // If there's a corresponding URL, render it with optional highlighting
      if (urls && urls[i]) {
        const url = urls[i];
        if (queryRegex) {
          const highlightedLink = url
            .split(queryRegex)
            .map((p, idx) =>
              queryRegex.test(p) ? <mark key={`link-highlight-${i}-${idx}`}>{p}</mark> : p
            );
          result.push(
            <Anchor
              key={`link-${i}`}
              href={url}
              fz="xs"
              target="_blank"
              rel="noopener noreferrer"
              style={{ lineHeight: 1 }}
            >
              {highlightedLink}
            </Anchor>
          );
        } else {
          result.push(
            <Anchor
              key={`link-${i}`}
              href={url}
              fz="sm"
              target="_blank"
              rel="noopener noreferrer"
              style={{ lineHeight: 1 }}
            >
              {url}
            </Anchor>
          );
        }
      }
    });

    return result;
  }

  // Utility to escape RegExp special characters from the query string
  function escapeRegExp(str: string) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  const isVideoFile = (path: string): boolean => {
    const videoExtensions: string[] = [
      '.mp4',
      '.webm',
      '.ogg',
      '.avi',
      '.mov',
      '.wmv',
      '.flv',
      '.mkv',
    ];
    return videoExtensions.some((ext: string) => path.toLowerCase().endsWith(ext));
  };

  const handleSearchSubmit = () => {
    setMessages([]);
    setHasMore(true);
    setChannelLastDates(Object.fromEntries(selectedTgChannelIds.map((id) => [id, null])));
    loadMessages(true);
  };

  const MessageContent = ({
    message,
    isExpanded,
    onToggleExpand,
  }: {
    message: any;
    isExpanded: boolean;
    onToggleExpand: () => void;
  }) => {
    const { measureRef, needsTruncation } = useMeasureText();

    return (
      <div className={classes.messageContent}>
        <div
          ref={measureRef}
          className={`${classes.messageText} ${
            isExpanded ? classes.messageTextExpanded : classes.messageTextTruncated
          }`}
        >
          {highlightText(message.text, searchQuery)}
        </div>
        {needsTruncation && (
          <Button
            variant="subtle"
            size="xs"
            onClick={onToggleExpand}
            className={classes.expandButton}
          >
            {isExpanded ? 'Show less' : 'Show more'}
          </Button>
        )}
      </div>
    );
  };

  // Function to deduplicate messages based on message_id
  const deduplicateMessages = useCallback((messages: any[]) => {
    const seen = new Set();
    return messages.filter((msg) => {
      if (seen.has(msg.message_id)) {
        return false;
      }
      seen.add(msg.message_id);
      return true;
    });
  }, []);

  const loadMessages = useCallback(
    async (reset: boolean = false) => {
      if (isLoadingMore && !reset) {
        return;
      }

      setIsLoadingMore(true);

      try {
        const base = apiUrl ?? 'http://localhost:8000/api';
        const currentLastDates = reset
          ? Object.fromEntries(selectedTgChannelIds.map((id) => [id, null]))
          : channelLastDates;

        const results = await Promise.all(
          selectedTgChannelIds.map(async (channelId) => {
            const before = currentLastDates[channelId];

            /**
             * So könnte man eine richtige Timeline nicht nach channeln sortiert haben:
             * const url = new URL(`${base}/messages/timeline`);
             * url.searchParams.set('channel_ids', selectedTgChannelIds.join(','));
             *
             */

            const url = new URL(`${base}/messages/channels/${channelId}/messages`);
            url.searchParams.set('limit', `${LIMIT}`);
            if (searchQuery) {
              url.searchParams.set('q', searchQuery);
            }
            if (before) {
              url.searchParams.set('before', before);
            }

            const res = await authFetch(url.toString());
            const data = await res.json();
            return { channelId, messages: data };
          })
        );

        const newMessages = results.flatMap((r) => r.messages);

        // Update messages with deduplication and proper sorting
        setMessages((prev) => {
          const combined = reset ? newMessages : [...prev, ...newMessages];
          const deduplicated = deduplicateMessages(combined);
          // Sort the entire combined array to maintain proper chronological order
          return deduplicated.sort(
            (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
          );
        });

        // Update last dates for pagination
        const newDates = { ...currentLastDates };
        results.forEach(({ channelId, messages }) => {
          const last = messages[messages.length - 1];
          if (last) {
            newDates[channelId] = last.date;
          }
        });
        setChannelLastDates(newDates);

        // Check if there are more messages to load
        const more = results.some((r) => r.messages.length === LIMIT);
        setHasMore(more);
      } catch (error) {
        console.error('Error loading messages:', error);
      } finally {
        setIsLoadingMore(false);
      }
    },
    [selectedTgChannelIds, searchQuery, channelLastDates, isLoadingMore, deduplicateMessages]
  );

  // Simple full refresh function - moved after loadMessages declaration
  const handleRefresh = useCallback(() => {
    if (isRefreshing || selectedTgChannelIds.length === 0) {
      return;
    }

    setIsRefreshing(true);
    setMessages([]);
    setHasMore(true);
    setChannelLastDates(Object.fromEntries(selectedTgChannelIds.map((id) => [id, null])));

    // Just reload all messages from the beginning
    loadMessages(true).finally(() => {
      setIsRefreshing(false);
    });
  }, [selectedTgChannelIds, loadMessages, isRefreshing]);

  // Reset and load initial messages when channels or search query changes
  useEffect(() => {
    if (selectedTgChannelIds.length > 0) {
      setMessages([]);
      setHasMore(true);
      setChannelLastDates(Object.fromEntries(selectedTgChannelIds.map((id) => [id, null])));
      loadMessages(true);
    }
  }, [selectedTgChannelIds, searchQuery]);

  const messageRows = messages.map((message) => {
    const isExpanded = expandedMessages.has(message.message_id);

    return (
      <Table.Tr
        key={message.message_id}
        bg={
          selectedRows.includes(message.message_id) ? 'var(--mantine-color-blue-light)' : undefined
        }
      >
        <Table.Td className={classes.checkboxColumn}>
          <Checkbox
            aria-label="Select row"
            checked={selectedRows.includes(message.message_id)}
            onChange={(event) =>
              setSelectedRows(
                event.currentTarget.checked
                  ? [...selectedRows, message.message_id]
                  : selectedRows.filter((position) => position !== message.message_id)
              )
            }
          />
        </Table.Td>
        <Table.Td className={classes.messageCell}>
          <Box>
            <div className={classes.authorRow}>
              <Text size="sm" fw={500} className={classes.authorName}>
                <Anchor onClick={() => onUpdateGraph('user', message.author.name)}>
                  {message.author.name}
                </Anchor>
                <span className={classes.channelName} style={{ marginLeft: '0.25rem' }}>
                  [
                  <Anchor
                    onClick={() => onUpdateGraph('channel', message.channel.username)}
                    className={classes.channelName}
                  >
                    {message.channel.username}
                  </Anchor>
                  ]
                </span>
              </Text>
              <Text size="xs" className={classes.timestamp}>
                {formatRelativeTime(message.date)}
              </Text>
            </div>
            <Group wrap="nowrap" align="flex-start" justify="space-between">
              <MessageContent
                message={message}
                isExpanded={isExpanded}
                onToggleExpand={() => toggleMessageExpansion(message.message_id)}
              />
              {message.media_path &&
                (isVideoFile(message.media_path) ? (
                  // eslint-disable-next-line jsx-a11y/media-has-caption
                  <video src={message.media_path} className={classes.messageVideo} controls>
                    Your browser does not support the video tag.
                  </video>
                ) : (
                  <ImageLightbox
                    key={message.media_path}
                    image={message.media_path}
                    thumbnailWidth={200}
                    thumbnailHeight={120}
                  />
                ))}
            </Group>
          </Box>
        </Table.Td>
      </Table.Tr>
    );
  });

  return (
    <div>
      <Group mb="md">
        <Input
          placeholder="Search messages..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              handleSearchSubmit();
            }
          }}
          leftSection={<IconSearch size={16} />}
          style={{ flex: 1 }}
        />
        <Tooltip label="Refresh for new messages">
          <ActionIcon
            variant="light"
            size="lg"
            onClick={handleRefresh}
            loading={isRefreshing}
            disabled={selectedTgChannelIds.length === 0}
          >
            <IconRefresh size={18} />
          </ActionIcon>
        </Tooltip>
      </Group>

      <ScrollArea
        h={475}
        viewportRef={scrollRef}
        onScrollPositionChange={({ y }) => {
          const el = scrollRef.current;
          if (el && el.scrollHeight - y - el.clientHeight < 100 && hasMore && !isLoadingMore) {
            loadMessages(false);
          }
        }}
      >
        <Table layout="fixed">
          <Table.Thead>
            <Table.Tr>
              <Table.Th className={classes.checkboxColumn}>
                <Checkbox
                  aria-label="Select all messages"
                  checked={messages.length > 0 && selectedRows.length === messages.length}
                  indeterminate={selectedRows.length > 0 && selectedRows.length < messages.length}
                  onChange={(event) => {
                    if (event.currentTarget.checked) {
                      setSelectedRows(messages.map((msg) => msg.message_id));
                    } else {
                      setSelectedRows([]);
                    }
                  }}
                />
              </Table.Th>
              <Table.Th>Messages</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>{messageRows}</Table.Tbody>
        </Table>
        {isLoadingMore && (
          <div style={{ textAlign: 'center', padding: '10px' }}>
            <Loader size="sm" />
          </div>
        )}
      </ScrollArea>
    </div>
  );
};

export default MessagesTab;
