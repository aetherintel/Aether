// src/components/WidgetGrid/WidgetAddModal.tsx
import React, { useState } from 'react';
import {
  Modal,
  SimpleGrid,
  Card,
  Text,
  Badge,
  Group,
  Stack,
  Button,
  TextInput,
  ActionIcon,
} from '@mantine/core';
import { IconSearch, IconPlus } from '@tabler/icons-react';
import { widgetRegistry } from '../../lib/widgets/widgetRegistry';
import { useWidgetStore } from '@/store/client/widgetStore';
import { WidgetType } from '@/types/widgets.types';
import classes from './WidgetAddModal.module.css';

interface WidgetAddModalProps {
  opened: boolean;
  onClose: () => void;
  category?: 'dashboard' | 'channel';
  layoutId: string;
}

export const WidgetAddModal: React.FC<WidgetAddModalProps> = ({
  opened,
  onClose,
  category = 'dashboard',
  layoutId,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const { addWidget } = useWidgetStore();
  
  const availableWidgets = widgetRegistry
    .getByCategory(category)
    .filter(widget => 
      widget.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      widget.description.toLowerCase().includes(searchQuery.toLowerCase())
    );

  const handleAddWidget = (type: WidgetType) => {
    if (layoutId) {
      addWidget(layoutId, type);
      onClose();
    }
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title="Add Widget"
      size="lg"
    >
      <Stack>
        <TextInput
          placeholder="Search widgets..."
          leftSection={<IconSearch size={16} />}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.currentTarget.value)}
        />
        
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          {availableWidgets.map((widget) => {
            const IconComponent = widget.icon as React.ComponentType<{ size?: number }>;
            
            return (
              <Card
                key={widget.type}
                withBorder
                padding="md"
                className={classes.widgetCard}
              >
                <Group justify="space-between" mb="xs">
                  <Group gap="xs">
                    <IconComponent size={24} />
                    <Text fw={500}>{widget.name}</Text>
                  </Group>
                  <ActionIcon
                    variant="filled"
                    onClick={() => handleAddWidget(widget.type)}
                    title="Add Widget"
                  >
                    <IconPlus size={16} />
                  </ActionIcon>
                </Group>
                
                <Text size="sm" c="dimmed" mb="sm">
                  {widget.description}
                </Text>
                
                <Group gap="xs">
                  <Badge size="xs" variant="light">
                    {widget.defaultSize.w}x{widget.defaultSize.h}
                  </Badge>
                  {widget.categories.map(cat => (
                    <Badge key={cat} size="xs" variant="dot">
                      {cat}
                    </Badge>
                  ))}
                </Group>
              </Card>
            );
          })}
        </SimpleGrid>
        
        {availableWidgets.length === 0 && (
          <Text c="dimmed" ta="center" py="xl">
            No widgets found matching your search
          </Text>
        )}
      </Stack>
    </Modal>
  );
};