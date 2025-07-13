import { IconArchive, IconTrash } from '@tabler/icons-react';
import { ActionIcon, Badge, Button, Card, Group, Image, Menu, rem, SimpleGrid, Text } from '@mantine/core';
import classes from './CaseCard.module.css';
import { CaseFile } from '../CaseFileList/CaseFileList';
import { Link } from 'react-router-dom';

interface CaseCardProps {
  caseFile: CaseFile;
  onDelete: (id: number) => void;
  onArchive: (id: number, archive: boolean) => void;
  compact?: boolean;
}

export default function CaseCard({ caseFile, onDelete, onArchive, compact = false }: CaseCardProps) {
  const handleDeleteCaseClick = () => {
    onDelete(caseFile.id);
  };
  const handleArchiveCaseClick = () => {
    onArchive(caseFile.id, !caseFile.archived);
  };

  const features = [...new Set(caseFile.tgchannels)].map((badge) => (
    <Badge variant="light" key={badge}>
      {badge}
    </Badge>
  ));

  const thumbnails = [...new Set(caseFile.thumbnails)]
  .slice(0, 4)  // Limit to first 4 items
  .map((thumbnail) => (
    <Image 
      key={thumbnail} 
      src={thumbnail} 
      alt={thumbnail} 
      height={90} 
      fallbackSrc="https://placehold.co/600x360?text=Not downloaded yet" 
    />
  ));

  return (
    <Card withBorder radius="md" p="md" className={classes.card} opacity={caseFile.archived ? 0.5 : 1}>
      {compact ? null : (
        <Card.Section>
          <SimpleGrid cols={2} spacing="0" verticalSpacing="0">
            {thumbnails}
          </SimpleGrid>
        </Card.Section>
      )}

      <Card.Section className={classes.section} mt={compact ? 0 : 'md'}>
        <Group justify="apart">
          <Text fz="lg" fw={500}>
            {caseFile.title}
          </Text>
          <Badge size="sm" variant="light">
            {caseFile.postCount} messages
          </Badge>
        </Group>
        <Text fz="sm" mt="xs">
          {caseFile.description}
        </Text>

        <Menu shadow="md" width={200}>
          <Menu.Target>
            <ActionIcon className={classes.actionIcon} variant="subtle">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                strokeWidth="1.5"
                stroke="gray"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path stroke="none" d="M0 0h24v24H0z" fill="none" />
                <path d="M12 12m-1 0a1 1 0 1 0 2 0a1 1 0 1 0 -2 0" />
                <path d="M12 19m-1 0a1 1 0 1 0 2 0a1 1 0 1 0 -2 0" />
                <path d="M12 5m-1 0a1 1 0 1 0 2 0a1 1 0 1 0 -2 0" />
              </svg>
            </ActionIcon>
          </Menu.Target>

          <Menu.Dropdown>
            {!caseFile.archived ? (
              <Menu.Item
                leftSection={<IconArchive style={{ width: rem(14), height: rem(14) }} />}
                onClick={handleArchiveCaseClick}
              >
                Archive case
              </Menu.Item>
            ) : null}
            {caseFile.archived ? (
              <Menu.Item
                leftSection={<IconArchive style={{ width: rem(14), height: rem(14) }} />}
                onClick={handleArchiveCaseClick}
              >
                Unarchive case
              </Menu.Item>
            ) : null}
            <Menu.Item
                color="red"
                leftSection={<IconTrash style={{ width: rem(14), height: rem(14) }} />}
                onClick={handleDeleteCaseClick}
              >
                Delete case
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>
      </Card.Section>

      <Card.Section className={classes.section}>
        <Text mt="md" className={classes.label} c="dimmed">
          Channels
        </Text>
        <Group gap={7} mt={5}>
          {features}
        </Group>
      </Card.Section>

      <Group mt="xs">
        <Button radius="md" component={Link} to={`/cases/${caseFile.id}`} style={{ flex: 1 }}>
          Show details
        </Button>
        <ActionIcon variant="default" radius="md" size={36} onClick={handleArchiveCaseClick} display={compact ? 'none' : 'block'}>
          <IconArchive className={classes.like} stroke={1.5} />
        </ActionIcon>
      </Group>
    </Card>
  );
}