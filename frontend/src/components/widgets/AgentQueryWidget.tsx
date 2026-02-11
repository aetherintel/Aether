import React from 'react';
import { Box } from '@mantine/core';
import { WidgetComponentProps } from '@/types/widgets.types';
import { AgentChat } from '../Agent/AgentChat';

export const AgentQueryWidget: React.FC<WidgetComponentProps> = ({ widget }) => {
  return (
    <Box h="100%" style={{ overflow: 'hidden' }} p="xs">
      <AgentChat embedded />
    </Box>
  );
};
