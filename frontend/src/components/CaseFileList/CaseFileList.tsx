import { useEffect, useState } from 'react';
import { Grid, Loader, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import CaseCard from '@/components/CaseCard/CaseCard';
import { authFetch } from '@/utils/authFetch';

const apiUrl = import.meta.env.VITE_API_URL;

export interface CaseFile {
  id: number;
  title: string;
  description: string;
  postCount: number;
  category: string;
  chartData: ChartDataPoint[];
  archived: boolean;
  tgchannels: string[];
  thumbnails: string[];
}

export interface ChartDataPoint {
  date: string;
  posts: number;
}

interface CaseFileListProps {
  archived: boolean;
  refreshTrigger?: number;
  onRefresh?: () => void;
  limit?: number;
  compact?: boolean;
}

export function CaseFileList({
  archived,
  refreshTrigger,
  onRefresh,
  limit,
  compact = false,
}: CaseFileListProps) {
  const [caseFiles, setCaseFiles] = useState<CaseFile[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchCaseFiles = async () => {
    const fetchUrl = new URL(`${apiUrl ?? 'http://localhost:8000/api'}/casefiles/`);

    fetchUrl.searchParams.set('archived', archived ? 'true' : 'false');

    if (limit) {
      fetchUrl.searchParams.set('limit', limit.toString());
    }

    setLoading(true);

    try {
      const res = await authFetch(fetchUrl.toString());
      const data = await res.json();
      setCaseFiles(data);
    } catch (err: any) {
      console.error('Error fetching casefiles:', err);
      notifications.show({
        title: 'Error fetching casefiles',
        message: err.message || 'Unknown error',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCaseFiles();
  }, [archived, refreshTrigger]);

  const handleDelete = async (id: number) => {
    const base = apiUrl ?? 'http://localhost:8000/api';
    const res = await authFetch(`${base}/casefiles/${id}`, { method: 'DELETE' });

    if (res.ok) {
      setCaseFiles((files) => files.filter((file) => file.id !== id));
      notifications.show({
        title: 'CaseFile',
        message: `CaseFile deleted with ID: ${id}`,
      });
      onRefresh?.();
    } else {
      notifications.show({
        title: 'CaseFile',
        message: 'Failed to delete casefile',
      });
    }
  };

  const handleArchive = async (id: number, archive: boolean) => {
    const base = apiUrl ?? 'http://localhost:8000/api';
    const archiveUrl = new URL(`${base}/casefiles/${id}/archive`);
    archiveUrl.searchParams.set('archived', archive ? 'true' : 'false');
    const archiveRes = await authFetch(archiveUrl.toString(), { method: 'PATCH' });
    const res = await archiveRes.json();

    if (res.ok) {
      setCaseFiles((files) => files.filter((file) => file.id !== id));
      notifications.show({
        title: 'CaseFile',
        message: `CaseFile ${archive ? 'archived' : 'unarchived'} with ID: ${id}`,
      });
      // Trigger refresh of both lists
      onRefresh?.();
    } else {
      notifications.show({
        title: 'CaseFile',
        message: 'Failed to archive casefile',
      });
    }
  };

  if (loading) {
    return <Loader />;
  }

  return (
    <>
      {caseFiles.length === 0 ? (
        <Text>{archived ? 'No archived cases found' : 'No active cases found'}</Text>
      ) : (
        <Grid columns={compact ? 1 : 3} gutter={compact ? 10 : 20}>
          {caseFiles.map((caseFile) => (
            <Grid.Col key={caseFile.id} span={{ base: 3, sm: 1 }}>
              <CaseCard
                caseFile={caseFile}
                onArchive={handleArchive}
                onDelete={handleDelete}
                compact={compact}
              />
            </Grid.Col>
          ))}
        </Grid>
      )}
    </>
  );
}
