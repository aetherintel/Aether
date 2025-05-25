import { useState } from 'react';
import { Box, Flex, FloatingIndicator, Tabs, Text } from '@mantine/core';
import { CaseFileList } from '../CaseFileList/CaseFileList';
import classes from './TabSection.module.css';

export default function TabSection() {
  const [rootRef, setRootRef] = useState<HTMLDivElement | null>(null);
  const [value, setValue] = useState<string | null>('1');
  const [controlsRefs, setControlsRefs] = useState<Record<string, HTMLButtonElement | null>>({});
  const setControlRef = (val: string) => (node: HTMLButtonElement) => {
    controlsRefs[val] = node;
    setControlsRefs(controlsRefs);
  };

  return (
    <Flex w="100%" direction="column" align="start" gap={16}>
      <Text className={classes.title}>All cases</Text>

      <Tabs w="100%" variant="none" value={value} onChange={setValue}>
        <Tabs.List ref={setRootRef} className={classes.list}>
          <Tabs.Tab value="1" ref={setControlRef('1')} className={classes.tab}>
            Recent
          </Tabs.Tab>
          <Tabs.Tab value="2" ref={setControlRef('2')} className={classes.tab}>
            Favourites
          </Tabs.Tab>
          <Tabs.Tab value="3" ref={setControlRef('3')} className={classes.tab}>
            Achieved
          </Tabs.Tab>

          <FloatingIndicator
            target={value ? controlsRefs[value] : null}
            parent={rootRef}
            className={classes.indicator}
          />
        </Tabs.List>

        <Box w="100%" my={30}>
          <Tabs.Panel w="100%" value="1">
            <CaseFileList />
          </Tabs.Panel>
          <Tabs.Panel value="2">Second tab content</Tabs.Panel>
          <Tabs.Panel value="3">Third tab content</Tabs.Panel>
        </Box>
      </Tabs>
    </Flex>
  );
}
