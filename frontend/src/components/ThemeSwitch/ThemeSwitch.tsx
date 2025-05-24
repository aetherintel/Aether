import { IconMoon, IconSun } from '@tabler/icons-react';
import cx from 'clsx';
import { ActionIcon, useComputedColorScheme, useMantineColorScheme } from '@mantine/core';
import classes from './ThemeSwitch.module.css';

export default function ThemeSwitch() {
  const { setColorScheme } = useMantineColorScheme();
  const computedColorScheme = useComputedColorScheme('light', {
    getInitialValueInEffect: true,
  });

  return (
    <ActionIcon
      onClick={() => setColorScheme(computedColorScheme === 'light' ? 'dark' : 'light')}
      variant="default"
      size="md"
      radius="md"
      aria-label="Toggle color scheme"
    >
      <IconMoon className={cx(classes.icon, classes.dark)} />
      <IconSun className={cx(classes.icon, classes.light)} />
    </ActionIcon>
  );
}
