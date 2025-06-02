import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Loader, Text, Title } from '@mantine/core';
import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';

const apiUrl = import.meta.env.VITE_API_URL;

export function CaseFileDetail() {
  const { id } = useParams<{ id: string }>();
  const [caseFile, setCaseFile] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${apiUrl ? apiUrl : 'http://localhost:8000/api'}/casefiles/${id}`)
      .then((res) => res.json())
      .then((data) => {
        setCaseFile(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <Loader />;
  }
  if (!caseFile) {
    return <Text>Case file not found.</Text>;
  }

  return (
    <div>
      <BreadcrumbsBar overrides={{ [`/cases/${caseFile.id}`]: caseFile.title }} />
      <Title>{caseFile.title}</Title>
      <Text>Category: {caseFile.category}</Text>
      <Text>Post count: {caseFile.postCount}</Text>
      <Text>Topics: {caseFile.topics?.join(', ')}</Text>
      <Text>Terms: {caseFile.terms?.join(', ')}</Text>
      <Text>Telegram Channels: {caseFile.tgchannels?.join(', ')}</Text>
      <Text>Duration: {caseFile.duration}</Text>
      {/* Render chartData or other fields as needed */}
    </div>
  );
}
