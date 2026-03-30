import React, { useState } from 'react';
import { ActionIcon, Group, Tooltip } from '@mantine/core';
import {
  IconLanguage,
  IconPhoto,
  IconTag,
  IconMoodSmile,
  IconMapPin,
  IconMicrophone,
  IconRefresh,
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
  const [loadingAudio, setLoadingAudio] = useState(false);
  const [loadingClassify, setLoadingClassify] = useState(false);
  const [loadingEmotion, setLoadingEmotion] = useState(false);
  const [loadingGeo, setLoadingGeo] = useState(false);

  const hasText = !!message.original_text?.trim();
  const hasImageText = !!message.image_text?.trim();
  const hasAudioText = !!message.audio_text?.trim();
  const hasAnalysisText = !!(message.translated_text?.trim() || message.original_text?.trim() || hasImageText || hasAudioText);
  const isImage = message.media_path && !isAudioFile(message.media_path) && !isVideoFile(message.media_path);
  const isAudioOrVideo = message.media_path && (isAudioFile(message.media_path) || isVideoFile(message.media_path));

  const showTranslate =
    hasText &&
    message.original_language !== 'de' &&
    message.translation_status !== 'completed';

  const showOcr =
    isImage &&
    message.image_analysis_status !== 'completed';

  const showAudioTranscribe =
    isAudioOrVideo &&
    message.audio_transcription_status !== 'completed' &&
    message.audio_transcription_status !== 'pending';

  // A worker ran before, but image_text or audio_text arrived afterwards — offer re-run
  const hasNewSources = (hasImageText || hasAudioText) &&
    !!(message.image_analysis_status === 'completed' || message.audio_transcription_status === 'completed');

  const showClassify =
    hasAnalysisText &&
    (message.classification_status !== 'completed' || hasNewSources);
  const rerunClassify = message.classification_status === 'completed' && hasNewSources;

  const showEmotion =
    hasAnalysisText &&
    (message.emotion_status !== 'completed' || hasNewSources);
  const rerunEmotion = message.emotion_status === 'completed' && hasNewSources;

  const showGeo =
    hasAnalysisText &&
    message.geolocation_status !== 'pending' &&
    (message.geolocation_status !== 'completed' &&
     message.geolocation_status !== 'no_location' &&
     message.geolocation_status !== 'no_coordinates' || hasNewSources);
  const rerunGeo = (message.geolocation_status === 'completed' ||
    message.geolocation_status === 'no_location' ||
    message.geolocation_status === 'no_coordinates') && hasNewSources;

  if (!showTranslate && !showOcr && !showAudioTranscribe && !showClassify && !showEmotion && !showGeo) return null;

  const analysisText = message.translated_text?.trim() || message.original_text?.trim()
    || message.audio_text?.trim() || message.image_text?.trim() || '';

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

      {showAudioTranscribe && (
        <Tooltip label="Transcribe audio">
          <ActionIcon
            size="sm"
            variant="subtle"
            color="orange"
            loading={loadingAudio}
            onClick={() =>
              enqueue(
                'queue/audio',
                {
                  message_id: message.message_id,
                  audio_path: message.media_path,
                  media_type: isVideoFile(message.media_path) ? 'video' : 'audio',
                  translate_transcription: true,
                  owner_id: ownerId,
                  case_id: caseId,
                },
                'Audio transcription',
                message.message_id,
                'audio_transcription_status',
                onStatusChange,
                setLoadingAudio,
              )
            }
          >
            <IconMicrophone size={14} />
          </ActionIcon>
        </Tooltip>
      )}

      {showClassify && (
        <Tooltip label={rerunClassify ? 'Re-classify (new text available)' : 'Classify'}>
          <ActionIcon
            size="sm"
            variant="subtle"
            color="violet"
            opacity={rerunClassify ? 0.6 : 1}
            loading={loadingClassify}
            onClick={() =>
              enqueue(
                'queue/classification',
                { message_id: message.message_id, text: analysisText, owner_id: ownerId, case_id: caseId },
                'Classification',
                message.message_id,
                'classification_status',
                onStatusChange,
                setLoadingClassify,
              )
            }
          >
            {rerunClassify ? <IconRefresh size={14} /> : <IconTag size={14} />}
          </ActionIcon>
        </Tooltip>
      )}

      {showEmotion && (
        <Tooltip label={rerunEmotion ? 'Re-analyse emotions (new text available)' : 'Emotion analysis'}>
          <ActionIcon
            size="sm"
            variant="subtle"
            color="pink"
            opacity={rerunEmotion ? 0.6 : 1}
            loading={loadingEmotion}
            onClick={() =>
              enqueue(
                'queue/emotion',
                { message_id: message.message_id, text: analysisText, owner_id: ownerId, case_id: caseId },
                'Emotion',
                message.message_id,
                'emotion_status',
                onStatusChange,
                setLoadingEmotion,
              )
            }
          >
            {rerunEmotion ? <IconRefresh size={14} /> : <IconMoodSmile size={14} />}
          </ActionIcon>
        </Tooltip>
      )}

      {showGeo && (
        <Tooltip label={rerunGeo ? 'Re-extract locations (new text available)' : 'Extract locations'}>
          <ActionIcon
            size="sm"
            variant="subtle"
            color="teal"
            opacity={rerunGeo ? 0.6 : 1}
            loading={loadingGeo}
            onClick={() =>
              enqueue(
                'queue/geolocation',
                { message_id: message.message_id, text: analysisText, owner_id: ownerId, case_id: caseId },
                'Geolocation',
                message.message_id,
                'geolocation_status',
                onStatusChange,
                setLoadingGeo,
              )
            }
          >
            {rerunGeo ? <IconRefresh size={14} /> : <IconMapPin size={14} />}
          </ActionIcon>
        </Tooltip>
      )}
    </Group>
  );
};
