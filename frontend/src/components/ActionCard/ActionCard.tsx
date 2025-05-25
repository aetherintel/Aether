import { Icon } from '@tabler/icons-react';
import { Box, Text } from '@mantine/core';
import classes from './ActionCard.module.css';

interface Props {
  icon: Icon;
  content: string;
  onClick?: () => void;
}

export default function ActionCard({ icon: Icon, content, onClick }: Props) {
  return (
    <Box className={classes.root} onClick={onClick}>
      <Icon size={20} />
      <Text className={classes.content} fz={13}>
        {content}
      </Text>
    </Box>
  );
}
