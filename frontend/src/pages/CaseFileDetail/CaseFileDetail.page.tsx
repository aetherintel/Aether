import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Loader, Text, Title, Grid, Card, Tabs, Stack } from '@mantine/core';
import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import classes from './CaseFileDetail.module.css';
import {
  IconUsersGroup,
  IconMessage,
  IconEye,
} from '@tabler/icons-react';
import GraphVisualization from '@/components/GraphVisualization/GraphVisualization';
import MessagesTab from '@/components/MessagesTab/MessagesTab';
import TgChannelsCheckboxList from '@/components/TgChannelsCheckboxList';
import ChannelsTab from '@/components/ChannelsTab';
import { authFetch } from '@/utils/authFetch';
import type { Channel, GroupedChannelStructure, OutputChannelStructure, OutputChannelEntry } from '../../types/caseFileDetail';

const apiUrl = import.meta.env.VITE_API_URL;

export function CaseFileDetail() {
  const { id } = useParams<{ id: string }>();
  const [caseFile, setCaseFile] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const [searchQuery, setSearchQuery] = useState('');

  const [tgChannels, setTgChannels] = useState<any>([]);
  const [selectedTgChannelIds, setSelectedTgChannelIds] = useState<string[]>([]);

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

        /*const channelsUrl = new URL(`${base}/messages/channels`);
        channelsUrl.searchParams.set('usernames', initialChannels.join(','));
        const channelsRes = await authFetch(channelsUrl.toString());
        const tgChannelsData = await channelsRes.json();*/
        
        if (initialChannels.length > 0) {
          try {
            // ✅ STEP 2: Expand channels using RECOMMENDS relationships
            const expandUrl = new URL(`${base}/messages/channels/expand`);
            expandUrl.searchParams.set('channel_usernames', initialChannels.join(','));
            const expandRes = await authFetch(expandUrl.toString());
            const expandedChannels = await expandRes.json();

            const uniqueChannels = [...new Set(
              // @ts-ignore
              Object.entries(expandedChannels).flatMap(([key, recommendations]) => [key, ...recommendations]).map(item => item.toLowerCase())
            )];
            
            console.log(`[DEBUG] Expanded ${initialChannels.length} to ${expandedChannels.length} channels`);
            
            // ✅ STEP 3: Get channel details for expanded list
            // IMPORTANT: Only fetch if we have channels to fetch
            //const channelsToFetch = expandedChannels.length > 0 ? expandedChannels : initialChannels;
            
            const channelsUrl = new URL(`${base}/messages/channels`);
            channelsUrl.searchParams.set('usernames', uniqueChannels.join(','));
            const channelsRes = await authFetch(channelsUrl.toString());
            const tgChannelsData = await channelsRes.json();

            const mergedChannelsData = transformChannelData(tgChannelsData, expandedChannels);

            setTgChannels(mergedChannelsData);
            setSelectedTgChannelIds(tgChannelsData.map((c: any) => c.channel_id));

            /*if (channelsToFetch.length > 0) {
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
                console.log(tgChannelsData);
                setTgChannels(tgChannelsData);
                setSelectedTgChannelIds(tgChannelsData.map((c: any) => c.channel_id));
              }
            } else {
              // No channels found after expansion
              setTgChannels([]);
              setSelectedTgChannelIds([]);
            }*/
            
          } catch (expandError) {
            console.warn('Failed to expand channels, using initial list:', expandError);
            
            // Fallback: fetch details for initial channels only
            /*const channelsUrl = new URL(`${base}/messages/channels`);
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
            }*/
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

  function transformChannelData(
    channelData: Channel[],
    groupedStructure: GroupedChannelStructure
  ): OutputChannelStructure {
    // Create a case-insensitive map from username to channel
    const channelMap = new Map<string, Channel>(
      channelData.map((c) => [c.username.toLowerCase(), c])
    );

    const result: OutputChannelStructure = {};

    for (const [groupKey, recommendedUsernames] of Object.entries(groupedStructure)) {
      const groupChannel = channelMap.get(groupKey.toLowerCase()) || null;

      const recommended: Record<string, { channel: Channel }> = {};
      for (const recUsername of recommendedUsernames) {
        const recChannel = channelMap.get(recUsername.toLowerCase());
        if (recChannel) {
          recommended[recUsername] = { channel: recChannel };
        }
      }

      result[groupKey] = {
        channel: groupChannel,
        recommended,
      };
    }

    return result;
  }

  const structuredChannels = Object.entries(tgChannels) as [string, OutputChannelEntry][];

  if (loading) {
    return <Loader />;
  }
  if (!caseFile) {
    return <Text>Case file not found.</Text>;
  }

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
                    <TgChannelsCheckboxList structuredChannels={structuredChannels} selectedTgChannelIds={selectedTgChannelIds} setSelectedTgChannelIds={setSelectedTgChannelIds} />
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
                  <Tabs.Tab value="messages" leftSection={<IconMessage size={16} />}>
                    Messages
                  </Tabs.Tab>
                  <Tabs.Tab value="scraper" leftSection={<IconUsersGroup size={16} />}>
                    Channels
                  </Tabs.Tab>
                  <Tabs.Tab value="visuals" leftSection={<IconEye size={16} />}>
                    Graph
                  </Tabs.Tab>
                </Tabs.List>

                <Tabs.Panel value="messages" mt="md">
                  <MessagesTab selectedTgChannelIds={selectedTgChannelIds} searchQuery={searchQuery} setSearchQuery={setSearchQuery} />
                </Tabs.Panel>

                <Tabs.Panel value="scraper" mt="md">
                  <ChannelsTab caseId={id!} caseFile={caseFile} structuredChannels={structuredChannels} />
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