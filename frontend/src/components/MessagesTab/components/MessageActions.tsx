import React, { useState } from 'react';
import { ActionIcon, Group, Tooltip } from '@mantine/core';
import {
  IconLanguage,
  IconPhoto,
  IconTag,
  IconMoodSmile,
  IconMapPin,
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { authFetch } from '@/utils/authFetch';
import { isAudioFile, isVideoFile } from '../utils';

const apiUrl = import.meta.env.VITE_API_URL;

interface MessageActionsProps {
  message: any;
  caseId: number;
  ownerId: string;
  onStatusChange: (messageId: string, updates: Record<string, string>) => void;
}

async function enqueue(
  endpoint: string,
  payload: object,
  label: string,
  messageId: string,
  statusKey: string,
  onStatusChange: (id: string, updates: Record<string, string>) => void,
  setLoading: (v: boolean) => void,
) {
  setLoading(true);
  try {
    const res = await authFetch(`${apiUrl}/${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Request failed');
    }
    onStatusChange(messageId, { [statusKey]: 'pending' });
    notifications.show({ title: 'Queued', message: `${label} job queued`, color: 'green' });
  } catch (e: any) {
    notifications.show({ title: 'Error', message: e.message || `Failed to queue ${label}`, color: 'red' });
  } finally {
    setLoading(false);
  }
}

export const MessageActions: React.FC<MessageActionsProps> = ({
  message,
  caseId,
  ownerId,
  onStatusChange,
}) => {
  const [loadingTranslate, setLoadingTranslate] = useState(false);
  const [loadingOcr, setLoadingOcr] = useState(false);
  const [loadingClassify, setLoadingClassify] = useState(false);
  const [loadingEmotion, setLoadingEmotion] = useState(false);
  const [loadingGeo, setLoadingGeo] = useState(false);

  const hasText = !!message.original_text?.trim();
  const hasAnalysisText = !!(message.translated_text?.trim() || message.original_text?.trim());
  const isImage = message.media_path && !isAudioFile(message.media_path) && !isVideoFile(message.media_path);

  const showTranslate =
    hasText &&
    message.original_language !== 'de' &&
    message.translation_status !== 'completed';

  const showOcr =
    isImage &&
    message.image_analysis_status !== 'completed';

  const showClassify =
    hasAnalysisText &&
    message.classification_status !== 'completed';

  const showEmotion =
    hasAnalysisText &&
    message.emotion_status !== 'completed';

  const showGeo =
    hasAnalysisText &&
    message.geolocation_status !== 'pending';

  if (!showTranslate && !showOcr && !showClassify && !showEmotion && !showGeo) return null;

  const analysisText = message.translated_text?.trim() || message.original_text || '';

  return (
    <Group gap={4} wrap="nowrap">
      {showTranslate && (
        <Tooltip label="Translate">
          <ActionIcon
            size="sm"
            variant="subtle"
            color="blue"
            loading={loadingTranslate}
            onClick={() =>
              enqueue(
                'queue/translation',
                {
                  message_id: message.message_id,
                  original_text: message.original_text,
                  source_language: message.original_language || 'en',
                  owner_id: ownerId,
                  case_id: caseId,
                },
                'Translation',
                message.message_id,
                'translation_status',
                onStatusChange,
                setLoadingTranslate,
              )
            }
          >
            <IconLanguage size={14} />
          </ActionIcon>
        </Tooltip>
      )}

      {showOcr && (
        <Tooltip label="Run OCR">
          <ActionIcon
            size="sm"
            variant="subtle"
            color="orange"
            loading={loadingOcr}
            onClick={() =>
              enqueue(
                'queue/image',
                {
                  message_id: message.message_id,
                  image_path: message.media_path,
                  extract_text: true,
                  detect_objects: false,
                  translate_extracted_text: true,
                  owner_id: ownerId,
                  case_id: caseId,
                },
                'OCR',
                message.message_id,
                'image_analysis_status',
                onStatusChange,
                setLoadingOcr,
              )
            }
          >
            <IconPhoto size={14} />
          </ActionIcon>
        </Tooltip>
      )}

      {showClassify && (
        <Tooltip label="Classify">
          <ActionIcon
            size="sm"
            variant="subtle"
            color="violet"
            loading={loadingClassify}
            onClick={() =>
              enqueue(
                'queue/classification',
                {
                  message_id: message.message_id,
                  text: analysisText,
                  owner_id: ownerId,
                  case_id: caseId,
                },
                'Classification',
                message.message_id,
                'classification_status',
                onStatusChange,
                setLoadingClassify,
              )
            }
          >
            <IconTag size={14} />
          </ActionIcon>
        </Tooltip>
      )}

      {showEmotion && (
        <Tooltip label="Emotion analysis">
          <ActionIcon
            size="sm"
            variant="subtle"
            color="pink"
            loading={loadingEmotion}
            onClick={() =>
              enqueue(
                'queue/emotion',
                {
                  message_id: message.message_id,
                  text: analysisText,
                  owner_id: ownerId,
                  case_id: caseId,
                },
                'Emotion',
                message.message_id,
                'emotion_status',
                onStatusChange,
                setLoadingEmotion,
              )
            }
          >
            <IconMoodSmile size={14} />
          </ActionIcon>
        </Tooltip>
      )}

      {showGeo && (
        <Tooltip label="Extract locations">
          <ActionIcon
            size="sm"
            variant="subtle"
            color="teal"
            loading={loadingGeo}
            onClick={() =>
              enqueue(
                'queue/geolocation',
                {
                  message_id: message.message_id,
                  text: analysisText,
                  owner_id: ownerId,
                  case_id: caseId,
                },
                'Geolocation',
                message.message_id,
                'geolocation_status',
                onStatusChange,
                setLoadingGeo,
              )
            }
          >
            <IconMapPin size={14} />
          </ActionIcon>
        </Tooltip>
      )}
    </Group>
  );
};
