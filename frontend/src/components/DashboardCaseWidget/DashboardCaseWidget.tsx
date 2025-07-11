import { Box, Title, Group, Button } from '@mantine/core';
import { IconChevronRight } from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import { CaseFileList } from '../CaseFileList/CaseFileList';
import classes from './DashboardCaseWidget.module.css';


export function DashboardCaseWidget() {
  return (
    <Box className={classes.widget}>
      <Group position="apart" className={classes.widgetHeader}>
        <Title order={3} className={classes.title}>Recent Cases</Title>
        <Button
          component={Link}
          to="/cases"
          variant="subtle"
          rightIcon={<IconChevronRight size={16} />}
          className={classes.viewAllButton}
          size="sm"
        >
          show all
        </Button>
      </Group>

      <div className={classes.compactList}>
        <CaseFileList
          archived={false}
          limit={3}
          compact={true}
        />
      </div>
    </Box>
  );
}

