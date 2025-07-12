import { useState, useEffect } from 'react';
import { TextInput, MultiSelect, Button, Group, Stack } from '@mantine/core';
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
}

export function TopMessagesForm({ searchParams, setSearchParams, onSearch }: TopMessagesFormProps) {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(false);

  // Laden der verfügbaren Channels beim ersten Rendern
  useEffect(() => {
    const fetchChannels = async () => {
      setLoading(true);
      try {
        const base = apiUrl ?? 'http://localhost:8000/api';
        const res = await authFetch(`${base}/messages/channels`);
        const data = await res.json();

        // Nur bereits gescrapte Channels anzeigen
        const scrapedChannels = data.filter((channel: any) => channel.is_scraped);
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
          label="Widget Name"
          placeholder="e.g. Top 5 news about climate protection"
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
          placeholder="Devide keywords with space"
          value={searchParams.keywords}
          onChange={(e) => setSearchParams((prev) => ({ ...prev, keywords: e.target.value }))}
          required
        />

        <Group justify="right">
          <Button type="submit" disabled={!searchParams.keywords || searchParams.channelIds.length === 0}>
            Suchen
          </Button>
        </Group>
      </Stack>
    </form>
  );
}