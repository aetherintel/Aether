// src/components/widgets/LocationHeatmapWidget.tsx
import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  Text,
  Group,
  Badge,
  Stack,
  ScrollArea,
  Skeleton,
  Alert,
  ActionIcon,
  Tooltip,
  Progress,
} from '@mantine/core';
import {
  IconMapPin,
  IconRefresh,
  IconAlertCircle,
  IconWorld,
} from '@tabler/icons-react';
import { WidgetComponentProps } from '@/types/widgets.types';
import { authFetch } from '@/utils/authFetch';

const apiUrl = import.meta.env.VITE_API_URL;

interface LocationData {
  location: string;
  count: number;
  percentage: number;
  coordinates: { lat: number; lng: number };
}

const fetchLocations = async (config: any): Promise<LocationData[]> => {
  const base = apiUrl ?? 'http://localhost:8000/api';
  const channelIds = config.filters?.channelIds || [];
  const limit = config.filters?.limit || 5;

  if (!channelIds || channelIds.length === 0) return [];

  try {
    const results = await Promise.all(
      channelIds.map(async (channelId: string) => {
        const url = `${base}/messages/channels/${channelId}/locations?limit=1000`;
        const res = await authFetch(url);
        return await res.json();
      })
    );

    const allMessages = results.flat();
    const locationCounts = new Map<string, {count: number, coords: {lat: number, lng: number}}>();

    allMessages.forEach((msg: any) => {
      const name = msg.canonical_name || `${msg.location.lat.toFixed(4)}, ${msg.location.lng.toFixed(4)}`;
      
      if (locationCounts.has(name)) {
        locationCounts.get(name)!.count += 1;
      } else {
        locationCounts.set(name, {
          count: 1,
          coords: msg.location
        });
      }
    });

    const total = Array.from(locationCounts.values()).reduce((a, b) => a + b.count, 0);
    const locations: LocationData[] = Array.from(locationCounts.entries())
      .map(([location, data]) => ({
        location,
        count: data.count,
        percentage: (data.count / total) * 100,
        coordinates: data.coords
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, limit);

    return locations;
  } catch (error) {
    console.error('Error in fetchLocations:', error);
    throw error;
  }
};

export const LocationHeatmapWidget: React.FC<WidgetComponentProps> = ({
  widget,
  onUpdate,
  onRemove,
  isEditing,
}) => {
  const [locations, setLocations] = useState<LocationData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const loadLocations = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        const data = await fetchLocations(widget.config);
        setLocations(data);
      } catch (err) {
        setError(err as Error);
      } finally {
        setIsLoading(false);
      }
    };

    loadLocations();

    const refreshInterval = widget.config.refreshInterval;
    if (refreshInterval && refreshInterval > 0) {
      const intervalId = setInterval(loadLocations, refreshInterval);
      return () => clearInterval(intervalId);
    }
  }, [widget.config, refreshKey]);

  if (isLoading) {
    return (
      <Stack gap="sm">
        {Array.from({ length: widget.config.filters?.limit || 5 }, (_, i) => (
          <Skeleton key={i} height={60} radius="md" />
        ))}
      </Stack>
    );
  }

  if (error) {
    return (
      <Alert icon={<IconAlertCircle size={16} />} color="red" title="Error loading locations">
        <Text size="sm">{error.message}</Text>
      </Alert>
    );
  }

  if (!locations || locations.length === 0) {
    return (
      <Box style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '200px' }}>
        <IconMapPin size={32} stroke={1.5} style={{ opacity: 0.5 }} />
        <Text size="sm" c="dimmed" mt="sm">No location data found</Text>
      </Box>
    );
  }

  const maxCount = Math.max(...locations.map(l => l.count));

  return (
    <Box style={{ position: 'relative' }}>
      <Group justify="flex-end" mb="xs">
        <Tooltip label="Refresh">
          <ActionIcon variant="subtle" size="sm" onClick={() => setRefreshKey(p => p + 1)}>
            <IconRefresh size={16} />
          </ActionIcon>
        </Tooltip>
      </Group>

      <ScrollArea h="calc(100% - 40px)" scrollbarSize={6}>
        <Stack gap="sm">
          {locations.map((location, index) => (
            <Card key={location.location} withBorder radius="md" padding="sm">
              <Group justify="space-between" mb="xs">
                <Group gap="xs">
                  <Badge size="sm" variant="dot" color="blue">#{index + 1}</Badge>
                  <IconWorld size={16} />
                  <Text size="sm" fw={500}>{location.location}</Text>
                </Group>
                <Badge size="sm" variant="light">
                  {location.count} mentions
                </Badge>
              </Group>

              <Progress 
                value={(location.count / maxCount) * 100} 
                size="sm"
                color="blue"
              />

              <Text size="xs" c="dimmed" mt={4}>
                {location.percentage.toFixed(1)}% of all mentions
              </Text>
            </Card>
          ))}
        </Stack>
      </ScrollArea>
    </Box>
  );
};