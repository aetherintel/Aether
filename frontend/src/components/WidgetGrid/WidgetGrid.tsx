// src/components/WidgetGrid/WidgetGrid.tsx
import React, { useState, useCallback, useMemo } from 'react';
import { Responsive, WidthProvider, Layout } from 'react-grid-layout';
import { 
  Box, 
  Button, 
  Group, 
  ActionIcon, 
  Tooltip, 
  Menu,
  Modal,
  TextInput,
  Select,
  Paper,
  Text,
  Badge,
  Switch,
  useMantineTheme
} from '@mantine/core';
import { 
  IconPlus, 
  IconEdit, 
  IconDeviceFloppy, 
  IconX,
  IconSettings,
  IconCopy,
  IconTrash,
  IconDots,
  IconLayout,
  IconDownload,
  IconUpload
} from '@tabler/icons-react';
import { useWidgetStore } from '@/store/client/widgetStore';
import { widgetRegistry } from '@/lib/widgets/widgetRegistry';
import { Widget, WidgetType } from '@/types/widgets.types';
import { WidgetContainer } from './WidgetContainer';
import { WidgetAddModal } from './WidgetAddModal';
import { notifications } from '@mantine/notifications';

// CSS imports for react-grid-layout
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import classes from './WidgetGrid.module.css';

const ResponsiveGridLayout = WidthProvider(Responsive);

interface WidgetGridProps {
  category?: 'dashboard' | 'channel';
  channelId?: string;
}

