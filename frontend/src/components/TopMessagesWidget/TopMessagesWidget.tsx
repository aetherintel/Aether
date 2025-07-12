import { useState, useEffect } from 'react';
import { Box, Title, Accordion, Text, Group, Button, Badge, Loader } from '@mantine/core';
import { IconChevronRight, IconMessage } from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import { authFetch } from '@/utils/authFetch';
import { TopMessagesForm } from './TopMessagesForm';
import classes from './TopMessagesWidget.module.css';

const apiUrl = import.meta.env.VITE_API_URL;

interface Message {
  message_id: string;
  channel_id: string;
  text: string;
  date: string;
  channel_title?: string;
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
    isActive: false
  });
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [configOpen, setConfigOpen] = useState(true);

  const fetchTopMessages = async () => {
    if (!searchParams.channelIds.length || !searchParams.keywords) {
      return;
    }

    setLoading(true);
    try {
      const results = await Promise.all(
        searchParams.channelIds.map(async (channelId) => {
          const base = apiUrl ?? 'http://localhost:8000/api';
          const url = new URL(`${base}/messages/channels/${channelId}/messages`);
          url.searchParams.set('limit', '5');
          url.searchParams.set('q', searchParams.keywords);

          const res = await authFetch(url.toString());
          const data = await res.json();
          return data.map((msg: any) => ({
            ...msg,
            channel_id: channelId
          }));
        })
      );

      // Alle Nachrichten kombinieren, sortieren und auf die Top 5 begrenzen
      const allMessages = results.flat();
      const sortedMessages = allMessages
        .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
        .slice(0, 5);

      setMessages(sortedMessages);

      // Widget als aktiv markieren, wenn Nachrichten gefunden wurden
      if (sortedMessages.length > 0) {
        setSearchParams(prev => ({ ...prev, isActive: true }));
        setConfigOpen(false); // Konfigurationsbereich schließen
      }
    } catch (error) {
      console.error('Error fetching top messages:', error);
    } finally {
      setLoading(false);
    }
  };

  // Formatierung des relativen Zeitstempels
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

  // Hervorhebung der Suchbegriffe im Text
  const highlightText = (text: string, query: string) => {
    if (!query) {return text;}

    const keywords = query.split(' ').filter(k => k.length > 0);
    const regex = new RegExp(`(${keywords.join('|')})`, 'gi');
    const parts = text.split(regex);

    return parts.map((part, index) =>
      regex.test(part) ? <mark key={index}>{part}</mark> : part
    );
  };

  return (
    <Box className={classes.widget}>
      <Accordion
        value={configOpen ? 'config' : 'messages'}
        onChange={(value) => setConfigOpen(value === 'config')}
      >
        <Accordion.Item value="config">
          <Group justify="apart" className={classes.widgetHeader}>
            <Accordion.Control>
              <Title order={3} className={classes.title}>Nachrichten-Suche konfigurieren</Title>
            </Accordion.Control>
          </Group>
          <Accordion.Panel>
            <TopMessagesForm
              searchParams={searchParams}
              setSearchParams={setSearchParams}
              onSearch={fetchTopMessages}
            />
          </Accordion.Panel>
        </Accordion.Item>

        {searchParams.isActive && (
          <Accordion.Item value="messages">
            <Group justify="apart" className={classes.widgetHeader}>
              <Accordion.Control>
                <Title order={3} className={classes.title}>{searchParams.label}</Title>
              </Accordion.Control>
              <Button
                onClick={() => setConfigOpen(true)}
                variant="subtle"
                size="xs"
                className={classes.configButton}
              >
                Konfigurieren
              </Button>
            </Group>
            <Accordion.Panel>
              {loading ? (
                <Loader size="sm" />
              ) : messages.length === 0 ? (
                <Text className={classes.noResults}>Keine Nachrichten gefunden</Text>
              ) : (
                <div className={classes.messagesList}>
                  {messages.map((message) => (
                    <div key={message.message_id} className={classes.messageItem}>
                      <Group justify="apart" className={classes.messageHeader}>
                        <Badge color="blue" radius="sm">{message.channel_title || message.channel_id}</Badge>
                        <Text size="xs" color="dimmed">{formatRelativeTime(message.date)}</Text>
                      </Group>
                      <Text className={classes.messageText}>
                        {highlightText(message.text, searchParams.keywords)}
                      </Text>
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