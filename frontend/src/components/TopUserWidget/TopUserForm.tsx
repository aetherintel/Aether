import { useEffect, useState } from 'react';
import { Button, Group, MultiSelect, Stack, TextInput } from '@mantine/core';
import { authFetch } from '@/utils/authFetch';

const apiUrl = import.meta.env.VITE_API_URL;

interface Channel {
  channel_id: string;
  title: string;
  username: string;
  is_scraped: boolean;
  message_count: number;
}

interface SearchParams {
  label: string;
  channelIds: string[];
  isActive: boolean;
}

interface TopUserFormProps {
  searchParams: SearchParams;
  setSearchParams: React.Dispatch<React.SetStateAction<SearchParams>>;
  onSearch: () => void;
  onReset: () => void;
}

export function TopUserForm({
  searchParams,
  setSearchParams,
  onSearch,
  onReset,
}: TopUserFormProps) {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(false);

  // Load available channels that have been scraped
  useEffect(() => {
    const fetchChannels = async () => {
      setLoading(true);
      try {
        const base = apiUrl ?? 'http://localhost:8000/api';
        const res = await authFetch(`${base}/messages/channels`);
        const data = await res.json();

        // Only show channels that have been scraped or have messages
        const scrapedChannels = data.filter(
          (channel: Channel) => channel.is_scraped === true || channel.message_count > 0
        );

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
          label="Title"
          placeholder="Top 5 active users"
          value={searchParams.label}
          onChange={(e) => setSearchParams((prev) => ({ ...prev, label: e.target.value }))}
          required
        />

        <MultiSelect
          label="Channels"
          placeholder="Choose Channels"
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

        <Group justify="right">
          {searchParams.isActive && (
            <Button onClick={onReset} variant="outline" color="red">
              Reset
            </Button>
          )}
          <Button type="submit" disabled={searchParams.channelIds.length === 0}>
            Search
          </Button>
        </Group>
      </Stack>
    </form>
  );
}
