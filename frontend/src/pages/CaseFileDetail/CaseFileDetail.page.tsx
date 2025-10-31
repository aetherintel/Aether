import { useEffect, useState } from 'react';
import { IconEye, IconInfoCircle, IconMessage, IconUsersGroup } from '@tabler/icons-react';
import { useParams } from 'react-router-dom';
import { Badge, Card, Grid, Group, Loader, Stack, Tabs, Text, Title } from '@mantine/core';
import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import ChannelsTab from '@/components/ChannelsTab';
import GraphVisualization from '@/components/GraphVisualization/GraphVisualization';
import MessagesTab from '@/components/MessagesTab/MessagesTab';
import TgChannelsCheckboxList from '@/components/TgChannelsCheckboxList';
import { authFetch } from '@/utils/authFetch';
import type {
  Channel,
  GroupedChannelStructure,
  OutputChannelEntry,
  OutputChannelStructure,
} from '../../types/caseFileDetail';
import classes from './CaseFileDetail.module.css';

const apiUrl = import.meta.env.VITE_API_URL;
type ExpandedChannels = Record<string, string[]>;

export function CaseFileDetail() {
  const { id } = useParams<{ id: string }>();
  const [caseFile, setCaseFile] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<string | null>('messages'); // Add tab state

  const [graphUser, setGraphUser] = useState<string | null>(null);
  const [graphType, setGraphType] = useState<string | null>(null);

  const [tgChannels, setTgChannels] = useState<any>([]);
  const [selectedTgChannelIds, setSelectedTgChannelIds] = useState<string[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true); // Start loading
      try {
        const base = apiUrl ?? 'http://localhost:8000/api';
        const resCaseFile = await authFetch(`${base}/casefiles/${id}`);
        const caseFileData = await resCaseFile.json();
        setCaseFile(caseFileData);

        console.log(caseFileData);

        const initialChannels = caseFileData.tgchannels || [];


        if (initialChannels.length > 0) {
          try {
            const expandUrl = new URL(`${base}/messages/channels/expand`);
            expandUrl.searchParams.set('channel_usernames', initialChannels.join(','));
            const expandRes = await authFetch(expandUrl.toString());
            const expandedChannels: ExpandedChannels = await expandRes.json();

            console.log('initial channels:', initialChannels);
            const uniqueChannels = [
            ...new Set(
              Object.entries(expandedChannels)
                .flatMap(([key, recommendations]) => {
                  const cleanKey = key.replace(/^"+|"+$/g, '').replace(/"/g, '');
                  const cleanRecs = (recommendations || []).map((r) =>
                    r.replace(/^"+|"+$/g, '').replace(/"/g, '')
                  );
                  return [cleanKey, ...cleanRecs];
                })
                .map((item) => item.toLowerCase())
            ),
          ];




            console.log(
              `[DEBUG] Expanded ${initialChannels.length} to ${Object.keys(expandedChannels || {}).length} channels and ${uniqueChannels.length} unique usernames`
            );

            const channelsUrl = new URL(`${base}/messages/channels`);
            channelsUrl.searchParams.set('usernames', uniqueChannels.join(','));
            const channelsRes = await authFetch(channelsUrl.toString());
            const tgChannelsData = await channelsRes.json();

            const mergedChannelsData = transformChannelData(tgChannelsData, expandedChannels);

            setTgChannels(mergedChannelsData);
            setSelectedTgChannelIds(tgChannelsData.map((c: any) => c.channel_id));

          } catch (expandError) {
            console.warn('Failed to expand channels, using initial list:', expandError);
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
        setLoading(false); // Always stop loading
      }
    };

    fetchData();
  }, [id]);

  function updateGraph(type: string | null, user: string | null) {
    setGraphType(type);
    setGraphUser(user);
    setActiveTab('visuals');
  }

  function formatDate(dateString: string | null): string {
    if (!dateString) {
      return 'No valid date provided';
    }
    const date = new Date(dateString);
    return date.toLocaleString();
  }

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

      if (groupChannel) {
        recommended[groupChannel.username] = { channel: groupChannel };
      }

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
                    <TgChannelsCheckboxList
                      structuredChannels={structuredChannels}
                      selectedTgChannelIds={selectedTgChannelIds}
                      setSelectedTgChannelIds={setSelectedTgChannelIds}
                    />
                  </Stack>
                </div>
              </Card>
            </Grid.Col>
          </Grid>
        </Grid.Col>
        <Grid.Col span={9}>
          <Card withBorder radius="md" className={classes.card}>
            <div className={classes.inner}>
              <Tabs value={activeTab} onChange={setActiveTab} w="100%">
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
                  <Tabs.Tab value="details" leftSection={<IconInfoCircle size={16} />}>
                    Details
                  </Tabs.Tab>
                </Tabs.List>

                <Tabs.Panel value="messages" mt="md">
                  <MessagesTab
                    selectedTgChannelIds={selectedTgChannelIds}
                    searchQuery={searchQuery}
                    setSearchQuery={setSearchQuery}
                    onUpdateGraph={updateGraph}
                  />
                </Tabs.Panel>

                <Tabs.Panel value="scraper" mt="md">
                  <ChannelsTab
                    caseId={id!}
                    caseFile={caseFile}
                    structuredChannels={structuredChannels}
                  />
                </Tabs.Panel>

                <Tabs.Panel value="visuals" mt="md">
                  <GraphVisualization
                    selectedChannelIds={selectedTgChannelIds}
                    searchQuery={searchQuery}
                    user={graphUser}
                    type={graphType}
                  />
                </Tabs.Panel>

                <Tabs.Panel value="details" mt="md">
                  <Card withBorder p="md">
                    <Stack gap="md">
                      <Group justify="flex-start" align="flex-start">
                        <Title order={2} size="h2" fw={600}>
                          {caseFile.title}
                        </Title>
                        <Badge color="blue" variant="light">
                          {caseFile.postCount} messages
                        </Badge>
                      </Group>

                      <Text size="md" c="dimmed" lineClamp={3}>
                        {caseFile.description}
                      </Text>

                      <Group gap="xs">
                        <Text size="sm" fw={500}>
                          Created:
                        </Text>
                        <Text size="sm" c="dimmed">
                          {formatDate(caseFile.created_at)}
                        </Text>
                      </Group>
                    </Stack>
                  </Card>
                </Tabs.Panel>
              </Tabs>
            </div>
          </Card>
        </Grid.Col>
      </Grid>
    </div>
  );
}
