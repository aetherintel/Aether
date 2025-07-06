import { Card, Stack, Title, Text, Button, Group, Box, List } from "@mantine/core";
import TelegramScraper from "@/components/TelegramScraper";
import { authFetch } from '@/utils/authFetch';
import { IconTrash } from "@tabler/icons-react";
import type { OutputChannelEntry } from "@/types/caseFileDetail";

const apiUrl = import.meta.env.VITE_API_URL;

interface ChannelsTabProps {
    caseId: string;
    caseFile: any;
    structuredChannels: [string, OutputChannelEntry][];
}

const ChannelsTab : React.FC<ChannelsTabProps> = ({ caseId, caseFile, structuredChannels }) => {

    const removeChannelsFromCase = async (channels: string[]) => {
        try {
            const base = apiUrl ?? 'http://localhost:8000/api';

            const removeChannelsRes = await authFetch(`${base}/casefiles/${caseId}/remove-channels`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(channels)
            });
            
            if (removeChannelsRes.ok) {
            const result = await removeChannelsRes.json();
            alert(`${result.removed_channels.length} removed channels: ${result.removed_channels.join(', ')}`);
            }
        } catch (error) {
            console.error('Error removing channels from case:', error);
            alert('Error removing channels from case');
        }
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
            /*const addChannelsRes = await authFetch(`${base}/casefiles/${id}/add-channels`, {
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
            }*/
        } else {
            alert('No new channels found');
        }
        
        } catch (error) {
            console.error('Error updating case with discoveries:', error);
            alert('Error checking for new channels');
        }
    };

    return (
        <div>
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
                <Card withBorder p="md">
                    <Stack gap="xs">
                    <Title order={4}>Channels</Title>
                    <Stack gap="sm">
                        {structuredChannels
                        .filter(([, groupValue]) => groupValue.channel)
                        .map(([groupKey, groupValue]) => (
                            <Card key={groupKey} padding="sm" withBorder>
                            <Group justify="space-between" align='flex-start'>
                                <Stack gap="xs" style={{ flex: 1 }}>
                                <Box>
                                    <Text fw={500}>{groupValue.channel!.username}</Text>
                                    <Text size="sm" c="dimmed">
                                    Last message: {groupValue.channel!.last_message_date}
                                    </Text>
                                    <Text size="xs" c="dimmed">
                                    ID: {groupValue.channel!.channel_id}
                                    </Text>
                                </Box>

                                <Text size="xs">Recommended Channels:</Text>
                                <List>
                                    {Object.entries(groupValue.recommended).map(([recUsername, recData]) => (
                                    <List.Item key={recUsername}>
                                        <Text size="xs">{recUsername} ({recData.channel.message_count} messages)</Text>
                                    </List.Item>
                                    ))}
                                </List>
                                </Stack>
                                <Stack gap="xs">
                                <Button
                                    onClick={() => removeChannelsFromCase([groupValue.channel!.username])}
                                    variant="filled" color="red"
                                    leftSection={<IconTrash size={14} />}
                                >
                                    Delete
                                </Button>
                                </Stack>
                            </Group>
                            </Card>
                        ))}
                    </Stack>
                    </Stack>
                </Card>
                <TelegramScraper case_id={parseInt(caseId!, 10)} />
            </Stack>
        </div>
    )
}

export default ChannelsTab;
