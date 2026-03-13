import React, { useState, useEffect } from 'react';
import {
  ActionIcon,
  Badge,
  Box,
  Collapse,
  Group,
  Loader,
  Text,
  Tooltip,
} from '@mantine/core';
import {
  IconChevronDown,
  IconChevronRight,
  IconMapPin,
  IconMoodSmile,
  IconTag,
} from '@tabler/icons-react';
import { authFetch } from '@/utils/authFetch';

interface Emotion {
  label: string;
  confidence: number;
  source_emotions?: string[];
}

interface Classification {
  label: string;
  description?: string;
  confidence: number;
}

interface Location {
  name: string;
  country?: string;
  lat?: number;
  lng?: number;
}

interface Enrichment {
  emotions: Emotion[];
  classifications: Classification[];
  locations: Location[];
}

interface MessageEnrichmentProps {
  messageId: string;
  emotionStatus?: string;
  classificationStatus?: string;
  geolocationStatus?: string;
  apiUrl: string;
}

const EMOTION_COLORS: Record<string, string> = {
  freude: 'yellow',
  trauer: 'blue',
  wut: 'red',
  angst: 'grape',
  ekel: 'green',
  überraschung: 'cyan',
  verachtung: 'orange',
  default: 'gray',
};

function emotionColor(label: string): string {
  return EMOTION_COLORS[label.toLowerCase()] ?? EMOTION_COLORS.default;
}

export const MessageEnrichment: React.FC<MessageEnrichmentProps> = ({
  messageId,
  emotionStatus,
  classificationStatus,
  geolocationStatus,
  apiUrl,
}) => {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<Enrichment | null>(null);

  const hasEmotions = emotionStatus === 'completed';
  const hasClassifications = classificationStatus === 'completed';
  const hasLocation = geolocationStatus === 'completed';

  // When a new analysis completes via SSE, clear cached data so the next open re-fetches
  useEffect(() => {
    setData(null);
  }, [emotionStatus, classificationStatus, geolocationStatus]);

  if (!hasEmotions && !hasClassifications && !hasLocation) return null;

  const toggle = async () => {
    if (!open && !data) {
      setLoading(true);
      try {
        const res = await authFetch(`${apiUrl}/messages/${messageId}/enrichment`);
        setData(await res.json());
      } catch {
        setData({ emotions: [], classifications: [], locations: [] });
      } finally {
        setLoading(false);
      }
    }
    setOpen((o) => !o);
  };

  return (
    <Box mt={4}>
      {/* Summary row — always visible */}
      <Group gap={4} style={{ cursor: 'pointer' }} onClick={toggle}>
        {hasEmotions && (
          <Tooltip label="Emotions analysiert">
            <Badge size="xs" variant="dot" color="pink" leftSection={<IconMoodSmile size={10} />}>
              Emotion
            </Badge>
          </Tooltip>
        )}
        {hasClassifications && (
          <Tooltip label="Klassifiziert">
            <Badge size="xs" variant="dot" color="violet" leftSection={<IconTag size={10} />}>
              Klassifikation
            </Badge>
          </Tooltip>
        )}
        {hasLocation && (
          <Tooltip label="Orte erkannt">
            <Badge size="xs" variant="dot" color="teal" leftSection={<IconMapPin size={10} />}>
              Geo
            </Badge>
          </Tooltip>
        )}
        <ActionIcon size="xs" variant="subtle" color="gray">
          {open ? <IconChevronDown size={12} /> : <IconChevronRight size={12} />}
        </ActionIcon>
      </Group>

      {/* Expanded detail panel */}
      <Collapse in={open}>
        <Box pt={6} pl={4} style={{ borderLeft: '2px solid var(--mantine-color-gray-3)' }}>
          {loading && <Loader size="xs" />}

          {data && (
            <>
              {/* Emotions */}
              {data.emotions.length > 0 && (
                <Box mb={6}>
                  <Text size="xs" c="dimmed" fw={600} mb={3}>Emotionen</Text>
                  <Group gap={4} wrap="wrap">
                    {data.emotions.map((e, i) => (
                      <Tooltip
                        key={i}
                        label={e.source_emotions?.length ? `Quell-Emotionen: ${e.source_emotions.join(', ')}` : ''}
                        disabled={!e.source_emotions?.length}
                      >
                        <Badge size="sm" color={emotionColor(e.label)} variant="light">
                          {e.label}{' '}
                          <Text span size="xs" c="dimmed">
                            {Math.round(e.confidence * 100)}%
                          </Text>
                        </Badge>
                      </Tooltip>
                    ))}
                  </Group>
                </Box>
              )}

              {/* Classifications */}
              {data.classifications.length > 0 && (
                <Box mb={6}>
                  <Text size="xs" c="dimmed" fw={600} mb={3}>Klassifikation</Text>
                  <Group gap={4} wrap="wrap">
                    {data.classifications.map((c, i) => (
                      <Tooltip key={i} label={c.description || ''} disabled={!c.description}>
                        <Badge size="sm" color="violet" variant="light">
                          {c.label}{' '}
                          <Text span size="xs" c="dimmed">
                            {Math.round(c.confidence * 100)}%
                          </Text>
                        </Badge>
                      </Tooltip>
                    ))}
                  </Group>
                </Box>
              )}

              {/* Locations */}
              {data.locations.length > 0 && (
                <Box>
                  <Text size="xs" c="dimmed" fw={600} mb={3}>Orte</Text>
                  <Group gap={4} wrap="wrap">
                    {data.locations.map((loc, i) => (
                      <Badge key={i} size="sm" color="teal" variant="light" leftSection={<IconMapPin size={10} />}>
                        {loc.name}{loc.country ? `, ${loc.country}` : ''}
                      </Badge>
                    ))}
                  </Group>
                </Box>
              )}

              {data.emotions.length === 0 && data.classifications.length === 0 && data.locations.length === 0 && (
                <Text size="xs" c="dimmed">Keine Details verfügbar.</Text>
              )}
            </>
          )}
        </Box>
      </Collapse>
    </Box>
  );
};
