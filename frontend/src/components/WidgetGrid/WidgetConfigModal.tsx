// src/components/WidgetGrid/WidgetConfigModal.tsx
import React, { useState, useEffect } from 'react';
import {
  Modal,
  TextInput,
  NumberInput,
  Select,
  Checkbox,
  Button,
  Group,
  Stack,
  Text,
  Divider,
  ColorPicker,
  MultiSelect,
  Loader,
  Alert,
} from '@mantine/core';
import { Widget, WidgetDefinition, WidgetConfig } from '@/types/widgets.types';
import { useForm } from '@mantine/form';
import { IconSettings, IconAlertCircle } from '@tabler/icons-react';
import { authFetch } from '@/utils/authFetch';

const apiUrl = import.meta.env.VITE_API_URL;

interface WidgetConfigModalProps {
  opened: boolean;
  onClose: () => void;
  widget: Widget;
  definition: WidgetDefinition;
  onSave: (config: WidgetConfig) => void;
}

interface CaseFile {
  id: number;
  title: string;
  description: string;
  category: string;
}

interface Channel {
  channel_id: string;
  title: string;
  username: string;
  is_scraped: boolean;
  message_count?: number;
}

export const WidgetConfigModal: React.FC<WidgetConfigModalProps> = ({
  opened,
  onClose,
  widget,
  definition,
  onSave,
}) => {
  const [cases, setCases] = useState<CaseFile[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loadingCases, setLoadingCases] = useState(false);
  const [loadingChannels, setLoadingChannels] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const form = useForm({
    initialValues: widget.config,
  });

  // Load initial values when widget config changes
  useEffect(() => {
    form.setValues(widget.config);
  }, [widget.config]);

  // Fetch cases on mount
  useEffect(() => {
    if (opened) {
      fetchCases();
      fetchChannels();
    }
  }, [opened]);

  const fetchCases = async () => {
    setLoadingCases(true);
    setError(null);
    try {
      const base = apiUrl ?? 'http://localhost:8000/api';
      const res = await authFetch(`${base}/casefiles/?archived=false`);
      
      if (!res.ok) {
        throw new Error('Failed to fetch cases');
      }
      
      const data = await res.json();
      setCases(data);
    } catch (err) {
      console.error('Error fetching cases:', err);
      setError('Failed to load cases');
    } finally {
      setLoadingCases(false);
    }
  };

  const fetchChannels = async () => {
    setLoadingChannels(true);
    setError(null);
    try {
      const base = apiUrl ?? 'http://localhost:8000/api';
      const res = await authFetch(`${base}/messages/channels`);
      
      if (!res.ok) {
        throw new Error('Failed to fetch channels');
      }
      
      const data = await res.json();
      
      // Filter to only show channels that have been scraped or have messages
      const scrapedChannels = data.filter(
        (channel: Channel) => channel.is_scraped === true || (channel.message_count && channel.message_count > 0)
      );
      
      setChannels(scrapedChannels);
    } catch (err) {
      console.error('Error fetching channels:', err);
      setError('Failed to load channels');
    } finally {
      setLoadingChannels(false);
    }
  };

  const handleSubmit = (values: WidgetConfig) => {
    onSave(values);
    onClose();
  };

  const renderField = (field: any) => {
    switch (field.type) {
      case 'text':
        return (
          <TextInput
            key={field.name}
            label={field.label}
            description={field.description}
            placeholder={field.placeholder}
            {...form.getInputProps(field.name)}
            required={field.validation?.required}
          />
        );

      case 'number':
        return (
          <NumberInput
            key={field.name}
            label={field.label}
            description={field.description}
            placeholder={field.placeholder}
            {...form.getInputProps(field.name)}
            min={field.validation?.min}
            max={field.validation?.max}
            required={field.validation?.required}
          />
        );

      case 'select':
        return (
          <Select
            key={field.name}
            label={field.label}
            description={field.description}
            placeholder={field.placeholder}
            data={field.options || []}
            {...form.getInputProps(field.name)}
            required={field.validation?.required}
          />
        );

      case 'multiselect':
        return (
          <MultiSelect
            key={field.name}
            label={field.label}
            description={field.description}
            placeholder={field.placeholder}
            data={field.options || []}
            {...form.getInputProps(field.name)}
            required={field.validation?.required}
            searchable
          />
        );

      case 'case-select':
        return (
          <Select
            key={field.name}
            label={field.label}
            description={field.description || 'Select a case to pull data from'}
            placeholder={field.placeholder || 'Select a case...'}
            data={cases.map(c => ({
              value: String(c.id),
              label: `${c.title} (${c.category})`,
            }))}
            {...form.getInputProps(field.name)}
            required={field.validation?.required}
            disabled={loadingCases}
            searchable
            rightSection={loadingCases ? <Loader size="xs" /> : undefined}
          />
        );

      case 'channel-multiselect':
        return (
          <MultiSelect
            key={field.name}
            label={field.label}
            description={field.description || 'Select channels to monitor'}
            placeholder={field.placeholder || 'Select channels...'}
            data={channels.map(channel => ({
              value: channel.channel_id,
              label: channel.title || channel.username || channel.channel_id,
            }))}
            {...form.getInputProps(field.name)}
            required={field.validation?.required}
            disabled={loadingChannels}
            searchable
            rightSection={loadingChannels ? <Loader size="xs" /> : undefined}
            nothingFoundMessage="No channels found. Make sure channels have been scraped."
          />
        );

      case 'checkbox':
        return (
          <Checkbox
            key={field.name}
            label={field.label}
            description={field.description}
            {...form.getInputProps(field.name, { type: 'checkbox' })}
          />
        );

      case 'color':
        return (
          <div key={field.name}>
            <Text size="sm" fw={500} mb={4}>
              {field.label}
            </Text>
            {field.description && (
              <Text size="xs" c="dimmed" mb={8}>
                {field.description}
              </Text>
            )}
            <ColorPicker
              format="hex"
              {...form.getInputProps(field.name)}
            />
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Group gap="xs">
          <IconSettings size={20} />
          <Text>Configure {widget.title}</Text>
        </Group>
      }
      size="md"
    >
      {error && (
        <Alert
          icon={<IconAlertCircle size={16} />}
          color="red"
          title="Error"
          mb="md"
          withCloseButton
          onClose={() => setError(null)}
        >
          {error}
        </Alert>
      )}

      <form onSubmit={form.onSubmit(handleSubmit)}>
        <Stack>
          {/* Render custom fields from schema */}
          {definition.configSchema?.fields.map(renderField)}

          {/* Common configuration options */}
          <Divider label="Common Settings" />

          <NumberInput
            label="Refresh Interval (ms)"
            description="How often to refresh data (0 to disable)"
            min={0}
            step={1000}
            {...form.getInputProps('refreshInterval')}
          />

          <Group justify="flex-end" mt="md">
            <Button variant="subtle" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit">
              Save Configuration
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
};