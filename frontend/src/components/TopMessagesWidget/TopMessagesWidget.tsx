import { useState, useEffect } from 'react';
import { Box, Title, Accordion, Text, Group, Button, Badge, Loader, Divider, ActionIcon } from '@mantine/core';
import { IconSettings, IconBrandTelegram } from '@tabler/icons-react';
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
    return `${text.substring(0, MAX_TEXT_LENGTH)  }...`;
  };

  // toggle message
  const toggleMessageExpansion = (messageId: string) => {
    setExpandedMessages(prev => 
      prev.includes(messageId) 
        ? prev.filter(id => id !== messageId) 
        : [...prev, messageId]
    );
  };

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
      setExpandedMessages([]); // Reset expanded messages
      
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

  // Kopen config
  const openConfig = () => {
    if (!openItems.includes('config')) {
      setOpenItems([...openItems, 'config']);
    }
  };

  return (
    <Box className={classes.widget}>
      <Group justify="apart" className={classes.widgetHeader}>
        <Title order={3} className={classes.title}>
          {searchParams.isActive ? searchParams.label : 'Top Messages'}
        </Title>
        <ActionIcon 
          variant="subtle" 
          color="gray" 
          onClick={openConfig}
          className={classes.settingsButton}
        >
          <IconSettings size={18} />
        </ActionIcon>
      </Group>

      <Accordion 
        multiple 
        value={openItems} 
        onChange={handleAccordionChange}
      >
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
                        <Group justify="apart" className={classes.messageHeader}>
                          <Badge color="blue" radius="sm">{message.channel_title || message.channel_id}</Badge>
                          <Group gap="xs">
                            <Text size="xs" color="dimmed">{formatRelativeTime(message.date)}</Text>
                            <IconBrandTelegram size={16} className={classes.telegramIcon} />
                          </Group>
                        </Group>
                        <div className={classes.messageContent}>
                          <Text className={classes.messageText}>
                            {expandedMessages.includes(message.message_id) 
                              ? highlightText(message.text, searchParams.keywords)
                              : highlightText(truncateText(message.text), searchParams.keywords)}
                          </Text>
                          {shouldTruncateText(message.text) && (
                            <Button 
                              variant="subtle"
                              onClick={() => toggleMessageExpansion(message.message_id)}
                              className={classes.showMoreButton}
                            >
                              {expandedMessages.includes(message.message_id) ? "Show less" : "Show more"}
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