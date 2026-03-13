// src/components/widgets/LocationMapWidget.tsx
import React, { useEffect, useState } from 'react';
import { Box, Alert, Skeleton, Text } from '@mantine/core';
import { IconAlertCircle, IconMapPin } from '@tabler/icons-react';
import { WidgetComponentProps } from '@/types/widgets.types';
import { authFetch } from '@/utils/authFetch';
import { LocationMap, MapPoint } from '@/components/map/LocationMap';

const apiUrl = import.meta.env.VITE_API_URL;

const fetchLocationPoints = async (config: any): Promise<MapPoint[]> => {
  const base = apiUrl ?? 'http://localhost:8000/api';
  const channelIds: string[] = config.filters?.channelIds ?? [];
  if (channelIds.length === 0) return [];

  const results = await Promise.all(
    channelIds.map(async (channelId) => {
      const res = await authFetch(
        `${base}/messages/channels/${channelId}/locations?limit=5000`,
      );
      const data = await res.json();
      // Normalise API shape → MapPoint
      return (Array.isArray(data) ? data : []).map((item: any) => ({
        id: item.message_id ?? `${item.lat}-${item.lng}`,
        lat: item.location?.lat ?? item.lat,
        lng: item.location?.lng ?? item.lng,
        canonical_name: item.canonical_name ?? item.name,
        country: item.country,
        mention_count: item.mention_count,
        sample_messages: item.sample_messages,
      } satisfies MapPoint));
    }),
  );
  return results.flat();
};

export const LocationMapWidget: React.FC<WidgetComponentProps> = ({ widget }) => {
  const [points, setPoints] = useState<MapPoint[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    fetchLocationPoints(widget.config)
      .then(data => { if (!cancelled) setPoints(data); })
      .catch(err => { if (!cancelled) setError(err as Error); })
      .finally(() => { if (!cancelled) setIsLoading(false); });

    const iv = widget.config.refreshInterval;
    if (iv && iv > 0) {
      const id = setInterval(() => {
        fetchLocationPoints(widget.config)
          .then(data => { if (!cancelled) setPoints(data); })
          .catch(() => {});
      }, iv);
      return () => { cancelled = true; clearInterval(id); };
    }
    return () => { cancelled = true; };
  }, [widget.config, refreshKey]);

  if (isLoading) return <Skeleton height="100%" radius="md" />;

  if (error) {
    return (
      <Alert icon={<IconAlertCircle size={16} />} color="red" title="Error loading map">
        <Text size="sm">{error.message}</Text>
      </Alert>
    );
  }

  if (points.length === 0) {
    return (
      <Box style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '300px' }}>
        <IconMapPin size={32} stroke={1.5} style={{ opacity: 0.5 }} />
        <Text size="sm" c="dimmed" mt="sm">No location data found</Text>
      </Box>
    );
  }

  return (
    <LocationMap
      points={points}
      onRefresh={() => setRefreshKey(k => k + 1)}
      height="100%"
    />
  );
};
