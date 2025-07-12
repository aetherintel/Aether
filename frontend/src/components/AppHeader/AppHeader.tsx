import { IconLogout, IconSettings, IconUser } from '@tabler/icons-react';
import { Link, useNavigate } from 'react-router-dom';
import { Avatar, Burger, Flex, Group, Menu, rem } from '@mantine/core';
import { useMediaQuery } from '@mantine/hooks';
import { useStore } from '../../store/client/useStore';
import ThemeSwitch from '../ThemeSwitch/ThemeSwitch';
import { useAuthStore } from '@/store/client/authStore';

interface Props {
  opened: boolean;
  toggle: () => void;
}

export default function AppHeader({ opened, toggle }: Props) {
  const { isNavbarCollapse, toggleNavbar } = useStore();
  const { logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

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
              leftSection={<IconLogout style={{ width: rem(14), height: rem(14) }} />}
              onClick={handleLogout}
            >
              Logout
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>
      </Flex>
    </Group>
  );
}
