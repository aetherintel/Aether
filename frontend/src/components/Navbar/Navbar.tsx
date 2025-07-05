import { useState } from 'react';
import {
  IconFiles,
  IconHome2,
  IconLogout,
  IconSettings,
  IconSwitchHorizontal,
  IconUser,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { Box, Center, Stack, Text, Tooltip, UnstyledButton } from '@mantine/core';
import { useAuthStore } from '../../store/client/authStore';
import classes from './Navbar.module.css';

interface NavbarLinkProps {
  icon: typeof IconHome2;
  label: string;
  active?: boolean;
  onClick?: () => void;
}

interface NavbarProps {
  isNavbarOpen: boolean;
}

function NavbarLink({ icon: Icon, label, active, onClick }: NavbarLinkProps) {
  return (
    <Tooltip label={label} position="right" transitionProps={{ duration: 0 }}>
      <UnstyledButton onClick={onClick} className={classes.link} data-active={active || undefined}>
        <Icon size={20} stroke={1.5} />
      </UnstyledButton>
    </Tooltip>
  );
}

const mockdata = [
  { icon: IconHome2, label: 'Home', href: '/' },
  { icon: IconFiles, label: 'Cases', href: '/cases' },
  { icon: IconUser, label: 'Account', href: '/account' },
  { icon: IconSettings, label: 'Settings', href: '/settings' },
];

export function Navbar({ isNavbarOpen }: NavbarProps) {
  const [active, setActive] = useState(0);
  const { logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const links = mockdata.map((link, index) => (
    <NavbarLink
      {...link}
      key={link.label}
      active={index === active}
      onClick={() => {
        setActive(index);
        navigate(link.href);
      }}
    />
  ));

  return (
    <nav className={classes.navbar} data-collapsed={isNavbarOpen}>
      <Center>
        <Box w={40} h={40} bg="white" style={{ borderRadius: '50%' }}>
          <Center h="100%">
            <Text size="xl" fw={700} c="blue">
              Æ
            </Text>
          </Center>
        </Box>
      </Center>

      <div className={classes.navbarMain}>
        <Stack justify="center" gap={0}>
          {links}
        </Stack>
      </div>

      <Stack justify="center" gap={0}>
        <NavbarLink icon={IconSwitchHorizontal} label="Change account" />
        <NavbarLink icon={IconLogout} label="Logout" onClick={handleLogout} />
      </Stack>
    </nav>
  );
}
