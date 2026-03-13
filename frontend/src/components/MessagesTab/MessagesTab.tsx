import { useCallback, useEffect, useRef, useState } from 'react';
import { useSSE } from '@/hooks/useSSE';
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
  Switch,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { authFetch } from '@/utils/authFetch';
import { useAuthStore } from '@/store/client/authStore';
import classes from './MessagesTab.module.css';

import { formatRelativeTime, isVideoFile, isAudioFile } from './utils';
import { MessageContent } from './components/MessageContent';
import { ImageWithTranscript } from './components/ImageWithTranscript';
import { AudioPlayer } from './components/AudioPlayer';
import { VideoPlayer } from './components/VideoPlayer';
import { MessageActions } from './components/MessageActions';

const apiUrl = import.meta.env.VITE_API_URL;

interface MessagesTabProps {
  selectedTgChannelIds: string[];
  searchQuery: string;
  setSearchQuery: React.Dispatch<React.SetStateAction<string>>;
  onUpdateGraph: (type: string, name: string) => void;
  caseId: number;
}

function decodeOwnerId(token: string | null): string {
  if (!token) return '';
  try {
    return JSON.parse(atob(token.split('.')[1])).sub ?? '';
  } catch {
    return '';
  }
}

const MessagesTab: React.FC<MessagesTabProps> = ({
  selectedTgChannelIds,
  searchQuery,
  setSearchQuery,
  onUpdateGraph,
  caseId,
}) => {
  const LIMIT = 10;
  const scrollRef = useRef<HTMLDivElement>(null);

  const token = useAuthStore((s) => s.token);
  const ownerId = decodeOwnerId(token);

  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const [expandedMessages, setExpandedMessages] = useState<Set<string>>(new Set());
  const [showImageTranscripts, setShowImageTranscripts] = useState(true);
  const [showAudioTranscripts, setShowAudioTranscripts] = useState(true);

  const [messages, setMessages] = useState<any[]>([]);
  const [hasMore, setHasMore] = useState(true);

  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const isLoadingMoreRef = useRef(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const channelLastDatesRef = useRef<{ [channelId: string]: string | null }>({});

  const toggleMessageExpansion = (messageId: string) => {
    setExpandedMessages((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(messageId)) newSet.delete(messageId);
      else newSet.add(messageId);
      return newSet;
    });
  };

  const deduplicateMessages = useCallback((msgs: any[]) => {
    const seen = new Set();
    return msgs.filter((msg) => {
      if (seen.has(msg.message_id)) return false;
      seen.add(msg.message_id);
      return true;
    });
  }, []);

  /** Optimistically update status fields on a single message in local state */
  const handleStatusChange = useCallback((messageId: string, updates: Record<string, string>) => {
    setMessages((prev) =>
      prev.map((m) => (m.message_id === messageId ? { ...m, ...updates } : m))
    );
  }, []);

  /** Live updates from workers via SSE */
  useSSE(useCallback((event) => {
    if (event.type === 'message_status_changed') {
      handleStatusChange(event.message_id, event.updates as Record<string, string>);
    }
  }, [handleStatusChange]));

  const loadMessages = useCallback(
    async (reset: boolean = false) => {
      if (isLoadingMoreRef.current && !reset) return;
      isLoadingMoreRef.current = true;
      setIsLoadingMore(true);
      try {
        const base = apiUrl ?? 'http://localhost:8000/api';
        const currentLastDates = reset
          ? Object.fromEntries(selectedTgChannelIds.map((id) => [id, null]))
          : channelLastDatesRef.current;

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
        results.forEach(({ channelId, messages: msgs }) => {
          const last = msgs[msgs.length - 1];
          if (last) newDates[channelId] = last.date;
        });
        channelLastDatesRef.current = newDates;
        channelLastDatesRef.current =(newDates);
        setHasMore(results.some((r) => r.messages.length === LIMIT));
      } catch (error) {
        console.error('Error loading messages:', error);
      } finally {
        isLoadingMoreRef.current = false;
        setIsLoadingMore(false);
      }
    },
    [selectedTgChannelIds, searchQuery, deduplicateMessages]
  );

  const handleRefresh = useCallback(() => {
    if (isRefreshing || selectedTgChannelIds.length === 0) return;
    setIsRefreshing(true);
    setMessages([]);
    setHasMore(true);
    channelLastDatesRef.current =(Object.fromEntries(selectedTgChannelIds.map((id) => [id, null])));
    loadMessages(true).finally(() => setIsRefreshing(false));
  }, [selectedTgChannelIds, loadMessages, isRefreshing]);

  useEffect(() => {
    if (selectedTgChannelIds.length > 0) {
      setMessages([]);
      setHasMore(true);
      channelLastDatesRef.current =(Object.fromEntries(selectedTgChannelIds.map((id) => [id, null])));
      loadMessages(true);
    }
  }, [selectedTgChannelIds, searchQuery]);

  const handleSearchSubmit = () => {
    setMessages([]);
    setHasMore(true);
    channelLastDatesRef.current =(Object.fromEntries(selectedTgChannelIds.map((id) => [id, null])));
    loadMessages(true);
  };

  // ─── Bulk actions ───────────────────────────────────────────────────────────

  const bulkEnqueue = async (
    endpoint: string,
    buildPayload: (msg: any) => object | null,
    label: string,
    statusKey: string,
  ) => {
    const targets = messages.filter(
      (m) => selectedRows.includes(m.message_id) && buildPayload(m) !== null
    );
    if (targets.length === 0) {
      notifications.show({ title: 'Nothing to do', message: `All selected messages already have ${label}`, color: 'yellow' });
      return;
    }

    const results = await Promise.allSettled(
      targets.map((m) =>
        authFetch(`${apiUrl}/${endpoint}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(buildPayload(m)),
        })
      )
    );

    const succeeded = results.filter((r) => r.status === 'fulfilled').length;
    const failed = results.length - succeeded;

    // Optimistic update for succeeded jobs
    targets.forEach((m, i) => {
      if (results[i].status === 'fulfilled') {
        handleStatusChange(m.message_id, { [statusKey]: 'pending' });
      }
    });

    notifications.show({
      title: `${label} queued`,
      message: `${succeeded} job(s) queued${failed > 0 ? `, ${failed} failed` : ''}`,
      color: succeeded > 0 ? 'green' : 'red',
    });
  };

  const bulkTranslate = () =>
    bulkEnqueue(
      'queue/translation',
      (m) =>
        m.original_text?.trim() &&
        m.original_language !== 'de' &&
        m.translation_status !== 'completed'
          ? { message_id: m.message_id, original_text: m.original_text, source_language: m.original_language || 'en', owner_id: ownerId, case_id: caseId }
          : null,
      'Translation',
      'translation_status',
    );

  const bulkOcr = () =>
    bulkEnqueue(
      'queue/image',
      (m) =>
        m.media_path && !isAudioFile(m.media_path) && !isVideoFile(m.media_path) &&
        m.image_analysis_status !== 'completed'
          ? { message_id: m.message_id, image_path: m.media_path, extract_text: true, detect_objects: false, translate_extracted_text: true, owner_id: ownerId, case_id: caseId }
          : null,
      'OCR',
      'image_analysis_status',
    );

  const bulkClassify = () =>
    bulkEnqueue(
      'queue/classification',
      (m) => {
        const text = m.translated_text?.trim() || m.original_text?.trim();
        return text &&
          m.classification_status !== 'completed'
          ? { message_id: m.message_id, text, owner_id: ownerId, case_id: caseId }
          : null;
      },
      'Classification',
      'classification_status',
    );

  const bulkEmotion = () =>
    bulkEnqueue(
      'queue/emotion',
      (m) => {
        const text = m.translated_text?.trim() || m.original_text?.trim();
        return text &&
          m.emotion_status !== 'completed'
          ? { message_id: m.message_id, text, owner_id: ownerId, case_id: caseId }
          : null;
      },
      'Emotion',
      'emotion_status',
    );

  const bulkGeo = () =>
    bulkEnqueue(
      'queue/geolocation',
      (m) => {
        const text = m.translated_text?.trim() || m.original_text?.trim();
        const done = ['completed', 'no_location', 'no_coordinates', 'failed'].includes(m.geolocation_status);
        return text && !done
          ? { message_id: m.message_id, text, owner_id: ownerId, case_id: caseId }
          : null;
      },
      'Geolocation',
      'geolocation_status',
    );

  // ─── Render ─────────────────────────────────────────────────────────────────

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
              <Group gap="xs">
                <MessageActions
                  message={message}
                  caseId={caseId}
                  ownerId={ownerId}
                  onStatusChange={handleStatusChange}
                />
                <Text size="xs" className={classes.timestamp}>{formatRelativeTime(message.date)}</Text>
              </Group>
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

      {selectedRows.length > 0 && (
        <Group mb="sm" gap="xs">
          <Text size="sm" c="dimmed">{selectedRows.length} selected:</Text>
          <Button size="xs" variant="light" color="blue" onClick={bulkTranslate}>Translate</Button>
          <Button size="xs" variant="light" color="orange" onClick={bulkOcr}>OCR</Button>
          <Button size="xs" variant="light" color="violet" onClick={bulkClassify}>Classify</Button>
          <Button size="xs" variant="light" color="pink" onClick={bulkEmotion}>Emotions</Button>
          <Button size="xs" variant="light" color="teal" onClick={bulkGeo}>Geolocate</Button>
        </Group>
      )}

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
