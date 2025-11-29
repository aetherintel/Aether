// src/components/widgets/LocationMapWidget.tsx
import React, { useEffect, useState } from 'react';
import {
  Box,
  Alert,
  ActionIcon,
  Tooltip,
  Group,
  Badge,
  Skeleton,
  Text,
} from '@mantine/core';
import {
  IconRefresh,
  IconAlertCircle,
  IconMapPin,
} from '@tabler/icons-react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { WidgetComponentProps } from '@/types/widgets.types';
import { authFetch } from '@/utils/authFetch';

const apiUrl = import.meta.env.VITE_API_URL;

// Fix Leaflet default icon
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

interface LocationPoint {
  message_id: string;
  location: { lat: number; lng: number };
  canonical_name?: string;
  country?: string;
  mention_count?: number;
  text?: string;
}

const fetchLocationPoints = async (config: any): Promise<LocationPoint[]> => {
  const base = apiUrl ?? 'http://localhost:8000/api';
  const channelIds = config.filters?.channelIds || [];

  if (!channelIds || channelIds.length === 0) return [];

  try {
    const results = await Promise.all(
      channelIds.map(async (channelId: string) => {
        const url = `${base}/messages/channels/${channelId}/locations?limit=5000`;
        const res = await authFetch(url);
        return await res.json();
      })
    );

    return results.flat();
  } catch (error) {
    console.error('Error fetching location points:', error);
    throw error;
  }
};

const FitBounds: React.FC<{ points: LocationPoint[] }> = ({ points }) => {
  const map = useMap();

  useEffect(() => {
    if (points.length > 0) {
      const bounds = L.latLngBounds(
        points.map(p => [p.location.lat, p.location.lng])
      );
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [points, map]);

  return null;
};

export const LocationMapWidget: React.FC<WidgetComponentProps> = ({
  widget,
  onUpdate,
  onRemove,
  isEditing,
}) => {
  const [points, setPoints] = useState<LocationPoint[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const loadPoints = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const data = await fetchLocationPoints(widget.config);
        setPoints(data);
      } catch (err) {
        setError(err as Error);
      } finally {
        setIsLoading(false);
      }
    };

    loadPoints();

    const refreshInterval = widget.config.refreshInterval;
    if (refreshInterval && refreshInterval > 0) {
      const intervalId = setInterval(loadPoints, refreshInterval);
      return () => clearInterval(intervalId);
    }
  }, [widget.config, refreshKey]);

  if (isLoading) {
    return <Skeleton height="100%" radius="md" />;
  }

  if (error) {
    return (
      <Alert icon={<IconAlertCircle size={16} />} color="red" title="Error loading map">
        <Text size="sm">{error.message}</Text>
      </Alert>
    );
  }

  if (!points || points.length === 0) {
    return (
      <Box style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '300px' }}>
        <IconMapPin size={32} stroke={1.5} style={{ opacity: 0.5 }} />
        <Text size="sm" c="dimmed" mt="sm">No location data found</Text>
      </Box>
    );
  }

  return (
    <Box style={{ position: 'relative', height: '100%', minHeight: '400px' }}>
      <Group justify="space-between" mb="xs" style={{ position: 'absolute', top: 10, right: 10, zIndex: 1000 }}>
        <Badge size="lg" variant="filled">
          {points.length} locations
        </Badge>
        <Tooltip label="Refresh">
          <ActionIcon variant="filled" size="lg" onClick={() => setRefreshKey(p => p + 1)}>
            <IconRefresh size={16} />
          </ActionIcon>
        </Tooltip>
      </Group>

      <MapContainer
        center={[51.1657, 10.4515]}
        zoom={6}
        style={{ height: '100%', width: '100%', borderRadius: '8px' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        
        <FitBounds points={points} />

        <MarkerClusterGroup>
          {points.map((point, idx) => (
            <Marker
              key={`${point.message_id}-${idx}`}
              position={[point.location.lat, point.location.lng]}
            >
              <Popup>
                <div>
                  <strong>{point.canonical_name || 'Unknown Location'}</strong>
                  {point.country && <div><small>{point.country}</small></div>}
                  {point.mention_count && <div><Badge size="xs">{point.mention_count} mentions</Badge></div>}
                  {point.text && (
                    <div style={{ marginTop: '8px', maxWidth: '200px' }}>
                      <small>{point.text.substring(0, 100)}...</small>
                    </div>
                  )}
                </div>
              </Popup>
            </Marker>
          ))}
        </MarkerClusterGroup>
      </MapContainer>
    </Box>
  );
};