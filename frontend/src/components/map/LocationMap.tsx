// src/components/map/LocationMap.tsx
// Shared map component used by LocationMapWidget (dashboard) and AgentChat.
import React, { useEffect, useState } from 'react';
import { Box, Group, Badge, ActionIcon, Tooltip, Loader, Button } from '@mantine/core';
import { IconRefresh, IconSettings } from '@tabler/icons-react';
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
import { authFetch } from '@/utils/authFetch';
import { OSINT_ICONS, OSINT_LABELS } from '@/utils/osintIcons';

const ESRI_API_KEY = import.meta.env.VITE_ESRI_API_KEY ?? '';
const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api';

// Fix Leaflet default icon (safe to call multiple times)
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

export interface MapPoint {
  /** Used as React key */
  id: string;
  lat: number;
  lng: number;
  canonical_name?: string;
  country?: string;
  mention_count?: number;
  sample_messages?: Array<{ text: string; date?: string }>;
}

type OsintItem = {
  id: number;
  lat: number;
  lng: number;
  name: string;
  operator: string;
  tags: Record<string, string>;
};
type OsintData = Record<string, OsintItem[]>;

interface LocationMapProps {
  points: MapPoint[];
  /** Show refresh button (dashboard widget mode) */
  onRefresh?: () => void;
  /** Height of the map container */
  height?: number | string;
}

// ── FitBounds ────────────────────────────────────────────────
const FitBounds: React.FC<{ points: MapPoint[] }> = ({ points }) => {
  const map = useMap();
  useEffect(() => {
    if (points.length > 0) {
      map.fitBounds(
        L.latLngBounds(points.map(p => [p.lat, p.lng])),
        { padding: [50, 50] },
      );
    }
  }, [points, map]);
  return null;
};

// ── Main component ────────────────────────────────────────────
export const LocationMap: React.FC<LocationMapProps> = ({
  points,
  onRefresh,
  height = '100%',
}) => {
  const [osintData, setOsintData] = useState<OsintData>({});
  const [loadingOsint, setLoadingOsint] = useState(false);
  // Track which coordinate was last loaded so we can show a button for the first point too
  const [osintCenter, setOsintCenter] = useState<{ lat: number; lng: number } | null>(null);

  const loadOsintLayers = async (lat: number, lng: number) => {
    setLoadingOsint(true);
    setOsintCenter({ lat, lng });
    try {
      const res = await authFetch(
        `${apiUrl}/geo/osint-layers?lat=${lat}&lng=${lng}&radius=500` +
        `&layers=cameras,atm,bank,police,military,power,water,alpr`,
      );
      const data: OsintData = await res.json();
      console.log('[OSINT] received:', JSON.stringify(Object.fromEntries(Object.entries(data).map(([k,v]) => [k, v.length]))));
      setOsintData(data);
    } catch (err) {
      console.error('Failed to load OSINT layers:', err);
    } finally {
      setLoadingOsint(false);
    }
  };

  const satelliteUrl = ESRI_API_KEY
    ? `https://ibasemaps-api.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}?token=${ESRI_API_KEY}`
    : null;

  const hasOsint = Object.values(osintData).some(items => items.length > 0);
  const firstPoint = points[0];

  return (
    <Box style={{ display: 'flex', flexDirection: 'column', height, width: '100%' }}>
      {/* ── Toolbar — sits above the map, no z-index/overflow fights ── */}
      <Group
        gap="xs"
        justify="flex-end"
        style={{ padding: '4px 6px', flexShrink: 0 }}
      >
        {loadingOsint && <Loader size="xs" />}

        <Badge size="sm" variant="light">
          {points.length} locations
        </Badge>

        {firstPoint && (
          <Tooltip label={hasOsint ? 'OSINT aktualisieren' : 'OSINT Layer laden'} withArrow>
            <Button
              size="xs"
              variant="filled"
              color="dark"
              loading={loadingOsint}
              leftSection={<IconSettings size={13} />}
              onClick={() => loadOsintLayers(
                osintCenter?.lat ?? firstPoint.lat,
                osintCenter?.lng ?? firstPoint.lng,
              )}
            >
              OSINT
            </Button>
          </Tooltip>
        )}

        {onRefresh && (
          <Tooltip label="Refresh" withArrow>
            <ActionIcon variant="filled" size="md" onClick={onRefresh}>
              <IconRefresh size={14} />
            </ActionIcon>
          </Tooltip>
        )}
      </Group>

      {/* ── Map fills remaining height ── */}
      <Box style={{ flex: 1, minHeight: 0, borderRadius: '8px', overflow: 'hidden' }}>
        <MapContainer
        center={[51.1657, 10.4515]}
        zoom={6}
        style={{ height: '100%', width: '100%' }}
        zoomControl={true}
      >
        <LayersControl position="bottomleft">
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
                attribution="Tiles &copy; Esri &mdash; Maxar, Earthstar Geographics"
                maxZoom={19}
              />
            </LayersControl.BaseLayer>
          )}

        </LayersControl>

        {/* ── OSINT Overlays — rendered outside LayersControl so dynamic updates work ── */}
        {Object.entries(osintData).map(([layer, items]) =>
          items && items.length > 0 ? (
            <LayerGroup key={layer}>
              {items.map(item =>
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
              )}
            </LayerGroup>
          ) : null
        )}

        <FitBounds points={points} />

        {/* ── Location markers ── */}
        <MarkerClusterGroup>
          {points.map((point, idx) => {
            const mentions = point.mention_count ?? 1;
            const radius = Math.min(Math.max(8 + Math.sqrt(mentions) * 2, 10), 36);
            const hue = Math.max(0, 120 - mentions * 4);
            const circleIcon = L.divIcon({
              className: '',
              html: `<div style="width:${radius * 2}px;height:${radius * 2}px;border-radius:50%;background:hsl(${hue},80%,50%);border:2px solid white;opacity:0.85;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:bold;color:white;box-shadow:0 1px 4px rgba(0,0,0,0.4)">${mentions > 1 ? mentions : ''}</div>`,
              iconSize: [radius * 2, radius * 2],
              iconAnchor: [radius, radius],
            });
            const sampleMsgs = point.sample_messages ?? [];
            return (
              <Marker
                key={`${point.id}-${idx}`}
                position={[point.lat, point.lng]}
                icon={circleIcon}
                eventHandlers={{ click: () => loadOsintLayers(point.lat, point.lng) }}
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
                      ↓ Klicken um OSINT-Layer zu laden
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
                                {msg.text && msg.text.length > 140
                                  ? msg.text.substring(0, 140) + '…'
                                  : (msg.text || '—')}
                              </div>
                              {msg.date && (
                                <div style={{ fontSize: '0.65rem', color: '#bbb', marginTop: 3 }}>
                                  {new Date(msg.date).toLocaleDateString('de-DE', {
                                    day: '2-digit', month: 'short', year: 'numeric',
                                  })}
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
    </Box>
  );
};
