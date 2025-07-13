import { Box, Center, Group, Text, Title } from '@mantine/core';
import classes from './Logo.module.css';

export default function Logo() {

  return (
    <Group justify="center" gap="xs" mb={15}>
        <Center>
            <Box w={60} h={60} bg="white" className={classes.circle}>
                <Center h="100%">
                    <Text fz="34" fw={500} c="blue">
                    Æ
                    </Text>
                </Center>
                <Title ta="center" fw={500} className={classes.innerTitle}>
                    Æther
                </Title>
            </Box>
        </Center>
        <Title ta="center" fw={500} c="white" className={classes.outerTitle}>
            Æther
        </Title>
    </Group>
  );
}