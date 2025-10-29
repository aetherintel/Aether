// src/components/GroupedJobsDisplay.tsx
import React, { useState } from 'react';
import {
  Paper,
  Stack,
  Group,
  Title,
  Badge,
  Card,
  Text,
  Button,
  ActionIcon,
} from '@mantine/core';
import {
  IconActivity,
  IconRefresh,
  IconTrash,
  IconChevronDown,
  IconChevronUp,
  IconBrandTelegram,
  IconLanguage,
  IconPhoto,
  IconVolume,
  IconMoodSmile,
} from '@tabler/icons-react';

interface ContainerInfo {
  id: string;
  name: string;
  image: string;
  status: string;
  labels?: {
    queue?: string;
    channels?: string;
    mode?: string;
    case_id?: string;
  };
  queue?: string;
  channels?: string;
  mode?: string;
  case_id?: string | number;
  session?: string;
  runtime?: string;
  created?: string;
}

interface GroupedJobsDisplayProps {
  status: ContainerInfo[];
  controlLoading: Record<string, boolean>;
  onJobControl: (jobId: string, action: 'remove' | 'requeue') => Promise<void>;
  canRemoveJob: (status: string) => boolean;
  canRequeueJob: (status: string) => boolean;
}

const GroupedJobsDisplay: React.FC<GroupedJobsDisplayProps> = ({
  status,
  controlLoading,
  onJobControl,
  canRemoveJob,
  canRequeueJob,
}) => {
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({
    telegram: true,
    translation: false,
    image: false,
    audio: false,
    sentiment: false,
  });

  // Track which status filter is active for each queue (null = show all)
  const [statusFilters, setStatusFilters] = useState<Record<string, string | null>>({});

  // Group jobs by queue
  const groupedJobs = status.reduce((acc, job) => {
    const queue = job.queue || job.labels?.queue || 'unknown';
    if (!acc[queue]) acc[queue] = [];
    acc[queue].push(job);
    return acc;
  }, {} as Record<string, ContainerInfo[]>);

  const getQueueIcon = (queue: string) => {
    if (queue.includes('telegram')) return <IconBrandTelegram size="1.2rem" />;
    if (queue.includes('translation')) return <IconLanguage size="1.2rem" />;
    if (queue.includes('image')) return <IconPhoto size="1.2rem" />;
    if (queue.includes('audio')) return <IconVolume size="1.2rem" />;
    if (queue.includes('emotion')) return <IconMoodSmile size="1.2rem" />;
    if (queue.includes('classification')) return <IconActivity size="1.2rem" />;

    return '⚙️';
  };

  const getQueueColor = (queue: string) => {
    if (queue.includes('telegram')) return 'blue';
    if (queue.includes('translation')) return 'violet';
    if (queue.includes('image')) return 'teal';
    if (queue.includes('audio')) return 'orange';
    if (queue.includes('emotion')) return 'pink';
    if (queue.includes('classification')) return 'cyan';
    return 'gray';
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
      case 'started':
        return 'blue';
      case 'pending':
      case 'queued':
        return 'yellow';
      case 'exited':
      case 'finished':
        return 'green';
      case 'failed':
        return 'red';
      default:
        return 'gray';
    }
  };

  const getStatusStats = (jobs: ContainerInfo[]) => {
    const stats = jobs.reduce((acc, job) => {
      const status = job.status.toLowerCase(); // Normalize status
      acc[status] = (acc[status] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    return stats;
  };

  const formatRuntime = (runtime?: string) => {
    return runtime || '';
  };

  const toggleGroup = (queue: string) => {
    setExpandedGroups((prev) => ({
      ...prev,
      [queue]: !prev[queue],
    }));
  };

  const toggleStatusFilter = (queue: string, status: string) => {
    setStatusFilters((prev) => ({
      ...prev,
      [queue]: prev[queue] === status ? null : status,
    }));
    // Auto-expand when filtering
    if (statusFilters[queue] !== status) {
      setExpandedGroups((prev) => ({ ...prev, [queue]: true }));
    }
  };

  const renderJobCard = (container: ContainerInfo) => {
    const isLoading = controlLoading[container.id] || false;
    const queue = container.queue || container.labels?.queue || '';
    const channels =
      container.labels?.channels || container.channels || container.mode || 'N/A';

    return (
      <Card key={container.id} padding="sm" withBorder>
        <Group justify="space-between" align="flex-start">
          <Stack gap="xs" style={{ flex: 1 }}>
            <Group align="center" gap="xs">
              <Text size="lg">{getQueueIcon(queue)}</Text>
              <Text fw={500}>{channels}</Text>
              <Badge color={getStatusColor(container.status)} variant="light">
                {container.status}
              </Badge>
              {container.runtime && (
                <Badge variant="outline" size="sm">
                  ⏱️ {formatRuntime(container.runtime)}
                </Badge>
              )}
            </Group>

            <Text size="sm" c="dimmed">
              {container.image}
            </Text>

            <Text size="xs" c="dimmed">
              ID: {container.id.substring(0, 12)}
            </Text>

            {container.case_id && (
              <Badge size="sm" variant="dot" color="blue">
                Case {container.case_id}
              </Badge>
            )}

            {container.session && container.session !== 'N/A' && (
              <Text size="xs" c="dimmed">
                Session: {container.session}
              </Text>
            )}
          </Stack>

          <Stack gap="xs" align="flex-end">
            {canRequeueJob(container.status) && (
              <Button
                size="xs"
                variant="light"
                color="orange"
                leftSection={<IconRefresh size="0.75rem" />}
                onClick={() => onJobControl(container.id, 'requeue')}
                loading={isLoading}
              >
                Retry
              </Button>
            )}

            {canRemoveJob(container.status) && (
              <Button
                size="xs"
                variant="light"
                color="red"
                leftSection={<IconTrash size="0.75rem" />}
                onClick={() => onJobControl(container.id, 'remove')}
                loading={isLoading}
              >
                Remove
              </Button>
            )}

            {!canRemoveJob(container.status) && !canRequeueJob(container.status) && (
              <Badge color="green" variant="dot">
                Active
              </Badge>
            )}
          </Stack>
        </Group>
      </Card>
    );
  };

  const renderGroupedSection = (queue: string, jobs: ContainerInfo[]) => {
    const stats = getStatusStats(jobs);
    const isExpanded = expandedGroups[queue];
    const isTelegram = queue.includes('telegram');
    const activeFilter = statusFilters[queue];

    // Filter jobs based on active status filter
    const filteredJobs = activeFilter
      ? jobs.filter((job) => job.status.toLowerCase() === activeFilter.toLowerCase())
      : jobs;

    // Determine if we should show jobs
    const shouldShowJobs = isTelegram || isExpanded || activeFilter;

    return (
      <Paper key={queue} p="md" withBorder>
        <Stack gap="md">
          {/* Header with stats */}
          <Group justify="space-between" align="center">
            <Group gap="xs">
              {getQueueIcon(queue)}
              <Title order={4} tt="capitalize">
                {queue.replace('-', ' ')} Jobs
              </Title>
              <Badge size="lg" color={getQueueColor(queue)} variant="light">
                {jobs.length}
              </Badge>
            </Group>

            {!isTelegram && (
              <ActionIcon
                variant="subtle"
                onClick={() => toggleGroup(queue)}
                size="lg"
              >
                {isExpanded ? (
                  <IconChevronUp size="1rem" />
                ) : (
                  <IconChevronDown size="1rem" />
                )}
              </ActionIcon>
            )}
          </Group>

          {/* Stats summary - clickable badges to filter */}
          <Group gap="sm">
            {stats.running > 0 && (
              <Badge
                color="blue"
                variant={activeFilter === 'running' ? 'filled' : 'dot'}
                style={{ cursor: 'pointer' }}
                onClick={() => toggleStatusFilter(queue, 'running')}
              >
                {stats.running} running
              </Badge>
            )}
            {stats.pending > 0 && (
              <Badge
                color="yellow"
                variant={activeFilter === 'pending' ? 'filled' : 'dot'}
                style={{ cursor: 'pointer' }}
                onClick={() => toggleStatusFilter(queue, 'pending')}
              >
                {stats.pending} pending
              </Badge>
            )}
            {stats.exited > 0 && (
              <Badge
                color="green"
                variant={activeFilter === 'exited' ? 'filled' : 'dot'}
                style={{ cursor: 'pointer' }}
                onClick={() => toggleStatusFilter(queue, 'exited')}
              >
                {stats.exited} completed
              </Badge>
            )}
            {stats.failed > 0 && (
              <Badge
                color="red"
                variant={activeFilter === 'failed' ? 'filled' : 'dot'}
                style={{ cursor: 'pointer' }}
                onClick={() => toggleStatusFilter(queue, 'failed')}
              >
                {stats.failed} failed
              </Badge>
            )}
          </Group>

          {/* Show jobs when expanded OR when filtered OR for telegram */}
          {shouldShowJobs && filteredJobs.length > 0 && (
            <Stack gap="sm">
              {activeFilter && (
                <Text size="sm" c="dimmed">
                  Showing {filteredJobs.length} {activeFilter} job{filteredJobs.length !== 1 ? 's' : ''}
                </Text>
              )}
              {filteredJobs.map(renderJobCard)}
            </Stack>
          )}

          {/* Show message if filter returns no results */}
          {shouldShowJobs && filteredJobs.length === 0 && activeFilter && (
            <Text size="sm" c="dimmed" ta="center">
              No {activeFilter} jobs found
            </Text>
          )}
        </Stack>
      </Paper>
    );
  };

  if (status.length === 0) {
    return null;
  }

  return (
    <Stack gap="md">
      <Group align="center" gap="xs">
        <IconActivity size="1.2rem" />
        <Title order={3}>Jobs Overview</Title>
        <Badge size="lg" variant="light">
          {status.length} total
        </Badge>
      </Group>

      {Object.entries(groupedJobs)
        .sort(([queueA], [queueB]) => {
          // Sort telegram first, then alphabetically
          if (queueA.includes('telegram')) return -1;
          if (queueB.includes('telegram')) return 1;
          return queueA.localeCompare(queueB);
        })
        .map(([queue, jobs]) => renderGroupedSection(queue, jobs))}
    </Stack>
  );
};

export default GroupedJobsDisplay;