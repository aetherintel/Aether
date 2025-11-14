// src/components/WidgetGrid/WidgetContainer.tsx
import React, { useState, Suspense, lazy } from 'react';
import {
  Paper,
  Group,
  Title,
  ActionIcon,
  Menu,
  LoadingOverlay,
  Text,
  Badge,
  Tooltip,
  Box,
  Modal,
} from '@mantine/core';
import {
  IconSettings,
  IconCopy,
  IconTrash,
  IconDots,
  IconRefresh,
  IconMaximize,
  IconMinimize,
  IconEdit,
} from '@tabler/icons-react';
import { Widget, WidgetComponentProps } from '@/types/widgets.types';
import { widgetRegistry } from '../../lib/widgets/widgetRegistry';
import { useWidgetStore } from '@/store/client/widgetStore';
import { WidgetConfigModal } from '@/components/WidgetGrid/WidgetConfigModal';
import { SimpleErrorBoundary } from './SimpleErrorBoundary';
import classes from './WidgetContainer.module.css';

interface WidgetContainerProps {
  widget: Widget;
  isEditing: boolean;
  isSelected: boolean;
  onSelect: () => void;
  onRemove: () => void;
  onDuplicate: () => void;
  channelId?: string;
}

// Error fallback component
const WidgetErrorFallback: React.FC<{ error: Error; resetErrorBoundary: () => void }> = ({
  error,
  resetErrorBoundary,
}) => (
  <Box p="md" className={classes.errorContainer}>
    <Text c="red" fw={500} mb="xs">Widget Error</Text>
    <Text size="sm" c="dimmed">{error.message}</Text>
    <ActionIcon 
      variant="subtle" 
      onClick={resetErrorBoundary} 
      mt="sm"
      title="Retry"
    >
      <IconRefresh size={16} />
    </ActionIcon>
  </Box>
);

export const WidgetContainer: React.FC<WidgetContainerProps> = ({
  widget,
  isEditing,
  isSelected,
  onSelect,
  onRemove,
  onDuplicate,
  channelId,
}) => {
  const [configModalOpen, setConfigModalOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  const { updateWidget, updateWidgetConfig } = useWidgetStore();
  
  // Get widget definition from registry
  const widgetDefinition = widgetRegistry.get(widget.type);
  
  if (!widgetDefinition) {
    return (
      <Paper withBorder p="md" className={classes.container}>
        <Text c="red">Unknown widget type: {widget.type}</Text>
      </Paper>
    );
  }

  const WidgetComponent = widgetDefinition.component;
  const IconComponent = widgetDefinition.icon;

  // Handle widget refresh
  const handleRefresh = async () => {
    setIsRefreshing(true);
    // Trigger re-render by updating lastUpdated
    const layoutId = useWidgetStore.getState().activeLayoutId;
    if (layoutId) {
      updateWidget(layoutId, widget.id, { lastUpdated: new Date() });
    }
    setTimeout(() => setIsRefreshing(false), 1000);
  };

  // Handle config update
  const handleConfigUpdate = (config: any) => {
    const layoutId = useWidgetStore.getState().activeLayoutId;
    if (layoutId) {
      updateWidgetConfig(layoutId, widget.id, config);
    }
  };

  // Handle title update
  const handleTitleUpdate = (title: string) => {
    const layoutId = useWidgetStore.getState().activeLayoutId;
    if (layoutId) {
      updateWidget(layoutId, widget.id, { title });
    }
  };

  // Component props
  const widgetProps: WidgetComponentProps = {
    widget,
    onUpdate: handleConfigUpdate,
    onRemove,
    isEditing,
  };

  return (
    <>
      <Paper
        withBorder
        className={`${classes.container} ${isSelected ? classes.selected : ''} ${
          isEditing ? classes.editing : ''
        }`}
        onClick={isEditing ? onSelect : undefined}
      >
        <LoadingOverlay visible={isRefreshing || widget.isLoading} />
        
        {/* Widget Header */}
        <Group justify="space-between" className={classes.header} mb="sm">
          <Group gap="xs">
            <IconComponent />
            <Title order={6} className={classes.title}>
              {widget.title}
            </Title>
            {widget.error && (
              <Badge color="red" size="xs">Error</Badge>
            )}
          </Group>
          
          <Group gap={4}>
            {/* Refresh Button */}
            {!isEditing && widget.config.refreshInterval && (
              <Tooltip label="Refresh">
                <ActionIcon
                  variant="subtle"
                  size="sm"
                  onClick={handleRefresh}
                >
                  <IconRefresh size={14} />
                </ActionIcon>
              </Tooltip>
            )}
            
            {/* Fullscreen Button */}
            {!isEditing && (
              <Tooltip label={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}>
                <ActionIcon
                  variant="subtle"
                  size="sm"
                  onClick={() => setIsFullscreen(!isFullscreen)}
                >
                  {isFullscreen ? <IconMinimize size={14} /> : <IconMaximize size={14} />}
                </ActionIcon>
              </Tooltip>
            )}
            
            {/* Options Menu */}
            <Menu position="bottom-end" withArrow>
              <Menu.Target>
                <ActionIcon variant="subtle" size="sm">
                  <IconDots size={14} />
                </ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item
                  leftSection={<IconSettings size={14} />}
                  onClick={() => setConfigModalOpen(true)}
                >
                  Configure
                </Menu.Item>
                <Menu.Item
                  leftSection={<IconEdit size={14} />}
                  onClick={() => {
                    const newTitle = prompt('Enter new title:', widget.title);
                    if (newTitle) handleTitleUpdate(newTitle);
                  }}
                >
                  Rename
                </Menu.Item>
                <Menu.Item
                  leftSection={<IconCopy size={14} />}
                  onClick={onDuplicate}
                >
                  Duplicate
                </Menu.Item>
                <Menu.Divider />
                <Menu.Item
                  leftSection={<IconTrash size={14} />}
                  color="red"
                  onClick={onRemove}
                >
                  Remove
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        </Group>
        
        {/* Widget Content */}
        <Box className={classes.content}>
          <SimpleErrorBoundary>
            <Suspense fallback={<LoadingOverlay visible />}>
              <WidgetComponent {...widgetProps} />
            </Suspense>
          </SimpleErrorBoundary>
        </Box>
      </Paper>

      {/* Configuration Modal */}
      <WidgetConfigModal
        opened={configModalOpen}
        onClose={() => setConfigModalOpen(false)}
        widget={widget}
        definition={widgetDefinition}
        onSave={handleConfigUpdate}
      />

      {/* Fullscreen Modal */}
      <Modal
        opened={isFullscreen}
        onClose={() => setIsFullscreen(false)}
        fullScreen
        title={widget.title}
      >
        <Box h="calc(100vh - 80px)">
          <SimpleErrorBoundary>
            <Suspense fallback={<LoadingOverlay visible />}>
              <WidgetComponent {...widgetProps} />
            </Suspense>
          </SimpleErrorBoundary>
        </Box>
      </Modal>
    </>
  );
};