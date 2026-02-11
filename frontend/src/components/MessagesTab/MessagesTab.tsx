import { useCallback, useEffect, useRef, useState } from 'react';
import { IconRefresh, IconSearch } from '@tabler/icons-react';
import {
  ActionIcon,
  Anchor,
  Box,
  Checkbox,
  Group,
  Input,
  Loader,
  ScrollArea,
  Table,
  Text,
  Tooltip,
  Switch,
} from '@mantine/core';
import { authFetch } from '@/utils/authFetch';
import classes from './MessagesTab.module.css';

import { formatRelativeTime, isVideoFile, isAudioFile } from './utils';
import { MessageContent } from './components/MessageContent';
import { ImageWithTranscript } from './components/ImageWithTranscript';
import { AudioPlayer } from './components/AudioPlayer';
import { VideoPlayer } from './components/VideoPlayer';

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

  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const [expandedMessages, setExpandedMessages] = useState<Set<string>>(new Set());
  const [showImageTranscripts, setShowImageTranscripts] = useState(false);
  const [showAudioTranscripts, setShowAudioTranscripts] = useState(false);

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

  const deduplicateMessages = useCallback((messages: any[]) => {
    const seen = new Set();
    return messages.filter((msg) => {
      if (seen.has(msg.message_id)) return false;
      seen.add(msg.message_id);
      return true;
    });
  }, []);

  const loadMessages = useCallback(
    async (reset: boolean = false) => {
      if (isLoadingMore && !reset) return;
      setIsLoadingMore(true);
      try {
        const base = apiUrl ?? 'http://localhost:8000/api';
        const currentLastDates = reset
          ? Object.fromEntries(selectedTgChannelIds.map((id) => [id, null]))
          : channelLastDates;

        const results = await Promise.all(
          selectedTgChannelIds.map(async (channelId) => {
            const before = currentLastDates[channelId];
            const url = new URL(`${base}/messages/channels/${channelId}/messages`);
            url.searchParams.set('limit', `${LIMIT}`);
            if (searchQuery) url.searchParams.set('q', searchQuery);
            if (before) url.searchParams.set('before', before);

            const res = await authFetch(url.toString());
            const data = await res.json();
            return { channelId, messages: data };
          })
        );

        const newMessages = results.flatMap((r) => r.messages);
        setMessages((prev) => {
          const combined = reset ? newMessages : [...prev, ...newMessages];
          const deduplicated = deduplicateMessages(combined);
          return deduplicated.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
        });

        const newDates = { ...currentLastDates };
        results.forEach(({ channelId, messages }) => {
          const last = messages[messages.length - 1];
          if (last) newDates[channelId] = last.date;
        });
        setChannelLastDates(newDates);
        setHasMore(results.some((r) => r.messages.length === LIMIT));
      } catch (error) {
        console.error('Error loading messages:', error);
      } finally {
        setIsLoadingMore(false);
      }
    },
    [selectedTgChannelIds, searchQuery, channelLastDates, isLoadingMore, deduplicateMessages]
  );

  const handleRefresh = useCallback(() => {
    if (isRefreshing || selectedTgChannelIds.length === 0) return;
    setIsRefreshing(true);
    setMessages([]);
    setHasMore(true);
    setChannelLastDates(Object.fromEntries(selectedTgChannelIds.map((id) => [id, null])));
    loadMessages(true).finally(() => setIsRefreshing(false));
  }, [selectedTgChannelIds, loadMessages, isRefreshing]);

  useEffect(() => {
    if (selectedTgChannelIds.length > 0) {
      setMessages([]);
      setHasMore(true);
      setChannelLastDates(Object.fromEntries(selectedTgChannelIds.map((id) => [id, null])));
      loadMessages(true);
    }
  }, [selectedTgChannelIds, searchQuery]);

  const handleSearchSubmit = () => {
    setMessages([]);
    setHasMore(true);
    setChannelLastDates(Object.fromEntries(selectedTgChannelIds.map((id) => [id, null])));
    loadMessages(true);
  };

  const messageRows = messages.map((message) => {
    const isExpanded = expandedMessages.has(message.message_id);

    const renderMedia = () => {
      if (!message.media_path) return null;
      if (isVideoFile(message.media_path)) {
        return <VideoPlayer mediaPath={message.media_path} audioText={message.audio_text} 
                            audioTextTranslated={message.audio_text_translated}
                            audioTranscriptionStatus={message.audio_transcription_status} messageId={message.message_id}
                            showAudioTranscripts={showAudioTranscripts} apiUrl={apiUrl} />;
      } else if (isAudioFile(message.media_path)) {
        return <AudioPlayer mediaPath={message.media_path} audioText={message.audio_text}
                            audioTextTranslated={message.audio_text_translated} 
                            audioTranscriptionStatus={message.audio_transcription_status} messageId={message.message_id}
                            mediaType={message.media_type} showAudioTranscripts={showAudioTranscripts} apiUrl={apiUrl} />;
      } else {
        return <ImageWithTranscript mediaPath={message.media_path} imageText={message.image_text}
                                    imageTextTranslated={message.image_text_translated}
                                    imageAnalysisStatus={message.image_analysis_status} messageId={message.message_id}
                                    showImageTranscripts={showImageTranscripts} apiUrl={apiUrl} />;
      }
    };

    return (
      <Table.Tr key={message.message_id} bg={selectedRows.includes(message.message_id) ? 'var(--mantine-color-blue-light)' : undefined}>
        <Table.Td className={classes.checkboxColumn}>
          <Checkbox checked={selectedRows.includes(message.message_id)}
                    onChange={(event) => setSelectedRows(event.currentTarget.checked ? [...selectedRows, message.message_id] : selectedRows.filter((id) => id !== message.message_id))} />
        </Table.Td>
        <Table.Td className={classes.messageCell}>
          <Box>
            <div className={classes.authorRow}>
              <Text size="sm" fw={500} className={classes.authorName}>
                {(!message.channel?.username || message.author?.name.toLowerCase() !== message.channel.username.toLowerCase()) && (
                  <Anchor onClick={() => message.author?.name && onUpdateGraph('user', message.author.name)}>{message.author?.name || 'Unknown Author'}</Anchor>
                )}
                <span className={classes.channelName} style={{ marginLeft: !message.channel?.username || message.author?.name.toLowerCase() !== message.channel.username.toLowerCase() ? '0.25rem' : 0 }}>
                  [<Anchor onClick={() => message.channel?.username && onUpdateGraph('channel', message.channel.username)} className={classes.channelName}>{message.channel?.username || 'Unknown Channel'}</Anchor>]
                </span>
              </Text>
              <Text size="xs" className={classes.timestamp}>{formatRelativeTime(message.date)}</Text>
            </div>
            <Group wrap="nowrap" align="flex-start" justify="space-between">
              <MessageContent message={message} isExpanded={isExpanded} onToggleExpand={() => toggleMessageExpansion(message.message_id)} searchQuery={searchQuery} />
              {renderMedia()}
            </Group>
          </Box>
        </Table.Td>
      </Table.Tr>
    );
  });

  return (
    <div>
      <Group mb="md">
        <Input placeholder="Search messages..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
               onKeyDown={(e) => e.key === 'Enter' && handleSearchSubmit()} leftSection={<IconSearch size={16} />} style={{ flex: 1 }} />
        <Group gap="xs">
          <Switch label="Image transcripts" checked={showImageTranscripts} onChange={(e) => setShowImageTranscripts(e.currentTarget.checked)} size="sm" />
          <Switch label="Audio transcripts" checked={showAudioTranscripts} onChange={(e) => setShowAudioTranscripts(e.currentTarget.checked)} size="sm" />
          <Tooltip label="Refresh for new messages">
            <ActionIcon variant="light" size="lg" onClick={handleRefresh} loading={isRefreshing}><IconRefresh size={18} /></ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      <ScrollArea h={475} viewportRef={scrollRef} onScrollPositionChange={({ y }) => {
        const el = scrollRef.current;
        if (el && el.scrollHeight - y - el.clientHeight < 100 && hasMore && !isLoadingMore) loadMessages(false);
      }}>
        <Table layout="fixed">
          <Table.Thead>
            <Table.Tr>
              <Table.Th className={classes.checkboxColumn}>
                <Checkbox checked={messages.length > 0 && selectedRows.length === messages.length}
                          indeterminate={selectedRows.length > 0 && selectedRows.length < messages.length}
                          onChange={(e) => setSelectedRows(e.currentTarget.checked ? messages.map((m) => m.message_id) : [])} />
              </Table.Th>
              <Table.Th>Messages</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>{messageRows}</Table.Tbody>
        </Table>
        {isLoadingMore && <div style={{ textAlign: 'center', padding: '10px' }}><Loader size="sm" /></div>}
      </ScrollArea>
    </div>
  );
};

export default MessagesTab;