import { useEffect, useState } from 'react';
import { IconBrandTelegram, IconSettings } from '@tabler/icons-react';
import {
  Accordion,
  ActionIcon,
  Anchor,
  Badge,
  Box,
  Button,
  Divider,
  Group,
  Loader,
  Text,
  Title,
} from '@mantine/core';
import { authFetch } from '@/utils/authFetch';
import { TopMessagesForm } from './TopMessagesForm';
import classes from './TopMessagesWidget.module.css';

const apiUrl = import.meta.env.VITE_API_URL;

interface Author {
  id: string;
  name: string;
}

interface ChannelInfo {
  id?: string;
  username?: string;
  title?: string;
}

interface Message {
  message_id: string;
  channel_id: string;

  // new backend fields
  original_text?: string;
  translated_text?: string | null;
  original_language?: string;
  translation_status?: string;

  // widget uses this as the "display text" (filled from above)
  text: string;

  date: string;
  channel_title?: string;
  author?: Author;
  channel?: ChannelInfo;

  // keep any other properties from the backend
  [key: string]: any;
}

interface SearchParams {
  label: string;
  channelIds: string[];
  keywords: string;
  isActive: boolean;
}

export function TopMessagesWidget() {
  const [searchParams, setSearchParams] = useState<SearchParams>({
    label: 'Top 5 Messages',
    channelIds: [],
    keywords: '',
    isActive: false,
  });
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [openItems, setOpenItems] = useState<string[]>(['config']);
  const [expandedMessages, setExpandedMessages] = useState<string[]>([]);

  const MAX_TEXT_LENGTH = 150;

  // check text length
  const shouldTruncateText = (text: string) => text.length > MAX_TEXT_LENGTH;

  // trim text
  const truncateText = (text: string) => {
    if (!shouldTruncateText(text)) {
      return text;
    }
    return `${text.substring(0, MAX_TEXT_LENGTH)}...`;
  };

  // toggle message
  const toggleMessageExpansion = (messageId: string) => {
    setExpandedMessages((prev) =>
      prev.includes(messageId) ? prev.filter((id) => id !== messageId) : [...prev, messageId]
    );
  };

  // load Config
  useEffect(() => {
    const savedConfig = localStorage.getItem('topMessagesConfig');
    if (savedConfig) {
      try {
        const config = JSON.parse(savedConfig);
        setSearchParams(config);
      } catch (e) {
        console.error('Error loading saved config:', e);
      }
    }

    // load messages
    const savedMessages = localStorage.getItem('topMessagesResults');
    if (savedMessages) {
      try {
        const msgData = JSON.parse(savedMessages);
        setMessages(msgData);
        // check if messages are available
        if (msgData.length > 0) {
          setSearchParams((prev) => ({ ...prev, isActive: true }));
          // open Messages-Accordion
          setOpenItems(['messages']);
        }
      } catch (e) {
        console.error('Error loading saved messages:', e);
      }
    }
  }, []);

  const resetWidget = () => {
    setSearchParams({
      label: 'Top 5 Messages',
      channelIds: [],
      keywords: '',
      isActive: false,
    });
    setMessages([]);
    setOpenItems(['config']);
    setExpandedMessages([]);

    // delete saved data
    localStorage.removeItem('topMessagesConfig');
    localStorage.removeItem('topMessagesResults');
  };

  const fetchTopMessages = async () => {
    if (!searchParams.channelIds.length || !searchParams.keywords) {
      return;
    }

    setLoading(true);
    try {
      const base = apiUrl ?? 'http://localhost:8000/api';
      const channelInfoMap = new Map<string, { title: string }>();

      // Load channel info (titles)
      try {
        const channelsRes = await authFetch(`${base}/messages/channels`);
        const channelsData = await channelsRes.json();

        channelsData.forEach((channel: any) => {
          channelInfoMap.set(channel.channel_id, {
            title: channel.title || channel.username || channel.channel_id,
          });
        });
      } catch (error) {
        console.error('Error fetching channel information:', error);
      }

      const resultsPerChannel = await Promise.all(
        searchParams.channelIds.map(async (channelId) => {
          try {
            const url = new URL(`${base}/messages/channels/${channelId}/messages`);
            url.searchParams.set('limit', '10');
            url.searchParams.set('q', searchParams.keywords.trim());

            const res = await authFetch(url.toString());
            const data = await res.json();

            const channelTitleFromMap = channelInfoMap.get(channelId)?.title;

            const mappedMessages: Message[] = data.map((msg: any) => {
              const channelTitle =
                channelTitleFromMap ||
                msg.channel?.title ||
                msg.channel?.username ||
                channelId;

              const translated = (msg.translated_text || '').trim();
              const original = (msg.original_text || '').trim();
              const fallback = (msg.text || '').trim();

              const finalText = translated || original || fallback || '';

              return {
                ...msg,
                channel_id: channelId,
                channel_title: channelTitle,
                text: finalText,
              };
            });

            return {
              channelId,
              messages: mappedMessages,
            };
          } catch (error) {
            console.error(`Error fetching messages for channel ${channelId}:`, error);
            return { channelId, messages: [] as Message[] };
          }
        })
      );

      let allMessages: Message[] = [];

      // case for one channel
      if (resultsPerChannel.length === 1) {
        allMessages = resultsPerChannel[0].messages
          .sort((a: any, b: any) => new Date(b.date).getTime() - new Date(a.date).getTime())
          .slice(0, 5);
      }
      // case for more channels
      else if (resultsPerChannel.length > 1) {
        const sortedChannels = [...resultsPerChannel].sort(
          (a, b) => b.messages.length - a.messages.length
        );

        const totalMessages = 5;
        const messagesPerChannel: Record<string, number> = {};
        let remainingMessages = totalMessages;

        // one message for each channel
        sortedChannels.forEach((channel) => {
          if (channel.messages.length > 0 && remainingMessages > 0) {
            messagesPerChannel[channel.channelId] = 1;
            remainingMessages--;
          } else {
            messagesPerChannel[channel.channelId] = 0;
          }
        });

        // distribute remaining messages
        while (remainingMessages > 0) {
          let distributed = false;
          for (const channel of sortedChannels) {
            if (
              channel.messages.length > messagesPerChannel[channel.channelId] &&
              remainingMessages > 0
            ) {
              messagesPerChannel[channel.channelId]++;
              remainingMessages--;
              distributed = true;
            }
          }
          // no more messages to distribute
          if (!distributed) {
            break;
          }
        }

        // final messages
        for (const channel of sortedChannels) {
          const count = messagesPerChannel[channel.channelId];
          if (count > 0) {
            const sortedMessages = channel.messages
              .sort((a: any, b: any) => new Date(b.date).getTime() - new Date(a.date).getTime())
              .slice(0, count);

            allMessages = [...allMessages, ...sortedMessages];
          }
        }

        // sort
        allMessages = allMessages.sort(
          (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
        );
      }

      setMessages(allMessages);
      setExpandedMessages([]);

      // mark widget as active
      if (allMessages.length > 0) {
        setSearchParams((prev) => ({ ...prev, isActive: true }));

        localStorage.setItem(
          'topMessagesConfig',
          JSON.stringify({
            ...searchParams,
            isActive: true,
          })
        );
        localStorage.setItem('topMessagesResults', JSON.stringify(allMessages));

        setOpenItems(['messages']);
      }
    } catch (error) {
      console.error('Error fetching top messages:', error);
    } finally {
      setLoading(false);
    }
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

  // --- highlighting logic from MessagesTab (URL-aware) ---
  function escapeRegExp(str: string) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function highlightText(text: string, query: string) {
    const urlRegex = /https?:\/\/[^\s]+/gi;
    const queryTrimmed = query.trim();
    const queryRegex = queryTrimmed
      ? new RegExp(`(${escapeRegExp(queryTrimmed)})`, 'gi')
      : null;

    const urlParts = text.split(urlRegex);
    const urls = text.match(urlRegex);
    const result: React.ReactNode[] = [];

    urlParts.forEach((part, i) => {
      if (queryRegex) {
        const highlighted = part
          .split(queryRegex)
          .map((p, idx) =>
            queryRegex.test(p) ? (
              <mark key={`highlight-${i}-${idx}`} className={classes.highlight}>
                {p}
              </mark>
            ) : (
              p
            )
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
              queryRegex.test(p) ? (
                <mark key={`link-highlight-${i}-${idx}`} className={classes.highlight}>
                  {p}
                </mark>
              ) : (
                p
              )
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
              fz="xs"
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

  // toggle-function for config
  const toggleConfig = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (openItems.includes('config')) {
      setOpenItems(openItems.filter((item) => item !== 'config'));
    } else {
      setOpenItems([...openItems, 'config']);
    }
  };

  return (
    <Box className={classes.widget}>
      <Group justify="space-between" className={classes.widgetHeader}>
        <Title order={3} className={classes.title}>
          {searchParams.isActive ? searchParams.label : 'Top Messages'}
        </Title>
        <ActionIcon
          variant="subtle"
          color="gray"
          onClick={toggleConfig}
          className={classes.settingsButton}
        >
          <IconSettings size={18} />
        </ActionIcon>
      </Group>

      <Accordion multiple value={openItems} onChange={setOpenItems}>
        <Accordion.Item value="config" className={classes.configAccordionItem}>
          <Accordion.Control className={classes.hiddenControl}>
            <span style={{ display: 'none' }}>Configuration</span>
          </Accordion.Control>
          <Accordion.Panel>
            <TopMessagesForm
              searchParams={searchParams}
              setSearchParams={setSearchParams}
              onSearch={fetchTopMessages}
              onReset={resetWidget}
            />
          </Accordion.Panel>
        </Accordion.Item>

        {searchParams.isActive && (
          <Accordion.Item value="messages" className={classes.messagesAccordionItem}>
            <Accordion.Control className={classes.hiddenControl}>
              <span style={{ display: 'none' }}>Messages</span>
            </Accordion.Control>
            <Accordion.Panel>
              {loading ? (
                <Loader size="sm" />
              ) : messages.length === 0 ? (
                <Text className={classes.noResults}>No messages found</Text>
              ) : (
                <div className={classes.messagesList}>
                  {messages.map((message, index) => (
                    <div key={message.message_id}>
                      <div className={classes.messageItem}>
                        <div className={classes.messageHeader}>
                          <Group
                            justify="space-between"
                            className={classes.messageHeaderInner}
                            wrap="nowrap"
                          >
                            <Group gap="xs" wrap="nowrap">
                              <Badge color="blue" radius="sm">
                                {message.channel_title ||
                                  message.channel?.username ||
                                  message.channel?.title ||
                                  message.channel_id}
                              </Badge>
                              {message.author && (
                                <Text size="xs" c="dimmed" className={classes.authorName}>
                                  {message.author.name}
                                </Text>
                              )}
                            </Group>
                            <Group gap="xs" className={classes.dateGroup} wrap="nowrap">
                              <Text size="xs" c="dimmed" className={classes.dateText}>
                                {formatRelativeTime(message.date)}
                              </Text>
                              <IconBrandTelegram size={16} className={classes.telegramIcon} />
                            </Group>
                          </Group>
                        </div>
                        <div className={classes.messageContent}>
                          <Text className={classes.messageText}>
                            {expandedMessages.includes(message.message_id)
                              ? highlightText(message.text, searchParams.keywords)
                              : highlightText(
                                  truncateText(message.text),
                                  searchParams.keywords
                                )}
                          </Text>
                          {shouldTruncateText(message.text) && (
                            <Button
                              variant="subtle"
                              onClick={() => toggleMessageExpansion(message.message_id)}
                              className={classes.showMoreButton}
                            >
                              {expandedMessages.includes(message.message_id)
                                ? 'Weniger anzeigen'
                                : 'Mehr anzeigen'}
                            </Button>
                          )}
                        </div>
                      </div>
                      {index < messages.length - 1 && <Divider my="sm" />}
                    </div>
                  ))}
                </div>
              )}
            </Accordion.Panel>
          </Accordion.Item>
        )}
      </Accordion>
    </Box>
  );
}