export const WidgetGrid: React.FC<WidgetGridProps> = ({ 
  category = 'dashboard', 
  channelId 
}) => {
  const theme = useMantineTheme();
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [layoutModalOpen, setLayoutModalOpen] = useState(false);
  const [newLayoutName, setNewLayoutName] = useState('');
  
  const {
    layouts,
    activeLayoutId,
    isEditMode,
    selectedWidgetId,
    getActiveLayout,
    getLayoutWidgets,
    setEditMode,
    selectWidget,
    updateWidgetPositions,
    removeWidget,
    duplicateWidget,
    duplicateLayout,
    createLayout,
    setActiveLayout,
    deleteLayout,
    exportLayout,
    clearLayout
  } = useWidgetStore();

  // Get current layout and widgets
  const activeLayout = getActiveLayout();
  const currentLayoutId = activeLayout?.id || layouts[0]?.id;
  const widgets = getLayoutWidgets(currentLayoutId);

  // Convert widgets to react-grid-layout format
  const gridLayouts = useMemo(() => {
    return widgets.map(widget => ({
      i: widget.id,
      x: widget.position.x,
      y: widget.position.y,
      w: widget.position.w,
      h: widget.position.h,
      minW: widget.position.minW,
      minH: widget.position.minH,
      static: !isEditMode
    }));
  }, [widgets, isEditMode]);

  // Handle layout changes
  const handleLayoutChange = useCallback((layout: Layout[]) => {
    if (!isEditMode || !currentLayoutId) return;
    
    const positions = layout.map(item => ({
      id: item.i,
      position: {
        x: item.x,
        y: item.y,
        w: item.w,
        h: item.h,
      }
    }));
    
    updateWidgetPositions(currentLayoutId, positions);
  }, [isEditMode, currentLayoutId, updateWidgetPositions]);

  // Handle widget removal
  const handleRemoveWidget = useCallback((widgetId: string) => {
    if (!currentLayoutId) return;
    
    removeWidget(currentLayoutId, widgetId);
    notifications.show({
      title: 'Widget removed',
      message: 'The widget has been removed from your dashboard',
      color: 'red',
    });
  }, [currentLayoutId, removeWidget]);

  // Handle widget duplication
  const handleDuplicateWidget = useCallback((widgetId: string) => {
    if (!currentLayoutId) return;
    
    duplicateWidget(currentLayoutId, widgetId);
    notifications.show({
      title: 'Widget duplicated',
      message: 'A copy of the widget has been added to your dashboard',
      color: 'teal',
    });
  }, [currentLayoutId, duplicateWidget]);

  // Create new layout
  const handleCreateLayout = useCallback(() => {
    if (!newLayoutName.trim()) return;
    
    const layout = createLayout(newLayoutName);
    setActiveLayout(layout.id);
    setNewLayoutName('');
    setLayoutModalOpen(false);
    
    notifications.show({
      title: 'Layout created',
      message: `"${newLayoutName}" has been created`,
      color: 'green',
    });
  }, [newLayoutName, createLayout, setActiveLayout]);

  // Export layout
  const handleExportLayout = useCallback(() => {
    if (!currentLayoutId) return;
    
    const layout = exportLayout(currentLayoutId);
    if (!layout) return;
    
    const dataStr = JSON.stringify(layout, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
    
    const exportFileDefaultName = `${layout.name.toLowerCase().replace(/\s+/g, '-')}-layout.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
    
    notifications.show({
      title: 'Layout exported',
      message: 'Your layout has been downloaded',
      color: 'blue',
    });
  }, [currentLayoutId, exportLayout]);

  return (
    <Box className={classes.gridContainer}>
      {/* Header Controls */}
      <Group justify="space-between" mb="md">
        <Group>
          <Select
            value={currentLayoutId}
            onChange={(value) => value && setActiveLayout(value)}
            data={layouts.map(l => ({ value: l.id, label: l.name }))}
            placeholder="Select layout"
            disabled={isEditMode}
          />
          
          <Menu position="bottom-start">
            <Menu.Target>
              <ActionIcon variant="subtle">
                <IconLayout size={20} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item 
                leftSection={<IconPlus size={16} />}
                onClick={() => setLayoutModalOpen(true)}
              >
                New Layout
              </Menu.Item>
              <Menu.Item 
                leftSection={<IconCopy size={16} />}
                onClick={() => {
                  if (activeLayout) {
                    const copy = duplicateLayout(currentLayoutId, `${activeLayout.name} (Copy)`);
                    setActiveLayout(copy.id);
                  }
                }}
              >
                Duplicate Layout
              </Menu.Item>
              <Menu.Divider />
              <Menu.Item 
                leftSection={<IconDownload size={16} />}
                onClick={handleExportLayout}
              >
                Export Layout
              </Menu.Item>
              <Menu.Item 
                leftSection={<IconUpload size={16} />}
                onClick={() => {/* TODO: Implement import */}}
              >
                Import Layout
              </Menu.Item>
              <Menu.Divider />
              <Menu.Item 
                leftSection={<IconTrash size={16} />}
                color="red"
                onClick={() => {
                  if (layouts.length > 1 && currentLayoutId) {
                    deleteLayout(currentLayoutId);
                  }
                }}
                disabled={layouts.length === 1}
              >
                Delete Layout
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>

        <Group>
          <Switch
            checked={isEditMode}
            onChange={(e) => setEditMode(e.currentTarget.checked)}
            label={isEditMode ? 'Edit Mode' : 'View Mode'}
            color="blue"
            size="md"
          />
          
          {isEditMode && (
            <>
              <Button
                leftSection={<IconPlus size={16} />}
                onClick={() => setAddModalOpen(true)}
                variant="filled"
                size="sm"
              >
                Add Widget
              </Button>
              
              <Button
                leftSection={<IconTrash size={16} />}
                onClick={() => {
                  if (currentLayoutId && widgets.length > 0) {
                    clearLayout(currentLayoutId);
                    notifications.show({
                      title: 'Layout cleared',
                      message: 'All widgets have been removed',
                      color: 'orange',
                    });
                  }
                }}
                variant="subtle"
                color="red"
                size="sm"
                disabled={widgets.length === 0}
              >
                Clear All
              </Button>
            </>
          )}
        </Group>
      </Group>

      {/* Grid Layout */}
      {widgets.length === 0 ? (
        <Paper p="xl" withBorder className={classes.emptyState}>
          <Text c="dimmed" ta="center" size="lg">
            No widgets added yet
          </Text>
          <Text c="dimmed" ta="center" size="sm" mt="xs">
            {isEditMode 
              ? 'Click "Add Widget" to get started' 
              : 'Switch to Edit Mode to add widgets'}
          </Text>
        </Paper>
      ) : (
        <ResponsiveGridLayout
          className={classes.gridLayout}
          layouts={{ lg: gridLayouts }}
          onLayoutChange={handleLayoutChange}
          breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
          cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
          rowHeight={60}
          isDraggable={isEditMode}
          isResizable={isEditMode}
          compactType="vertical"
          preventCollision={false}
          margin={[16, 16]}
        >
          {widgets.map(widget => (
            <div key={widget.id} className={classes.widgetWrapper}>
              <WidgetContainer
                widget={widget}
                isEditing={isEditMode}
                isSelected={selectedWidgetId === widget.id}
                onSelect={() => selectWidget(widget.id)}
                onRemove={() => handleRemoveWidget(widget.id)}
                onDuplicate={() => handleDuplicateWidget(widget.id)}
                channelId={channelId}
              />
            </div>
          ))}
        </ResponsiveGridLayout>
      )}

      {/* Add Widget Modal */}
      <WidgetAddModal
        opened={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        category={category}
        layoutId={currentLayoutId}
      />

      {/* Create Layout Modal */}
      <Modal
        opened={layoutModalOpen}
        onClose={() => {
          setLayoutModalOpen(false);
          setNewLayoutName('');
        }}
        title="Create New Layout"
      >
        <TextInput
          label="Layout Name"
          placeholder="Enter layout name"
          value={newLayoutName}
          onChange={(e) => setNewLayoutName(e.currentTarget.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleCreateLayout()}
          mb="md"
        />
        <Group justify="flex-end">
          <Button variant="subtle" onClick={() => setLayoutModalOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleCreateLayout} disabled={!newLayoutName.trim()}>
            Create Layout
          </Button>
        </Group>
      </Modal>
    </Box>
  );
};