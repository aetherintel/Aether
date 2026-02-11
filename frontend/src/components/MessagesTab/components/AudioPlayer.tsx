import React, { useState } from 'react';
import { Box, Badge, Popover, Group, Text, Button, Textarea } from '@mantine/core';
import { IconVolume } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { authFetch } from '@/utils/authFetch';

interface AudioPlayerProps {
  mediaPath: string;
  audioText: string;
  audioTextTranslated: string;
  audioTranscriptionStatus: string;
  messageId: string;
  mediaType: string;
  showAudioTranscripts: boolean;
  apiUrl: string;
}

export const AudioPlayer: React.FC<AudioPlayerProps> = ({
  mediaPath,
  audioText,
  audioTextTranslated,
  audioTranscriptionStatus,
  messageId,
  mediaType,
  showAudioTranscripts,
  apiUrl,
}) => {
  const [opened, setOpened] = useState(false);
  const [isPinned, setIsPinned] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);
  const [isTriggering, setIsTriggering] = useState(false);

  const hasTranscript = audioText && audioText.trim().length > 0;
  const hasTranslation = audioTextTranslated && audioTextTranslated.trim().length > 0;
  const needsProcessing = audioTranscriptionStatus === 'none';
  const isProcessing = audioTranscriptionStatus === 'pending';

  const handleMouseEnter = () => { if (!isPinned) setOpened(true); };
  const handleMouseLeave = () => { if (!isPinned) setOpened(false); };
  const handleClick = () => { setIsPinned(!isPinned); setOpened(true); };
  const handleClose = () => { setIsPinned(false); setOpened(false); };

  const handleTriggerAudioTranscription = async () => {
    setIsTriggering(true);
    try {
      const response = await authFetch(`${apiUrl}/queue/audio-transcription`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: messageId, media_path: mediaPath, media_type: mediaType || 'audio', translate_transcription: true }),
      });
      if (!response.ok) throw new Error('Failed to trigger audio transcription');
      notifications.show({ title: 'Success', message: 'Audio transcription job queued', color: 'green' });
    } catch (error: any) {
      notifications.show({ title: 'Error', message: error.message || 'Failed to trigger audio transcription', color: 'red' });
    } finally { setIsTriggering(false); }
  };

  return (
    <Box style={{ position: 'relative', minWidth: 200 }}>
      <audio src={mediaPath} controls style={{ width: '100%', maxWidth: 300 }}>Your browser does not support the audio element.</audio>

      {showAudioTranscripts && needsProcessing && (
        <Box onClick={handleTriggerAudioTranscription} style={{ position: 'absolute', top: -8, right: 4, cursor: 'pointer' }}>
          <Badge leftSection={<IconVolume size={12} />} color="orange" variant="filled" size="sm">
            {isTriggering ? 'Starting...' : 'No Transcript'}
          </Badge>
        </Box>
      )}

      {showAudioTranscripts && isProcessing && (
        <Box style={{ position: 'absolute', top: -8, right: 4 }}>
          <Badge leftSection={<IconVolume size={12} />} color="yellow" variant="filled" size="sm">Processing...</Badge>
        </Box>
      )}

      {showAudioTranscripts && hasTranscript && (
        <Popover width={300} position="bottom" withArrow shadow="md" opened={opened} onChange={setOpened}>
          <Popover.Target>
            <Box onMouseEnter={handleMouseEnter} onMouseLeave={handleMouseLeave} onClick={handleClick}
                 style={{ position: 'absolute', top: -8, right: 4, cursor: 'pointer' }}>
              <Badge leftSection={<IconVolume size={12} />} color={isPinned ? 'teal' : 'grape'} variant="filled" size="sm">Transcript</Badge>
            </Box>
          </Popover.Target>
          <Popover.Dropdown style={{ maxHeight: 400, overflowY: 'auto' }}>
            <Box>
              <Group justify="space-between" mb="xs">
                <Text size="sm" fw={500}>Audio Transcript</Text>
                <Group gap="xs">
                  {hasTranslation && (
                    <Button variant="subtle" size="xs" onClick={() => setShowOriginal(!showOriginal)}>
                      {showOriginal ? 'DE' : 'Original'}
                    </Button>
                  )}
                  {isPinned && <Button variant="subtle" size="xs" onClick={handleClose}>Close</Button>}
                </Group>
              </Group>
              <Textarea value={showOriginal || !hasTranslation ? audioText : audioTextTranslated} readOnly autosize minRows={3} maxRows={15}
                        styles={{ input: { fontSize: '0.875rem', backgroundColor: 'var(--mantine-color-gray-0)' } }} />
            </Box>
          </Popover.Dropdown>
        </Popover>
      )}
    </Box>
  );
};
