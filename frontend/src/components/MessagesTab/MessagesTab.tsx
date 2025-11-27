import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { IconRefresh, IconSearch, IconVolume, IconPhoto } from '@tabler/icons-react';
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
  Popover,
  Textarea,
  Badge,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
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

  const useMeasureText = () => {
    const measureRef = useRef<HTMLDivElement>(null);
    const [needsTruncation, setNeedsTruncation] = useState(false);

    useLayoutEffect(() => {
      if (measureRef.current) {
        const element = measureRef.current;
        const computedStyle = window.getComputedStyle(element);
        const lineHeight = parseFloat(computedStyle.lineHeight);
        const actualHeight = element.scrollHeight;
        const lineCount = Math.round(actualHeight / lineHeight);
        setNeedsTruncation(lineCount > 3);
      }
    });

    return { measureRef, needsTruncation };
  };

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
    const urlParts = text.split(urlRegex);
    const urls = text.match(urlRegex);
    const result: React.ReactNode[] = [];

    urlParts.forEach((part, i) => {
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

  const isAudioFile = (path: string): boolean => {
    const audioExtensions: string[] = ['.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac'];
    return audioExtensions.some((ext: string) => path.toLowerCase().endsWith(ext));
  };

  const handleSearchSubmit = () => {
    setMessages([]);
    setHasMore(true);
    setChannelLastDates(Object.fromEntries(selectedTgChannelIds.map((id) => [id, null])));
    loadMessages(true);
  };

  interface MessageContentProps {
    message: {
      original_text: string;
      translated_text?: string | null;
      original_language?: string;
      translation_status?: string;
    };
    searchQuery?: string;
    isExpanded: boolean;
    onToggleExpand: () => void;
  }

  const MessageContent = ({
    message,
    searchQuery = '',
    isExpanded,
    onToggleExpand,
  }: MessageContentProps) => {
    const { measureRef, needsTruncation } = useMeasureText();
    const [showOriginal, setShowOriginal] = useState(false);
    console.log(message);
    const hasTranslation =
      !!message.translated_text &&
      message.translated_text.trim().length > 0 &&
      message.translation_status === 'completed';

    const displayedText =
      (showOriginal || !hasTranslation ? message.original_text : message.translated_text) || '';

    const handleToggleLanguage = () => setShowOriginal((prev) => !prev);

    const languageLabel =
      message.original_language && message.original_language.length > 0
        ? message.original_language.toUpperCase()
        : 'N/A';

    return (
      <div className={classes.messageContent}>
        <div
          ref={measureRef}
          className={`${classes.messageText} ${
            isExpanded ? classes.messageTextExpanded : classes.messageTextTruncated
          }`}
        >
          {highlightText(displayedText, searchQuery || '')}
        </div>

        <div className={classes.actionsRow}>
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

          {hasTranslation && (
            <Button
              variant="subtle"
              size="xs"
              onClick={handleToggleLanguage}
              className={classes.languageToggle}
            >
              {showOriginal ? 'View German translation' : `View original (${languageLabel})`}
            </Button>
          )}
        </div>
      </div>
    );
  };

  const ImageWithTranscript = ({ mediaPath, imageText, imageTextTranslated, imageAnalysisStatus, messageId }: any) => {
    const [opened, setOpened] = useState(false);
    const [isPinned, setIsPinned] = useState(false);
    const [showOriginal, setShowOriginal] = useState(false);
    const [isTriggering, setIsTriggering] = useState(false);

    const hasTranscript = imageText && imageText.trim().length > 0;
    const hasTranslation = imageTextTranslated && imageTextTranslated.trim().length > 0;
    const needsProcessing = imageAnalysisStatus === 'none';
    const isProcessing = imageAnalysisStatus === 'pending';

    const handleMouseEnter = () => {
      if (!isPinned) setOpened(true);
    };

    const handleMouseLeave = () => {
      if (!isPinned) setOpened(false);
    };

    const handleClick = () => {
      setIsPinned(!isPinned);
      setOpened(true);
    };

    const handleClose = () => {
      setIsPinned(false);
      setOpened(false);
    };

    const handleTriggerImageAnalysis = async () => {
      setIsTriggering(true);
      try {
        const response = await authFetch(`${apiUrl}/queue/image`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message_id: messageId,
            image_path: mediaPath,
            extract_text: true,
            detect_objects: false,
            translate_extracted_text: true,
          }),
        });

        if (!response.ok) {
          throw new Error('Failed to trigger image analysis');
        }

        notifications.show({
          title: 'Success',
          message: 'Image analysis job queued',
          color: 'green',
        });
      } catch (error: any) {
        notifications.show({
          title: 'Error',
          message: error.message || 'Failed to trigger image analysis',
          color: 'red',
        });
      } finally {
        setIsTriggering(false);
      }
    };

    return (
      <Box style={{ position: 'relative' }}>
        <ImageLightbox image={mediaPath} thumbnailWidth={200} thumbnailHeight={120} />
        
        {showImageTranscripts && needsProcessing && (
          <Box
            onClick={handleTriggerImageAnalysis}
            style={{
              position: 'absolute',
              top: 4,
              right: 4,
              cursor: 'pointer',
            }}
          >
            <Badge
              leftSection={<IconPhoto size={12} />}
              color="orange"
              variant="filled"
              size="sm"
            >
              {isTriggering ? 'Starting...' : 'No Transcript'}
            </Badge>
          </Box>
        )}

        {showImageTranscripts && isProcessing && (
          <Box
            style={{
              position: 'absolute',
              top: 4,
              right: 4,
            }}
          >
            <Badge
              leftSection={<IconPhoto size={12} />}
              color="yellow"
              variant="filled"
              size="sm"
            >
              Processing...
            </Badge>
          </Box>
        )}
        
        {showImageTranscripts && hasTranscript && (
          <Popover width={300} position="bottom" withArrow shadow="md" opened={opened} onChange={setOpened}>
            <Popover.Target>
              <Box
                onMouseEnter={handleMouseEnter}
                onMouseLeave={handleMouseLeave}
                onClick={handleClick}
                style={{
                  position: 'absolute',
                  top: 4,
                  right: 4,
                  cursor: 'pointer',
                }}
              >
                <Badge
                  leftSection={<IconPhoto size={12} />}
                  color={isPinned ? 'teal' : 'blue'}
                  variant="filled"
                  size="sm"
                >
                  Transcript
                </Badge>
              </Box>
            </Popover.Target>
            <Popover.Dropdown style={{ maxHeight: 400, overflowY: 'auto' }}>
              <Box>
                <Group justify="space-between" mb="xs">
                  <Text size="sm" fw={500}>
                    Image Transcript
                  </Text>
                  <Group gap="xs">
                    {hasTranslation && (
                      <Button
                        variant="subtle"
                        size="xs"
                        onClick={() => setShowOriginal(!showOriginal)}
                      >
                        {showOriginal ? 'DE' : 'Original'}
                      </Button>
                    )}
                    {isPinned && (
                      <Button
                        variant="subtle"
                        size="xs"
                        onClick={handleClose}
                      >
                        Close
                      </Button>
                    )}
                  </Group>
                </Group>
                <Textarea
                  value={showOriginal || !hasTranslation ? imageText : imageTextTranslated}
                  readOnly
                  autosize
                  minRows={3}
                  maxRows={15}
                  styles={{
                    input: {
                      fontSize: '0.875rem',
                      backgroundColor: 'var(--mantine-color-gray-0)',
                    },
                  }}
                />
              </Box>
            </Popover.Dropdown>
          </Popover>
        )}
      </Box>
    );
  };

  const AudioPlayer = ({ mediaPath, audioText, audioTextTranslated, audioTranscriptionStatus, messageId, mediaType }: any) => {
    const [opened, setOpened] = useState(false);
    const [isPinned, setIsPinned] = useState(false);
    const [showOriginal, setShowOriginal] = useState(false);
    const [isTriggering, setIsTriggering] = useState(false);

    const hasTranscript = audioText && audioText.trim().length > 0;
    const hasTranslation = audioTextTranslated && audioTextTranslated.trim().length > 0;
    const needsProcessing = audioTranscriptionStatus === 'none';
    const isProcessing = audioTranscriptionStatus === 'pending';

    const handleMouseEnter = () => {
      if (!isPinned) setOpened(true);
    };

    const handleMouseLeave = () => {
      if (!isPinned) setOpened(false);
    };

    const handleClick = () => {
      setIsPinned(!isPinned);
      setOpened(true);
    };

    const handleClose = () => {
      setIsPinned(false);
      setOpened(false);
    };

    const handleTriggerAudioTranscription = async () => {
      setIsTriggering(true);
      try {
        const response = await authFetch(`${apiUrl}/queue/audio-transcription`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message_id: messageId,
            media_path: mediaPath,
            media_type: mediaType || 'audio',
            translate_transcription: true,
          }),
        });

        if (!response.ok) {
          throw new Error('Failed to trigger audio transcription');
        }

        notifications.show({
          title: 'Success',
          message: 'Audio transcription job queued',
          color: 'green',
        });
      } catch (error: any) {
        notifications.show({
          title: 'Error',
          message: error.message || 'Failed to trigger audio transcription',
          color: 'red',
        });
      } finally {
        setIsTriggering(false);
      }
    };

    return (
      <Box style={{ position: 'relative', minWidth: 200 }}>
        <audio src={mediaPath} controls style={{ width: '100%', maxWidth: 300 }}>
          Your browser does not support the audio element.
        </audio>

        {showAudioTranscripts && needsProcessing && (
          <Box
            onClick={handleTriggerAudioTranscription}
            style={{
              position: 'absolute',
              top: -8,
              right: 4,
              cursor: 'pointer',
            }}
          >
            <Badge
              leftSection={<IconVolume size={12} />}
              color="orange"
              variant="filled"
              size="sm"
            >
              {isTriggering ? 'Starting...' : 'No Transcript'}
            </Badge>
          </Box>
        )}

        {showAudioTranscripts && isProcessing && (
          <Box
            style={{
              position: 'absolute',
              top: -8,
              right: 4,
            }}
          >
            <Badge
              leftSection={<IconVolume size={12} />}
              color="yellow"
              variant="filled"
              size="sm"
            >
              Processing...
            </Badge>
          </Box>
        )}

        {showAudioTranscripts && hasTranscript && (
          <Popover width={300} position="bottom" withArrow shadow="md" opened={opened} onChange={setOpened}>
            <Popover.Target>
              <Box
                onMouseEnter={handleMouseEnter}
                onMouseLeave={handleMouseLeave}
                onClick={handleClick}
                style={{
                  position: 'absolute',
                  top: -8,
                  right: 4,
                  cursor: 'pointer',
                }}
              >
                <Badge
                  leftSection={<IconVolume size={12} />}
                  color={isPinned ? 'teal' : 'grape'}
                  variant="filled"
                  size="sm"
                >
                  Transcript
                </Badge>
              </Box>
            </Popover.Target>
            <Popover.Dropdown style={{ maxHeight: 400, overflowY: 'auto' }}>
              <Box>
                <Group justify="space-between" mb="xs">
                  <Text size="sm" fw={500}>
                    Audio Transcript
                  </Text>
                  <Group gap="xs">
                    {hasTranslation && (
                      <Button
                        variant="subtle"
                        size="xs"
                        onClick={() => setShowOriginal(!showOriginal)}
                      >
                        {showOriginal ? 'DE' : 'Original'}
                      </Button>
                    )}
                    {isPinned && (
                      <Button
                        variant="subtle"
                        size="xs"
                        onClick={handleClose}
                      >
                        Close
                      </Button>
                    )}
                  </Group>
                </Group>
                <Textarea
                  value={showOriginal || !hasTranslation ? audioText : audioTextTranslated}
                  readOnly
                  autosize
                  minRows={3}
                  maxRows={15}
                  styles={{
                    input: {
                      fontSize: '0.875rem',
                      backgroundColor: 'var(--mantine-color-gray-0)',
                    },
                  }}
                />
              </Box>
            </Popover.Dropdown>
          </Popover>
        )}
      </Box>
    );
  };

  const VideoPlayer = ({ mediaPath, audioText, audioTextTranslated, audioTranscriptionStatus, messageId }: any) => {
    const [opened, setOpened] = useState(false);
    const [isPinned, setIsPinned] = useState(false);
    const [showOriginal, setShowOriginal] = useState(false);
    const [isTriggering, setIsTriggering] = useState(false);

    const hasTranscript = audioText && audioText.trim().length > 0;
    const hasTranslation = audioTextTranslated && audioTextTranslated.trim().length > 0;
    const needsProcessing = audioTranscriptionStatus === 'none';
    const isProcessing = audioTranscriptionStatus === 'pending';

    const handleMouseEnter = () => {
      if (!isPinned) setOpened(true);
    };

    const handleMouseLeave = () => {
      if (!isPinned) setOpened(false);
    };

    const handleClick = () => {
      setIsPinned(!isPinned);
      setOpened(true);
    };

    const handleClose = () => {
      setIsPinned(false);
      setOpened(false);
    };

    const handleTriggerAudioTranscription = async () => {
      setIsTriggering(true);
      try {
        const response = await authFetch(`${apiUrl}/queue/audio-transcription`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message_id: messageId,
            media_path: mediaPath,
            media_type: 'video',
            translate_transcription: true,
          }),
        });

        if (!response.ok) {
          throw new Error('Failed to trigger audio transcription');
        }

        notifications.show({
          title: 'Success',
          message: 'Video audio transcription job queued',
          color: 'green',
        });
      } catch (error: any) {
        notifications.show({
          title: 'Error',
          message: error.message || 'Failed to trigger audio transcription',
          color: 'red',
        });
      } finally {
        setIsTriggering(false);
      }
    };

    return (
      <Box style={{ position: 'relative', minWidth: 200 }}>
        <video src={mediaPath} className={classes.messageVideo} controls>
          Your browser does not support the video tag.
        </video>

        {showAudioTranscripts && needsProcessing && (
          <Box
            onClick={handleTriggerAudioTranscription}
            style={{
              position: 'absolute',
              top: 4,
              right: 4,
              cursor: 'pointer',
            }}
          >
            <Badge
              leftSection={<IconVolume size={12} />}
              color="orange"
              variant="filled"
              size="sm"
            >
              {isTriggering ? 'Starting...' : 'No Audio Transcript'}
            </Badge>
          </Box>
        )}

        {showAudioTranscripts && isProcessing && (
          <Box
            style={{
              position: 'absolute',
              top: 4,
              right: 4,
            }}
          >
            <Badge
              leftSection={<IconVolume size={12} />}
              color="yellow"
              variant="filled"
              size="sm"
            >
              Processing...
            </Badge>
          </Box>
        )}

        {showAudioTranscripts && hasTranscript && (
          <Popover width={300} position="bottom" withArrow shadow="md" opened={opened} onChange={setOpened}>
            <Popover.Target>
              <Box
                onMouseEnter={handleMouseEnter}
                onMouseLeave={handleMouseLeave}
                onClick={handleClick}
                style={{
                  position: 'absolute',
                  top: 4,
                  right: 4,
                  cursor: 'pointer',
                }}
              >
                <Badge
                  leftSection={<IconVolume size={12} />}
                  color={isPinned ? 'teal' : 'grape'}
                  variant="filled"
                  size="sm"
                >
                  Audio Transcript
                </Badge>
              </Box>
            </Popover.Target>
            <Popover.Dropdown style={{ maxHeight: 400, overflowY: 'auto' }}>
              <Box>
                <Group justify="space-between" mb="xs">
                  <Text size="sm" fw={500}>
                    Video Audio Transcript
                  </Text>
                  <Group gap="xs">
                    {hasTranslation && (
                      <Button
                        variant="subtle"
                        size="xs"
                        onClick={() => setShowOriginal(!showOriginal)}
                      >
                        {showOriginal ? 'DE' : 'Original'}
                      </Button>
                    )}
                    {isPinned && (
                      <Button
                        variant="subtle"
                        size="xs"
                        onClick={handleClose}
                      >
                        Close
                      </Button>
                    )}
                  </Group>
                </Group>
                <Textarea
                  value={showOriginal || !hasTranslation ? audioText : audioTextTranslated}
                  readOnly
                  autosize
                  minRows={3}
                  maxRows={15}
                  styles={{
                    input: {
                      fontSize: '0.875rem',
                      backgroundColor: 'var(--mantine-color-gray-0)',
                    },
                  }}
                />
              </Box>
            </Popover.Dropdown>
          </Popover>
        )}
      </Box>
    );
  };

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

        setMessages((prev) => {
          const combined = reset ? newMessages : [...prev, ...newMessages];
          const deduplicated = deduplicateMessages(combined);
          return deduplicated.sort(
            (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
          );
        });

        const newDates = { ...currentLastDates };
        results.forEach(({ channelId, messages }) => {
          const last = messages[messages.length - 1];
          if (last) {
            newDates[channelId] = last.date;
          }
        });
        setChannelLastDates(newDates);

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

  const handleRefresh = useCallback(() => {
    if (isRefreshing || selectedTgChannelIds.length === 0) {
      return;
    }

    setIsRefreshing(true);
    setMessages([]);
    setHasMore(true);
    setChannelLastDates(Object.fromEntries(selectedTgChannelIds.map((id) => [id, null])));

    loadMessages(true).finally(() => {
      setIsRefreshing(false);
    });
  }, [selectedTgChannelIds, loadMessages, isRefreshing]);

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

    const renderMedia = () => {
      if (!message.media_path) return null;

      if (isVideoFile(message.media_path)) {
        return (
          <VideoPlayer
            mediaPath={message.media_path}
            audioText={message.audio_text}
            audioTextTranslated={message.audio_text_translated}
            audioTranscriptionStatus={message.audio_transcription_status}
            messageId={message.message_id}
          />
        );
      } else if (isAudioFile(message.media_path)) {
        return (
          <AudioPlayer
            mediaPath={message.media_path}
            audioText={message.audio_text}
            audioTextTranslated={message.audio_text_translated}
            audioTranscriptionStatus={message.audio_transcription_status}
            messageId={message.message_id}
            mediaType={message.media_type}
          />
        );
      } else {
        return (
          <ImageWithTranscript
            mediaPath={message.media_path}
            imageText={message.image_text}
            imageTextTranslated={message.image_text_translated}
            imageAnalysisStatus={message.image_analysis_status}
            messageId={message.message_id}
          />
        );
      }
    };

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
                {(!message.channel?.username ||
                  message.author?.name.toLowerCase() !== message.channel.username.toLowerCase()) && (
                  <Anchor
                    onClick={() =>
                      message.author?.name && onUpdateGraph('user', message.author.name)
                    }
                  >
                    {message.author?.name || 'Unknown Author'}
                  </Anchor>
                )}
                <span
                  className={classes.channelName}
                  style={{
                    marginLeft:
                      !message.channel?.username ||
                      message.author?.name.toLowerCase() !==
                        message.channel.username.toLowerCase()
                        ? '0.25rem'
                        : 0,
                  }}
                >
                  [
                  <Anchor
                    onClick={() =>
                      message.channel?.username &&
                      onUpdateGraph('channel', message.channel.username)
                    }
                    className={classes.channelName}
                  >
                    {message.channel?.username || 'Unknown Channel'}
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
                searchQuery={searchQuery}
              />
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
        <Group gap="xs">
          <Switch
            label="Image transcripts"
            checked={showImageTranscripts}
            onChange={(e) => setShowImageTranscripts(e.currentTarget.checked)}
            size="sm"
          />
          <Switch
            label="Audio transcripts"
            checked={showAudioTranscripts}
            onChange={(e) => setShowAudioTranscripts(e.currentTarget.checked)}
            size="sm"
          />
          <Tooltip label="Refresh for new messages">
            <ActionIcon variant="light" size="lg" onClick={handleRefresh} loading={isRefreshing}>
              <IconRefresh size={18} />
            </ActionIcon>
          </Tooltip>
        </Group>
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