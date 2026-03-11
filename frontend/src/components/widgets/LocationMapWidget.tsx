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
  Loader,
} from '@mantine/core';
import {
  IconRefresh,
  IconAlertCircle,
  IconMapPin,
} from '@tabler/icons-react';
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  useMap,
  LayersControl,
  LayerGroup,
} from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { WidgetComponentProps } from '@/types/widgets.types';
import { authFetch } from '@/utils/authFetch';
import { OSINT_ICONS, OSINT_LABELS } from '@/utils/osintIcons';

const apiUrl = import.meta.env.VITE_API_URL;
const ESRI_API_KEY = import.meta.env.VITE_ESRI_API_KEY ?? '';

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
  sample_messages?: Array<{ text: string; date?: string }>;
}

type OsintData = Record<string, Array<{
  id: number;
  lat: number;
  lng: number;
  name: string;
  operator: string;
  tags: Record<string, string>;
}>>;

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
}) => {
  const [points, setPoints] = useState<LocationPoint[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [osintData, setOsintData] = useState<OsintData>({});
  const [loadingOsint, setLoadingOsint] = useState(false);

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

  const loadOsintLayers = async (lat: number, lng: number) => {
    setLoadingOsint(true);
    try {
      const base = apiUrl ?? 'http://localhost:8000/api';
      const res = await authFetch(
        `${base}/geo/osint-layers?lat=${lat}&lng=${lng}&radius=500&layers=cameras,atm,bank,police,military,power,water,alpr`
      );
      const data = await res.json();
      setOsintData(data);
    } catch (err) {
      console.error('Failed to load OSINT layers:', err);
    } finally {
      setLoadingOsint(false);
    }
  };

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

  const satelliteUrl = ESRI_API_KEY
    ? `https://ibasemaps-api.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}?token=${ESRI_API_KEY}`
    : null;

  return (
    <Box style={{ position: 'relative', height: '100%', minHeight: '400px' }}>
      <Group justify="space-between" mb="xs" style={{ position: 'absolute', top: 10, right: 10, zIndex: 1000 }}>
        {loadingOsint && <Loader size="xs" />}
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
        <LayersControl position="topright">
          {/* ── Basemaps ── */}
          <LayersControl.BaseLayer checked name="OpenStreetMap">
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
          </LayersControl.BaseLayer>

          {satelliteUrl && (
            <LayersControl.BaseLayer name="Satellite (ArcGIS)">
              <TileLayer
                url={satelliteUrl}
                attribution='Tiles &copy; Esri &mdash; Maxar, Earthstar Geographics'
                maxZoom={19}
              />
            </LayersControl.BaseLayer>
          )}

          {/* ── OSINT Overlays ── */}
          {Object.entries(osintData).map(([layer, items]) =>
            items && items.length > 0 ? (
              <LayersControl.Overlay key={layer} checked name={OSINT_LABELS[layer] ?? layer}>
                <LayerGroup>
                  {items.map(item => (
                    item.lat != null && item.lng != null ? (
                      <Marker
                        key={item.id}
                        position={[item.lat, item.lng]}
                        icon={OSINT_ICONS[layer]}
                      >
                        <Popup>
                          <div style={{ fontFamily: 'system-ui, sans-serif', minWidth: 160 }}>
                            <div style={{ fontWeight: 700, marginBottom: 4 }}>
                              {OSINT_LABELS[layer] ?? layer}
                            </div>
                            {item.name && <div>{item.name}</div>}
                            {item.operator && (
                              <div style={{ fontSize: '0.75rem', color: '#888' }}>{item.operator}</div>
                            )}
                            {item.tags?.['surveillance:type'] && (
                              <div style={{ fontSize: '0.75rem' }}>
                                Type: {item.tags['surveillance:type']}
                              </div>
                            )}
                          </div>
                        </Popup>
                      </Marker>
                    ) : null
                  ))}
                </LayerGroup>
              </LayersControl.Overlay>
            ) : null
          )}
        </LayersControl>

        <FitBounds points={points} />

        {/* ── Location Markers (cluster) — click loads OSINT layers ── */}
        <MarkerClusterGroup>
          {points.map((point, idx) => {
            const mentions = point.mention_count ?? 1;
            const radius = Math.min(Math.max(8 + Math.sqrt(mentions) * 2, 10), 36);
            const hue = Math.max(0, 120 - mentions * 4);
            const circleIcon = L.divIcon({
              className: '',
              html: `<div style="width:${radius*2}px;height:${radius*2}px;border-radius:50%;background:hsl(${hue},80%,50%);border:2px solid white;opacity:0.85;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:bold;color:white;box-shadow:0 1px 4px rgba(0,0,0,0.4)">${mentions > 1 ? mentions : ''}</div>`,
              iconSize: [radius * 2, radius * 2],
              iconAnchor: [radius, radius],
            });
            const sampleMsgs = point.sample_messages || (point.text ? [{ text: point.text }] : []);
            return (
              <Marker
                key={`${point.message_id}-${idx}`}
                position={[point.location.lat, point.location.lng]}
                icon={circleIcon}
                eventHandlers={{
                  click: () => loadOsintLayers(point.location.lat, point.location.lng),
                }}
              >
                <Popup minWidth={260} maxWidth={320}>
                  <div style={{ fontFamily: 'system-ui, sans-serif' }}>
                    <div style={{ fontWeight: 700, fontSize: '0.95rem', marginBottom: 2 }}>
                      📍 {point.canonical_name || 'Unknown Location'}
                    </div>
                    {point.country && (
                      <div style={{ fontSize: '0.75rem', color: '#888', marginBottom: 6 }}>
                        🌍 {point.country}
                      </div>
                    )}
                    <div style={{ display: 'inline-block', background: `hsl(${hue},80%,45%)`, color: 'white', borderRadius: 10, padding: '2px 10px', fontSize: '0.72rem', fontWeight: 700, marginBottom: sampleMsgs.length ? 8 : 0 }}>
                      {mentions} {mentions === 1 ? 'mention' : 'mentions'}
                    </div>
                    <div style={{ fontSize: '0.68rem', color: '#aaa', marginTop: 4 }}>
                      ↓ OSINT-Layer werden geladen…
                    </div>
                    {sampleMsgs.length > 0 && (
                      <div style={{ borderTop: '1px solid #e9ecef', paddingTop: 6, marginTop: 6 }}>
                        <div style={{ fontSize: '0.68rem', color: '#aaa', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 5 }}>
                          Recent messages
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 180, overflowY: 'auto' }}>
                          {sampleMsgs.map((msg, mi) => (
                            <div key={mi} style={{ background: '#f8f9fa', borderRadius: 6, padding: '5px 8px', borderLeft: '3px solid #4dabf7' }}>
                              <div style={{ fontSize: '0.76rem', color: '#333', lineHeight: 1.4 }}>
                                {msg.text && msg.text.length > 140 ? msg.text.substring(0, 140) + '…' : (msg.text || '—')}
                              </div>
                              {msg.date && (
                                <div style={{ fontSize: '0.65rem', color: '#bbb', marginTop: 3 }}>
                                  {new Date(msg.date).toLocaleDateString('de-DE', { day: '2-digit', month: 'short', year: 'numeric' })}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </Popup>
              </Marker>
            );
          })}
        </MarkerClusterGroup>
      </MapContainer>
    </Box>
  );
};
