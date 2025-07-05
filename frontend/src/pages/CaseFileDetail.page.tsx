import { useEffect, useState, useRef, useCallback, useLayoutEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Loader, Text, Title, Grid, Card, Tabs, Table, Checkbox, ScrollArea, Stack, Input, Button, Box } from '@mantine/core';
import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import classes from './CaseFileDetail.module.css';
import {
  IconDownload,
  IconMessage,
  IconEye,
  IconSearch,
} from '@tabler/icons-react';
import GraphVisualization from '@/components/GraphVisualization/GraphVisualization';
import TelegramScraper from '@/components/TelegramScraper';
import { authFetch } from '@/utils/authFetch';

const apiUrl = import.meta.env.VITE_API_URL;

export function CaseFileDetail() {
  const { id } = useParams<{ id: string }>();
  const [caseFile, setCaseFile] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const [tgChannels, setTgChannels] = useState<any[]>([]);
  const [selectedTgChannelIds, setSelectedTgChannelIds] = useState<string[]>([]);

  const [selectedRows, setSelectedRows] = useState<number[]>([]);

  const LIMIT = 10;
  const [messages, setMessages] = useState<any[]>([]);
  const [hasMore, setHasMore] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const [channelLastDates, setChannelLastDates] = useState<{ [channelId: string]: string | null }>({});
  const [expandedMessages, setExpandedMessages] = useState<Set<string>>(new Set());

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

  const toggleMessageExpansion = (messageId: string) => {
    setExpandedMessages(prev => {
      const newSet = new Set(prev);
      if (newSet.has(messageId)) {
        newSet.delete(messageId);
      } else {
        newSet.add(messageId);
      }
      return newSet;
    });
  };

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);  // Start loading
      try {
        const base = apiUrl ?? 'http://localhost:8000/api';
        const resCaseFile = await authFetch(`${base}/casefiles/${id}`);
        const caseFileData = await resCaseFile.json();
        setCaseFile(caseFileData);
  
        // ✅ STEP 1: Get case channels from PostgreSQL
        const initialChannels = caseFileData.tgchannels || [];
        
        if (initialChannels.length > 0) {
          try {
            // ✅ STEP 2: Expand channels using RECOMMENDS relationships
            const expandUrl = new URL(`${base}/messages/channels/expand`);
            expandUrl.searchParams.set('channel_usernames', initialChannels.join(','));
            const expandRes = await authFetch(expandUrl.toString());
            const expandedChannels = await expandRes.json();
            
            console.log(`[DEBUG] Expanded ${initialChannels.length} to ${expandedChannels.length} channels`);
            
            // ✅ STEP 3: Get channel details for expanded list
            // IMPORTANT: Only fetch if we have channels to fetch
            const channelsToFetch = expandedChannels.length > 0 ? expandedChannels : initialChannels;
            
            if (channelsToFetch.length > 0) {
              const channelsUrl = new URL(`${base}/messages/channels`);
              channelsUrl.searchParams.set('usernames', channelsToFetch.join(','));
              const channelsRes = await authFetch(channelsUrl.toString());
              const tgChannelsData = await channelsRes.json();
              
              // Handle case where channels exist in case but aren't scraped yet
              if (tgChannelsData.length === 0) {
                console.log('[INFO] Channels not yet scraped, showing placeholder data');
                // Create placeholder entries for unscraped channels
                const placeholderChannels = channelsToFetch.map((username: string) => ({
                  channel_id: `pending_${username}`,
                  username,
                  title: `${username} (pending scrape)`,
                  message_count: 0,
                  last_message_date: null,
                  is_scraped: false,
                  scraped_at: null,
                }));
                setTgChannels(placeholderChannels);
                setSelectedTgChannelIds([]);  // Don't select unscraped channels
              } else {
                setTgChannels(tgChannelsData);
                setSelectedTgChannelIds(tgChannelsData.map((c: any) => c.channel_id));
              }
            } else {
              // No channels found after expansion
              setTgChannels([]);
              setSelectedTgChannelIds([]);
            }
            
          } catch (expandError) {
            console.warn('Failed to expand channels, using initial list:', expandError);
            
            // Fallback: fetch details for initial channels only
            const channelsUrl = new URL(`${base}/messages/channels`);
            channelsUrl.searchParams.set('usernames', initialChannels.join(','));
            const channelsRes = await authFetch(channelsUrl.toString());
            const tgChannelsData = await channelsRes.json();
            
            // Handle empty response for unscraped channels
            if (tgChannelsData.length === 0) {
              const placeholderChannels = initialChannels.map((username: string) => ({
                channel_id: `pending_${username}`,
                username,
                title: `${username} (pending scrape)`,
                message_count: 0,
                last_message_date: null,
                is_scraped: false,
                scraped_at: null,
              }));
              setTgChannels(placeholderChannels);
              setSelectedTgChannelIds([]);
            } else {
              setTgChannels(tgChannelsData);
              setSelectedTgChannelIds(tgChannelsData.map((c: any) => c.channel_id));
            }
          }
        } else {
          // No channels in case
          setTgChannels([]);
          setSelectedTgChannelIds([]);
        }

        document.title = `${caseFileData.title} - Æther`; 
      } catch (error) {
        console.error('Error fetching case data:', error);
        // Handle error appropriately
      } finally {
        setLoading(false);  // Always stop loading
      }
    };
    
    fetchData();
  }, [id]);
  

  // Function to deduplicate messages based on message_id
  const deduplicateMessages = useCallback((messages: any[]) => {
    const seen = new Set();
    return messages.filter(msg => {
      if (seen.has(msg.message_id)) {
        return false;
      }
      seen.add(msg.message_id);
      return true;
    });
  }, []);

  const loadMessages = useCallback(async (reset: boolean = false) => {
    if (isLoadingMore && !reset) {return;}
    
    setIsLoadingMore(true);
    
    try {
      const base = apiUrl ?? 'http://localhost:8000/api';
      const currentLastDates = reset ? 
        Object.fromEntries(selectedTgChannelIds.map(id => [id, null])) : 
        channelLastDates;

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

      const newMessages = results.flatMap(r => r.messages);

      // Update messages with deduplication and proper sorting
      setMessages(prev => {
        const combined = reset ? newMessages : [...prev, ...newMessages];
        const deduplicated = deduplicateMessages(combined);
        // Sort the entire combined array to maintain proper chronological order
        return deduplicated.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
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
      const more = results.some(r => r.messages.length === LIMIT);
      setHasMore(more);

    } catch (error) {
      console.error('Error loading messages:', error);
    } finally {
      setIsLoadingMore(false);
    }
  }, [selectedTgChannelIds, searchQuery, channelLastDates, isLoadingMore, deduplicateMessages]);

  // Reset and load initial messages when channels or search query changes
  useEffect(() => {
    if (selectedTgChannelIds.length > 0) {
      setMessages([]);
      setHasMore(true);
      setChannelLastDates(Object.fromEntries(selectedTgChannelIds.map(id => [id, null])));
      loadMessages(true);
    }
  }, [selectedTgChannelIds, searchQuery]);

  const handleSearchSubmit = () => {
    setMessages([]);
    setHasMore(true);
    setChannelLastDates(Object.fromEntries(selectedTgChannelIds.map(id => [id, null])));
    loadMessages(true);
  };

  if (loading) {
    return <Loader />;
  }
  if (!caseFile) {
    return <Text>Case file not found.</Text>;
  }

  function highlightText(text: string, query: string) {
    if (!query) { return text; }

    const regex = new RegExp(`(${query})`, 'gi');
    const parts = text.split(regex);

    return parts.map((part, index) =>
      regex.test(part) ? <mark key={index}>{part}</mark> : part
    );
  }

  const isVideoFile = (path: string): boolean => {
    const videoExtensions: string[] = ['.mp4', '.webm', '.ogg', '.avi', '.mov', '.wmv', '.flv', '.mkv'];
    return videoExtensions.some((ext: string) => path.toLowerCase().endsWith(ext));
  };

  const updateCaseWithDiscoveredChannels = async () => {
    if (!caseFile?.tgchannels?.length) {return;}
  
    try {
      const base = apiUrl ?? 'http://localhost:8000/api';
      
      // Get expanded channels using RECOMMENDS
      const expandUrl = new URL(`${base}/messages/channels/expand`);
      expandUrl.searchParams.set('channel_usernames', caseFile.tgchannels.join(','));
      
      const expandRes = await authFetch(expandUrl.toString());
      const expandedChannels = await expandRes.json();
      
      // Check if we discovered new channels
      const originalChannels = new Set(caseFile.tgchannels);
      const newChannels = expandedChannels.filter((ch: string) => !originalChannels.has(ch));
      
      if (newChannels.length > 0) {
        console.log(`[DISCOVERY] Found ${newChannels.length} new channels:`, newChannels);
        
        // Add new channels to case
        const addChannelsRes = await authFetch(`${base}/casefiles/${id}/add-channels`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(newChannels)
        });
        
        if (addChannelsRes.ok) {
          const result = await addChannelsRes.json();
          alert(`Discovered ${result.added_channels.length} new channels: ${result.added_channels.join(', ')}`);
          window.location.reload();
        }
      } else {
        alert('No new channels found');
      }
      
    } catch (error) {
      console.error('Error updating case with discoveries:', error);
      alert('Error checking for new channels');
    }
  };

  // Component for individual message content with measurement
  const MessageContent = ({ message, isExpanded, onToggleExpand }: { 
    message: any, 
    isExpanded: boolean, 
    onToggleExpand: () => void 
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

  const messageRows = messages.map((message) => {
    const isExpanded = expandedMessages.has(message.message_id);

    return (
      <Table.Tr
        key={message.message_id}
        bg={selectedRows.includes(message.message_id) ? 'var(--mantine-color-blue-light)' : undefined}
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
                {message.author.name} <span className={classes.channelName}>
                  [{message.channel.username}]
                </span>
              </Text>
              <Text size="xs" className={classes.timestamp}>
                {formatRelativeTime(message.date)}
              </Text>
            </div>
            <MessageContent
              message={message}
              isExpanded={isExpanded}
              onToggleExpand={() => toggleMessageExpansion(message.message_id)}
            />
            {message.media_path && (
              isVideoFile(message.media_path) ? (
                // eslint-disable-next-line jsx-a11y/media-has-caption
                <video
                  src={message.media_path} 
                  className={classes.messageVideo}
                  controls
                >
                  Your browser does not support the video tag.
                </video>
              ) : (
                <img 
                  src={message.media_path} 
                  alt={message.media_path} 
                  className={classes.messageImage} 
                />
              )
            )}
          </Box>
        </Table.Td>
      </Table.Tr>
    );
  });

  const tgChannelsCheckboxes = tgChannels.map((channel: any) => (
    <Checkbox
      key={channel.channel_id}
      label={channel.username}
      checked={selectedTgChannelIds.includes(channel.channel_id)}
      onChange={(event) => {
        const checked = event.currentTarget.checked;
        setSelectedTgChannelIds((current) =>
          checked
            ? [...current, channel.channel_id]
            : current.filter((id) => id !== channel.channel_id)
        );
      }}
    />
  ));

  return (
    <div>
      <BreadcrumbsBar overrides={{ [`/cases/${caseFile.id}`]: caseFile.title }} />
      <Title mb="xl">{caseFile.title}</Title>

      <Grid>
        <Grid.Col span={3}>
          <Grid>
            <Grid.Col>
              <Card withBorder p="xl" radius="md" className={classes.card}>
                <div className={classes.inner}>
                  <Stack>
                    <Text>Telegram Channels:</Text>
                    {tgChannelsCheckboxes}
                  </Stack>
                </div>
              </Card>
            </Grid.Col>
          </Grid>
        </Grid.Col>
        <Grid.Col span={9}>
          <Card withBorder radius="md" className={classes.card}>
            <div className={classes.inner}>
              <Tabs defaultValue="messages" w="100%">
                <Tabs.List>
                  <Tabs.Tab value="messages" leftSection={<IconMessage size={12} />}>
                    Messages
                  </Tabs.Tab>
                  <Tabs.Tab value="scraper" leftSection={<IconDownload size={12} />}>
                    Scraper
                  </Tabs.Tab>
                  <Tabs.Tab value="visuals" leftSection={<IconEye size={12} />}>
                    Graph
                  </Tabs.Tab>
                </Tabs.List>

                <Tabs.Panel value="messages" mt="md">
                  <Input placeholder="Search messages..." 
                    value={searchQuery} 
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        handleSearchSubmit();
                      }
                    }} 
                    leftSection={<IconSearch size={16} />}
                    mb="md" />

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
                    <Table>
                      <Table.Thead>
                        <Table.Tr>
                          <Table.Th className={classes.checkboxColumn}>
                            <Checkbox
                              aria-label="Select all messages"
                              checked={messages.length > 0 && selectedRows.length === messages.length}
                              indeterminate={selectedRows.length > 0 && selectedRows.length < messages.length}
                              onChange={(event) => {
                                if (event.currentTarget.checked) {
                                  setSelectedRows(messages.map(msg => msg.message_id));
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
                </Tabs.Panel>

                <Tabs.Panel value="scraper" mt="md">
                  <Stack gap="md">
                    <Card withBorder p="md">
                      <Stack gap="xs">
                        <Title order={4}>Channel Discovery</Title>
                        <Text size="sm" c="dimmed">
                          Check for new channels discovered through scraping
                        </Text>
                        <Button 
                          onClick={updateCaseWithDiscoveredChannels}
                          variant="outline"
                        >
                          Check for New Channels
                        </Button>
                      </Stack>
                    </Card>
                    <TelegramScraper case_id={parseInt(id!, 10)} />
                  </Stack>
                </Tabs.Panel>

                <Tabs.Panel value="visuals" mt="md">
                  <GraphVisualization 
                    selectedChannelIds={selectedTgChannelIds}
                    searchQuery={searchQuery}
                  />
                </Tabs.Panel>
              </Tabs>
            </div>
          </Card>
        </Grid.Col>
      </Grid>
    </div>
  );
}