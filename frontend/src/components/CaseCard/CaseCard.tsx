import { IconLink, IconShare, IconTrash, IconUser } from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import { LineChart } from '@mantine/charts';
import { ActionIcon, Box, Divider, Flex, Group, Menu, rem, Text } from '@mantine/core';
import { CaseFile } from '../CaseFileList/CaseFileList';
import classes from './CaseCard.module.css';

const exampleChartData = [
  {
    date: 'Mar 22',
    posts: 2890,
  },
  {
    date: 'Mar 23',
    posts: 2756,
  },
  {
    date: 'Mar 24',
    posts: 5322,
  },
];

interface CaseCardProps {
  caseFile: CaseFile;
  onDelete: (id: number) => void;
}

export default function CaseCard({ caseFile, onDelete }: CaseCardProps) {
  const handleDeleteCaseClick = () => {
    onDelete(caseFile.id);
  };

  return (
    <Box className={classes.root}>
      <Box className={classes.imageSection}>
        <Group w="100%" align="center" justify="space-between">
          <Flex direction="column" align="start" gap={3} component={Link} to={`/cases/${caseFile.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
            <Text lh={1} className={classes.title}>
              {caseFile.title}
            </Text>
            <Flex align="center" gap={10}>
              <Text fz={12}>{caseFile.category}</Text>

              <Divider component="span" orientation="vertical" />
              <Text fz={12} component="span">
                {caseFile.postCount} posts
              </Text>
            </Flex>
          </Flex>
        </Group>

        <LineChart
          h={110}
          data={exampleChartData}
          dataKey="date"
          series={[{ name: 'posts', label: 'Posts', color: 'blue' }]}
          curveType="natural"
          tickLine="none"
          gridAxis="none"
          withXAxis={false}
          withYAxis={false}
          withDots={false}
          withTooltip={false}
          mx={rem(-21)}
        />

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
            <Menu.Item
              leftSection={
                <IconLink
                  style={{
                    width: rem(14),
                    height: rem(14),
                    transform: 'rotate(-40deg)',
                  }}
                />
              }
              fz={12}
            >
              Copy link
            </Menu.Item>

            <Menu.Item
              leftSection={<IconShare style={{ width: rem(14), height: rem(14) }} />}
              fz={12}
            >
              Share case
            </Menu.Item>
            <Menu.Item
              fz={12}
              leftSection={<IconUser style={{ width: rem(14), height: rem(14) }} />}
            >
              Manage permission
            </Menu.Item>
            <Menu.Item
              color="red"
              leftSection={<IconTrash style={{ width: rem(14), height: rem(14) }} />}
              onClick={handleDeleteCaseClick}
            >
              Delete case
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>
      </Box>
    </Box>
  );
}
