import { useEffect, useState } from 'react';
import { Button, Group, MultiSelect, Stack, TextInput } from '@mantine/core';
import { authFetch } from '@/utils/authFetch';

const apiUrl = import.meta.env.VITE_API_URL;

interface Channel {
  channel_id: string;
  title: string;
  username: string;
  is_scraped: boolean;
}

interface SearchParams {
  label: string;
  channelIds: string[];
  keywords: string;
  isActive: boolean;
}

interface TopMessagesFormProps {
  searchParams: SearchParams;
  setSearchParams: React.Dispatch<React.SetStateAction<SearchParams>>;
  onSearch: () => void;
  onReset: () => void;
}

export function TopMessagesForm({
  searchParams,
  setSearchParams,
  onSearch,
  onReset,
}: TopMessagesFormProps) {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(false);

  // load channels
  useEffect(() => {
    const fetchChannels = async () => {
      setLoading(true);
      try {
        const base = apiUrl ?? 'http://localhost:8000/api';
        const res = await authFetch(`${base}/messages/channels`);
        const data = await res.json();

        console.log('all available channels:', data);

        // get only channels that have been scraped or have messages
        const scrapedChannels = data.filter((channel: any) => {
          // Debug for every channel
          console.log(
            `Channel ${channel.username}: is_scraped=${channel.is_scraped}, message_count=${channel.message_count}`
          );
          return channel.is_scraped === true || channel.message_count > 0;
        });

        console.log('scraped Channels:', scrapedChannels);
        setChannels(scrapedChannels);
      } catch (error) {
        console.error('Error fetching channels:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchChannels();
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch();
  };

  return (
    <form onSubmit={handleSubmit}>
      <Stack gap="md">
        <TextInput
          label="Topic Name"
          placeholder="Top 5 news about climate protection"
          value={searchParams.label}
          onChange={(e) => setSearchParams((prev) => ({ ...prev, label: e.target.value }))}
          required
        />

        <MultiSelect
          label="Channel"
          placeholder="Choose Channel"
          data={channels.map((channel) => ({
            value: channel.channel_id,
            label: channel.title || channel.username || channel.channel_id,
          }))}
          value={searchParams.channelIds}
          onChange={(value) => setSearchParams((prev) => ({ ...prev, channelIds: value }))}
          searchable
          nothingFoundMessage="No Channels found"
          disabled={loading}
          required
        />

        <TextInput
          label="Keywords"
          placeholder="eg. climate, corona, news, ..."
          value={searchParams.keywords}
          onChange={(e) => setSearchParams((prev) => ({ ...prev, keywords: e.target.value }))}
          required
        />

        <Group justify="right">
          {searchParams.isActive && (
            <Button onClick={onReset} variant="outline" color="red">
              Reset
            </Button>
          )}
          <Button
            type="submit"
            disabled={!searchParams.keywords || searchParams.channelIds.length === 0}
          >
            Search
          </Button>
        </Group>
      </Stack>
    </form>
  );
}
