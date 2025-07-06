import { IconSettings, IconTrash, IconUser } from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import { Avatar, Burger, Flex, Group, Menu, rem } from '@mantine/core';
import { useMediaQuery } from '@mantine/hooks';
import { useStore } from '../../store/client/useStore';
import ThemeSwitch from '../ThemeSwitch/ThemeSwitch';

interface Props {
  opened: boolean;
  toggle: () => void;
}

export default function AppHeader({ opened, toggle }: Props) {
  const { isNavbarCollapse, toggleNavbar } = useStore();

  const smallScreen = useMediaQuery('(max-width: 48em)');

  return (
    <Group h="100%" px="lg" justify="space-between">
      <Flex align="center" gap={16}>
        {smallScreen ? (
          <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
        ) : (
          <Burger
            style={{
              outline: 'none',
            }}
            size="sm"
            opened={!isNavbarCollapse}
            onClick={toggleNavbar}
          />
        )}
      </Flex>

      <Flex align="center" gap={24}>
        <ThemeSwitch />

        <Menu shadow="md" width={200}>
          <Menu.Target>
            <Avatar radius="xl">
              <IconUser color="black" />
            </Avatar>
          </Menu.Target>

          <Menu.Dropdown>
            <Menu.Label>Æther</Menu.Label>
            <Menu.Item
              leftSection={<IconSettings style={{ width: rem(14), height: rem(14) }} />}
              component={Link}
              to="/settings"
            >
              Settings
            </Menu.Item>

            <Menu.Divider />

            <Menu.Item
              color="red"
              leftSection={<IconTrash style={{ width: rem(14), height: rem(14) }} />}
            >
              Delete my account
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>
      </Flex>
    </Group>
  );
}
