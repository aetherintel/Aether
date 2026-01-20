import React from 'react';
import { Box } from '@mantine/core';
import { WidgetComponentProps } from '@/types/widgets.types';
import { AgentQueryInterface } from '../Dashboard/AgentQueryInterface';

export const AgentQueryWidget: React.FC<WidgetComponentProps> = ({ widget }) => {
  return (
    <Box h="100%" style={{ overflow: 'hidden' }} p="xs">
      <AgentQueryInterface embedded />
    </Box>
  );
};
