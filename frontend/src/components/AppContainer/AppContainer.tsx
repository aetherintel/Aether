import '@mantine/core/styles.css';
import '@mantine/notifications/styles.css';

import { Suspense, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { AppShell, Overlay } from '@mantine/core';
import { useDisclosure, useMediaQuery } from '@mantine/hooks';
import { useAuthStore } from '../../store/client/authStore';
import { useStore } from '../../store/client/useStore';
import AppHeader from '../AppHeader/AppHeader';
import { Navbar } from '../Navbar/Navbar';
import classes from './AppContainer.module.css';

export default function AppContainer() {
  const [opened, { toggle, close }] = useDisclosure();

  const { isNavbarCollapse } = useStore();

  const smallScreen = useMediaQuery('(max-width: 48em)');

  useEffect(() => {
    if (opened && smallScreen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'visible';
    }
  }, [opened, smallScreen]);

  const { isAuthenticated } = useAuthStore();

  return (
    <AppShell
      padding="md"
      navbar={{
        width: isNavbarCollapse ? 81 : 0,
        breakpoint: 'sm',
        collapsed: { mobile: !opened },
      }}
      classNames={{
        navbar: classes.navbar,
        header: classes.header,
        main: classes.main,
      }}
      header={{ height: 60 }}
      disabled={!isAuthenticated}
    >
      <AppShell.Header>
        <AppHeader opened={opened} toggle={toggle} />
      </AppShell.Header>
      <AppShell.Navbar data-smallscreen={smallScreen} data-collapse={isNavbarCollapse}>
        <Navbar isNavbarOpen={isNavbarCollapse} />
      </AppShell.Navbar>
      <AppShell.Main>
        {opened && smallScreen && (
          <Overlay
            onClick={close}
            zIndex={100}
            h="100vh"
            color="#000"
            backgroundOpacity={0.35}
            blur={15}
          />
        )}
        <Suspense fallback={<div>Loading</div>}>
          <Outlet />
        </Suspense>
      </AppShell.Main>
    </AppShell>
  );
}
