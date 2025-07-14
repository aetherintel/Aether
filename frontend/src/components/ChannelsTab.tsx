import { IconTrash } from '@tabler/icons-react';
import { Box, Button, Card, Group, List, Stack, Text, Title } from '@mantine/core';
import TelegramScraper from '@/components/TelegramScraper';
import type { OutputChannelEntry } from '@/types/caseFileDetail';
import { authFetch } from '@/utils/authFetch';

const apiUrl = import.meta.env.VITE_API_URL;

interface ChannelsTabProps {
  caseId: string;
  caseFile: any;
  structuredChannels: [string, OutputChannelEntry][];
}

const ChannelsTab: React.FC<ChannelsTabProps> = ({ caseId, structuredChannels }) => {
  const removeChannelsFromCase = async (channels: string[]) => {
    try {
      const base = apiUrl ?? 'http://localhost:8000/api';

      const removeChannelsRes = await authFetch(`${base}/casefiles/${caseId}/remove-channels`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(channels),
      });

      if (removeChannelsRes.ok) {
        const result = await removeChannelsRes.json();
        alert(
          `${result.removed_channels.length} removed channels: ${result.removed_channels.join(', ')}`
        );
      }
    } catch (error) {
      console.error('Error removing channels from case:', error);
      alert('Error removing channels from case');
    }
  };

  function formatDate(dateString: string | null): string {
    if (!dateString) {
      return 'No valid date provided';
    }
    const date = new Date(dateString);
    return date.toLocaleString();
  }

  return (
    <div>
      <Stack gap="md">
        <Card withBorder p="md">
          <Stack gap="xs">
            <Title order={4}>Channels</Title>
            <Stack gap="sm">
              {structuredChannels
                .filter(([, groupValue]) => groupValue.channel)
                .map(([groupKey, groupValue]) => (
                  <Card key={groupKey} padding="sm" withBorder>
                    <Group justify="space-between" align="flex-start">
                      <Stack gap="xs" style={{ flex: 1 }}>
                        <Box>
                          <Text fw={500}>{groupValue.channel!.username}</Text>
                          <Text size="sm" c="dimmed">
                            Last message: {formatDate(groupValue.channel!.last_message_date)}
                          </Text>
                          <Text size="xs" c="dimmed">
                            ID: {groupValue.channel!.channel_id}
                          </Text>
                        </Box>

                        <Text size="xs">Recommended Channels:</Text>
                        <List>
                          {Object.entries(groupValue.recommended).map(([recUsername, recData]) => (
                            <List.Item key={recUsername}>
                              <Text size="xs">
                                {recUsername} ({recData.channel.message_count} messages)
                              </Text>
                            </List.Item>
                          ))}
                        </List>
                      </Stack>
                      <Stack gap="xs">
                        <Button
                          onClick={() => removeChannelsFromCase([groupValue.channel!.username])}
                          variant="filled"
                          color="red"
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
  );
};

export default ChannelsTab;
