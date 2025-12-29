import React, { useState } from 'react';
import { Box, Badge, Popover, Group, Text, Button, Textarea } from '@mantine/core';
import { IconPhoto } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { ImageLightbox } from '@/components/ImageLightbox';
import { authFetch } from '@/utils/authFetch';

interface ImageWithTranscriptProps {
  mediaPath: string;
  imageText: string;
  imageTextTranslated: string;
  imageAnalysisStatus: string;
  messageId: string;
  showImageTranscripts: boolean;
  apiUrl: string;
}

export const ImageWithTranscript: React.FC<ImageWithTranscriptProps> = ({
  mediaPath,
  imageText,
  imageTextTranslated,
  imageAnalysisStatus,
  messageId,
  showImageTranscripts,
  apiUrl,
}) => {
  const [opened, setOpened] = useState(false);
  const [isPinned, setIsPinned] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);
  const [isTriggering, setIsTriggering] = useState(false);

  const hasTranscript = imageText && imageText.trim().length > 0;
  const hasTranslation = imageTextTranslated && imageTextTranslated.trim().length > 0;
  const needsProcessing = imageAnalysisStatus === 'none';
  const isProcessing = imageAnalysisStatus === 'pending';

  const handleMouseEnter = () => { if (!isPinned) setOpened(true); };
  const handleMouseLeave = () => { if (!isPinned) setOpened(false); };
  const handleClick = () => { setIsPinned(!isPinned); setOpened(true); };
  const handleClose = () => { setIsPinned(false); setOpened(false); };

  const handleTriggerImageAnalysis = async () => {
    setIsTriggering(true);
    try {
      const response = await authFetch(`${apiUrl}/queue/image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message_id: messageId,
          image_path: mediaPath,
          extract_text: true,
          detect_objects: false,
          translate_extracted_text: true,
        }),
      });
      if (!response.ok) throw new Error('Failed to trigger image analysis');
      notifications.show({ title: 'Success', message: 'Image analysis job queued', color: 'green' });
    } catch (error: any) {
      notifications.show({ title: 'Error', message: error.message || 'Failed to trigger image analysis', color: 'red' });
    } finally { setIsTriggering(false); }
  };

  return (
    <Box style={{ position: 'relative' }}>
      <ImageLightbox image={mediaPath} thumbnailWidth={200} thumbnailHeight={120} />
      
      {showImageTranscripts && needsProcessing && (
        <Box onClick={handleTriggerImageAnalysis} style={{ position: 'absolute', top: 4, right: 4, cursor: 'pointer' }}>
          <Badge leftSection={<IconPhoto size={12} />} color="orange" variant="filled" size="sm">
            {isTriggering ? 'Starting...' : 'No Transcript'}
          </Badge>
        </Box>
      )}

      {showImageTranscripts && isProcessing && (
        <Box style={{ position: 'absolute', top: 4, right: 4 }}>
          <Badge leftSection={<IconPhoto size={12} />} color="yellow" variant="filled" size="sm">Processing...</Badge>
        </Box>
      )}
      
      {showImageTranscripts && hasTranscript && (
        <Popover width={300} position="bottom" withArrow shadow="md" opened={opened} onChange={setOpened}>
          <Popover.Target>
            <Box onMouseEnter={handleMouseEnter} onMouseLeave={handleMouseLeave} onClick={handleClick}
                 style={{ position: 'absolute', top: 4, right: 4, cursor: 'pointer' }}>
              <Badge leftSection={<IconPhoto size={12} />} color={isPinned ? 'teal' : 'blue'} variant="filled" size="sm">Transcript</Badge>
            </Box>
          </Popover.Target>
          <Popover.Dropdown style={{ maxHeight: 400, overflowY: 'auto' }}>
            <Box>
              <Group justify="space-between" mb="xs">
                <Text size="sm" fw={500}>Image Transcript</Text>
                <Group gap="xs">
                  {hasTranslation && (
                    <Button variant="subtle" size="xs" onClick={() => setShowOriginal(!showOriginal)}>
                      {showOriginal ? 'DE' : 'Original'}
                    </Button>
                  )}
                  {isPinned && <Button variant="subtle" size="xs" onClick={handleClose}>Close</Button>}
                </Group>
              </Group>
              <Textarea value={showOriginal || !hasTranslation ? imageText : imageTextTranslated} readOnly autosize minRows={3} maxRows={15}
                        styles={{ input: { fontSize: '0.875rem', backgroundColor: 'var(--mantine-color-gray-0)' } }} />
            </Box>
          </Popover.Dropdown>
        </Popover>
      )}
    </Box>
  );
};
