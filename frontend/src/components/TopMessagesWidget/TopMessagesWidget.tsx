import { useState, useEffect } from 'react';
import { Box, Title, Accordion, Text, Group, Button, Badge, Loader } from '@mantine/core';
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

interface Channel {
  channel_id: string;
  title: string;
  username: string;
  is_scraped: boolean | null;
  message_count: number;
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
  // Array for Accordion-Items
  const [openItems, setOpenItems] = useState<string[]>(['config']);

  //load Config
  useEffect(() => {
    // load config
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
          setSearchParams(prev => ({ ...prev, isActive: true }));
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
      isActive: false
    });
    setMessages([]);
    setOpenItems(['config']);
    
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
      // get channelInfo
      const base = apiUrl ?? 'http://localhost:8000/api';
      const channelInfoMap = new Map();
      
      try {
        // load & save channels
        const channelsRes = await authFetch(`${base}/messages/channels`);
        const channelsData = await channelsRes.json();
        
        channelsData.forEach((channel: any) => {
          channelInfoMap.set(channel.channel_id, {
            title: channel.title || channel.username || channel.channel_id
          });
        });
      } catch (error) {
        console.error("Error fetching channel information:", error);
      }

      // sort results per channel
      const resultsPerChannel = await Promise.all(
        searchParams.channelIds.map(async (channelId) => {
          try {
            const url = new URL(`${base}/messages/channels/${channelId}/messages`);
            // more messages to sort after
            url.searchParams.set('limit', '10');
            url.searchParams.set('q', searchParams.keywords.trim());
            
            console.log(`API-Anfrage für Channel ${channelId}:`, url.toString());
            
            const res = await authFetch(url.toString());
            const data = await res.json();
            
            console.log(`Ergebnis für Channel ${channelId}:`, data.length, "Nachrichten gefunden");
            
            return {
              channelId,
              messages: data.map((msg: any) => ({
                ...msg,
                channel_id: channelId,
                channel_title: channelInfoMap.get(channelId)?.title || channelId
              }))
            };
          } catch (error) {
            console.error(`Error fetching messages for channel ${channelId}:`, error);
            return { channelId, messages: [] };
          }
        })
      );
      
      // equality of messages
      let allMessages: Message[] = [];
      
      // case for one channel
      if (resultsPerChannel.length === 1) {
        allMessages = resultsPerChannel[0].messages
          .sort((a: any, b: any) => new Date(b.date).getTime() - new Date(a.date).getTime())
          .slice(0, 5);
      } 
      // case for more channels
      else if (resultsPerChannel.length > 1) {
        // sorting channels
        const sortedChannels = [...resultsPerChannel]
          .sort((a, b) => b.messages.length - a.messages.length);
        
        // how many messages per channel
        const totalChannels = sortedChannels.length;
        const totalMessages = 5;
        
        // messages for channel
        const messagesPerChannel: Record<string, number> = {};
        let remainingMessages = totalMessages;
        
        // only one message per channel
        sortedChannels.forEach(channel => {
          if (channel.messages.length > 0 && remainingMessages > 0) {
            messagesPerChannel[channel.channelId] = 1;
            remainingMessages--;
          } else {
            messagesPerChannel[channel.channelId] = 0;
          }
        });
        
        // sort messages for the rest
        while (remainingMessages > 0) {
          for (const channel of sortedChannels) {
            if (channel.messages.length > messagesPerChannel[channel.channelId] && remainingMessages > 0) {
              messagesPerChannel[channel.channelId]++;
              remainingMessages--;
            }
            if (remainingMessages === 0) {
              break;
            }
          }
          // no messages remaining
          if (remainingMessages === totalMessages) {
            break;
          }
        }
        
        console.log("Verteilung der Nachrichten pro Kanal:", messagesPerChannel);
        
        // final messages
        for (const channel of sortedChannels) {
          const count = messagesPerChannel[channel.channelId];
          if (count > 0) {
            // Nachrichten für diesen Kanal nach Datum sortieren
            const sortedMessages = channel.messages
              .sort((a: any, b: any) => new Date(b.date).getTime() - new Date(a.date).getTime())
              .slice(0, count);
            
            allMessages = [...allMessages, ...sortedMessages];
          }
        }
        
        // sort
        allMessages = allMessages.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
      }
      
      console.log("Insgesamt ausgewählte Nachrichten:", allMessages.length);
      setMessages(allMessages);
      
      // mark widget as active
      if (allMessages.length > 0) {
        setSearchParams(prev => ({ ...prev, isActive: true }));
        
        // save config
        localStorage.setItem('topMessagesConfig', JSON.stringify({
          ...searchParams,
          isActive: true
        }));
        localStorage.setItem('topMessagesResults', JSON.stringify(allMessages));
        
        // switch to messages-view
        setOpenItems(['messages']);
      } else {
        console.log("Keine Nachrichten gefunden. Widget bleibt inaktiv.");
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

  // Handler for AccordionChange
  const handleAccordionChange = (value: string[]) => {
    setOpenItems(value);
  };

  // Button Klick-Handler
  const handleConfigureClick = (e: React.MouseEvent) => {
    e.stopPropagation(); // stop
    
    // if config is open
    if (openItems.includes('config')) {
      return;
    }
    // else
    setOpenItems([...openItems, 'config']);
  };

  return (
    <Box className={classes.widget}>
      <Accordion 
        multiple 
        value={openItems} 
        onChange={handleAccordionChange}
      >
        <Accordion.Item value="config" className={searchParams.isActive ? classes.configAccordionItem : ''}>
          <Group justify="apart" className={classes.widgetHeader}>
            <Accordion.Control>
              <Title order={3} className={classes.title}>Top 5 Messages</Title>
            </Accordion.Control>
          </Group>
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
            <Group justify="apart" className={classes.widgetHeader}>
              <Accordion.Control>
                <Title order={3} className={classes.title}>{searchParams.label}</Title>
              </Accordion.Control>
              <Button
                onClick={handleConfigureClick}
                variant="subtle"
                size="xs"
                className={classes.configButton}
              >
                Settings
              </Button>
            </Group>
            <Accordion.Panel>
              {loading ? (
                <Loader size="sm" />
              ) : messages.length === 0 ? (
                <Text className={classes.noResults}>No messages found</Text>
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