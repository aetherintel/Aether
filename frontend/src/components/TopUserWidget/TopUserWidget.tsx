import { useState, useEffect } from 'react';
import { Box, Title, Accordion, Text, Group, Badge, Loader, Divider, ActionIcon, Progress } from '@mantine/core';
import { IconSettings, IconUserCircle } from '@tabler/icons-react';
import { authFetch } from '@/utils/authFetch';
import { TopUserForm } from './TopUserForm';
import classes from './TopUserWidget.module.css';

const apiUrl = import.meta.env.VITE_API_URL;

interface User {
  id: string;
  name: string;
  messageCount: number;
  channels: {
    id: string;
    title: string;
    count: number;
  }[];
  percentage: number;
}

interface SearchParams {
  label: string;
  channelIds: string[];
  isActive: boolean;
}

export function TopUserWidget() {
  const [searchParams, setSearchParams] = useState<SearchParams>({
    label: 'Top 5 Active Users',
    channelIds: [],
    isActive: false
  });
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [openItems, setOpenItems] = useState<string[]>(['config']);

  // Load config and users from local storage
  useEffect(() => {
    const savedConfig = localStorage.getItem('topUserConfig');
    if (savedConfig) {
      try {
        const config = JSON.parse(savedConfig);
        setSearchParams(config);
      } catch (e) {
        console.error('Error loading saved config:', e);
      }
    }

    // Load users
    const savedUsers = localStorage.getItem('topUserResults');
    if (savedUsers) {
      try {
        const userData = JSON.parse(savedUsers);
        setUsers(userData.users || []);
        
        // Open users accordion if data is available
        if (userData.users && userData.users.length > 0) {
          setSearchParams(prev => ({ ...prev, isActive: true }));
          setOpenItems(['users']);
        }
      } catch (e) {
        console.error('Error loading saved users:', e);
      }
    }
  }, []);

  // Reset widget to initial state
  const resetWidget = () => {
    setSearchParams({
      label: 'Top 5 Active Users',
      channelIds: [],
      isActive: false
    });
    setUsers([]);
    setOpenItems(['config']);
    
    localStorage.removeItem('topUserConfig');
    localStorage.removeItem('topUserResults');
  };

  // Fetch top users data from API
  const fetchTopUsers = async () => {
    if (!searchParams.channelIds.length) {
      return;
    }

    setLoading(true);
    try {
      const base = apiUrl ?? 'http://localhost:8000/api';
      const channelInfoMap = new Map();
      
      // Fetch channel information
      try {
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

      // Track user activity across channels
      const userActivityMap = new Map<string, { 
        name: string, 
        totalCount: number,
        channelCounts: Map<string, number>
      }>();
      
      let allMessagesCount = 0;

      // Process messages from each selected channel
      await Promise.all(
        searchParams.channelIds.map(async (channelId) => {
          try {
            const url = new URL(`${base}/messages/channels/${channelId}/messages`);
            url.searchParams.set('limit', '1000');
            
            const res = await authFetch(url.toString());
            const messages = await res.json();
            
            allMessagesCount += messages.length;

            // Count messages per user
            messages.forEach((msg: any) => {
              if (msg.author && msg.author.id) {
                const userId = msg.author.id;
                const userName = msg.author.name || 'Unknown User';
                
                if (!userActivityMap.has(userId)) {
                  userActivityMap.set(userId, { 
                    name: userName, 
                    totalCount: 0,
                    channelCounts: new Map()
                  });
                }
                
                const userData = userActivityMap.get(userId)!;
                userData.totalCount += 1;
                
                // Count messages per channel
                if (!userData.channelCounts.has(channelId)) {
                  userData.channelCounts.set(channelId, 0);
                }
                userData.channelCounts.set(
                  channelId, 
                  userData.channelCounts.get(channelId)! + 1
                );
              }
            });
          } catch (error) {
            console.error(`Error fetching messages for channel ${channelId}:`, error);
          }
        })
      );
      
      // Convert data to the required format
      const topUsers = Array.from(userActivityMap.entries())
        .map(([id, data]) => ({
          id,
          name: data.name,
          messageCount: data.totalCount,
          channels: Array.from(data.channelCounts.entries())
            .sort((a, b) => b[1] - a[1]) // Sort channels by activity (most active first)
            .map(([channelId, count]) => ({
              id: channelId,
              title: channelInfoMap.get(channelId)?.title || channelId,
              count
            })),
          percentage: allMessagesCount > 0 ? (data.totalCount / allMessagesCount) * 100 : 0
        }))
        .sort((a, b) => b.messageCount - a.messageCount)
        .slice(0, 5); // Top 5 users
      
      setUsers(topUsers);
      
      // Mark widget as active if users were found
      if (topUsers.length > 0) {
        setSearchParams(prev => ({ ...prev, isActive: true }));
        
        localStorage.setItem('topUserConfig', JSON.stringify({
          ...searchParams,
          isActive: true
        }));
        
        localStorage.setItem('topUserResults', JSON.stringify({
          users: topUsers
        }));
        
        setOpenItems(['users']);
      }
    } catch (error) {
      console.error('Error fetching top users:', error);
    } finally {
      setLoading(false);
    }
  };

  // Toggle config accordion
  const toggleConfig = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (openItems.includes('config')) {
      setOpenItems(openItems.filter(item => item !== 'config'));
    } else {
      setOpenItems([...openItems, 'config']);
    }
  };

  return (
    <Box className={classes.widget}>
      <Group justify="space-between" className={classes.widgetHeader}>
        <Title order={3} className={classes.title}>
          {searchParams.isActive ? searchParams.label : 'Top Active Users'}
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

      <Accordion 
        multiple 
        value={openItems} 
        onChange={setOpenItems}
      >
        <Accordion.Item value="config" className={classes.configAccordionItem}>
          <Accordion.Control className={classes.hiddenControl}>
            <span style={{ display: 'none' }}>Configuration</span>
          </Accordion.Control>
          <Accordion.Panel>
            <TopUserForm
              searchParams={searchParams}
              setSearchParams={setSearchParams}
              onSearch={fetchTopUsers}
              onReset={resetWidget}
            />
          </Accordion.Panel>
        </Accordion.Item>

        {searchParams.isActive && (
          <Accordion.Item value="users" className={classes.usersAccordionItem}>
            <Accordion.Control className={classes.hiddenControl}>
              <span style={{ display: 'none' }}>Users</span>
            </Accordion.Control>
            <Accordion.Panel>
              {loading ? (
                <Loader size="sm" />
              ) : users.length === 0 ? (
                <Text className={classes.noResults}>No users found</Text>
              ) : (
                <div className={classes.usersList}>
                  {users.map((user, index) => (
                    <div key={user.id}>
                      <div className={classes.userItem}>
                        <div className={classes.userHeader}>
                          <Group justify="space-between" className={classes.userHeaderInner} wrap="nowrap">
                            <Group gap="xs" wrap="nowrap">
                              <IconUserCircle size={20} className={classes.userIcon} />
                              <Text fw={500}>{user.name}</Text>
                            </Group>
                            <Badge color="green" radius="sm">
                              {user.messageCount} messages
                            </Badge>
                          </Group>
                        </div>
                        <div className={classes.userContent}>
                          <Group className={classes.progressGroup}>
                            <Progress 
                              value={user.percentage} 
                              color="blue" 
                              size="sm"
                              className={classes.userProgress}
                            />
                            <Text size="xs" className={classes.percentageText}>
                              {user.percentage.toFixed(1)}%
                            </Text>
                          </Group>
                          <Text size="xs" color="dimmed" className={classes.userInfo}>
                            Activity across channels:
                          </Text>
                          <div className={classes.channelsList}>
                            {user.channels.map(channel => (
                              <Group key={channel.id} justify="space-between" className={classes.channelItem}>
                                <Text size="xs">{channel.title}</Text>
                                <Badge size="xs" variant="light">
                                  {channel.count} posts
                                </Badge>
                              </Group>
                            ))}
                          </div>
                        </div>
                      </div>
                      {index < users.length - 1 && <Divider my="sm" />}
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