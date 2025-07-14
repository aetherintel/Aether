import React, { useState } from 'react';
import { IconX } from '@tabler/icons-react';
import { ActionIcon, Box, Image, Modal } from '@mantine/core';

interface ImageLightboxProps {
  image: string;
  thumbnailWidth?: number | string;
  thumbnailHeight?: number | string;
  className?: string;
  style?: React.CSSProperties;
}

const ImageLightbox: React.FC<ImageLightboxProps> = ({
  image,
  thumbnailWidth = '100%',
  thumbnailHeight = 'auto',
  className,
  style,
}) => {
  const [opened, setOpened] = useState<boolean>(false);

  const openLightbox = (): void => {
    setOpened(true);
  };

  const closeLightbox = (): void => {
    setOpened(false);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>): void => {
    if (event.key === 'Escape') {
      closeLightbox();
    }
  };

  const handleMouseEnter = (e: React.MouseEvent<HTMLDivElement>): void => {
    const target = e.currentTarget;
    target.style.transform = 'scale(1.02)';
    target.style.boxShadow = '0 8px 32px rgba(0,0,0,0.12)';
  };

  const handleMouseLeave = (e: React.MouseEvent<HTMLDivElement>): void => {
    const target = e.currentTarget;
    target.style.transform = 'scale(1)';
    target.style.boxShadow = 'none';
  };

  return (
    <>
      {/* Thumbnail Image */}
      <Box
        className={className}
        style={{
          cursor: 'pointer',
          borderRadius: '8px',
          overflow: 'hidden',
          transition: 'transform 0.2s ease, box-shadow 0.2s ease',
          display: 'inline-block',
          minWidth: thumbnailWidth,
          width: thumbnailWidth,
          height: thumbnailHeight,
          ...style,
        }}
        onClick={openLightbox}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        <Image
          src={image}
          alt={image}
          fallbackSrc="https://placehold.co/600x360?text=Not downloaded yet"
          fit="cover"
          style={{
            width: '100%',
            height: '100%',
          }}
        />
      </Box>

      {/* Lightbox Modal */}
      <Modal
        opened={opened}
        onClose={closeLightbox}
        size="90%"
        padding={0}
        centered
        withCloseButton={false}
        overlayProps={{
          backgroundOpacity: 0.9,
          blur: 3,
        }}
        onKeyDown={handleKeyDown}
        tabIndex={-1}
      >
        <Box pos="relative" style={{ minHeight: '60vh' }}>
          {/* Close Button */}
          <ActionIcon
            pos="absolute"
            top={16}
            right={16}
            size="lg"
            variant="filled"
            color="dark"
            style={{ zIndex: 1000 }}
            onClick={closeLightbox}
          >
            <IconX size={18} />
          </ActionIcon>

          {/* Main Image */}
          <Image
            src={image}
            alt={image}
            fit="cover"
            style={{
              height: '100%',
              width: '100%',
            }}
          />
        </Box>
      </Modal>
    </>
  );
};

export { ImageLightbox };
