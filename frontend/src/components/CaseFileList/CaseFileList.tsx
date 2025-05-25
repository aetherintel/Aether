import { useEffect, useState } from 'react';
import { Grid, Loader } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import CaseCard from '../CaseCard/CaseCard';

const apiUrl = import.meta.env.VITE_API_URL;

export interface CaseFile {
  id: number;
  title: string;
  postCount: number;
  category: string;
  chartData: ChartDataPoint[];
}

export interface ChartDataPoint {
  date: string;
  posts: number;
}

export function CaseFileList() {
  const [caseFiles, setCaseFiles] = useState<CaseFile[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${apiUrl ? apiUrl : 'http://localhost:8000/api'}/casefiles/`)
      .then((res) => res.json())
      .then((data) => setCaseFiles(data))
      .catch((err) => {
        notifications.show({
          title: 'Error fetching casefiles',
          message: err.message || 'Unknown error',
          color: 'red',
        });
      })
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (id: number) => {
    const res = await fetch(`${apiUrl ? apiUrl : 'http://localhost:8000/api'}/casefiles/${id}`, {
      method: 'DELETE',
    });

    if (res.ok) {
      setCaseFiles((files) => files.filter((file) => file.id !== id));
      notifications.show({
        title: 'CaseFile',
        message: `CaseFile deleted with ID: ${id}`,
      });
    } else {
      notifications.show({
        title: 'CaseFile',
        message: 'Failed to delete casefile',
      });
    }
  };

  if (loading) {
    return <Loader />;
  }

  return (
    <Grid columns={3} gutter={20}>
      {caseFiles.map((caseFile) => (
        <Grid.Col key={caseFile.id} span={{ base: 3, md: 1 }}>
          <CaseCard caseFile={caseFile} onDelete={handleDelete} />
        </Grid.Col>
      ))}
    </Grid>
  );
}
