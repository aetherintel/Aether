import { useState } from 'react';
import { Button, NumberInput, Stack, TextInput } from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';

const apiUrl = import.meta.env.VITE_API_URL;

interface CaseFileFormValues {
  title: string;
  category: string;
  postCount: number;
}

export function CreateCaseFileForm() {
  const form = useForm<CaseFileFormValues>({
    initialValues: {
      title: '',
      category: '',
      postCount: 0,
    },
  });

  const [loading, setLoading] = useState(false);

  const handleSubmit = async (values: CaseFileFormValues) => {
    setLoading(true);
    try {
      const res = await fetch(`${apiUrl ? apiUrl : 'http://localhost:8000/api'}/casefiles`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(values),
      });

      if (!res.ok) {
        throw new Error('Failed to create case file');
      }

      const data = await res.json();
      notifications.show({
        title: 'CaseFile',
        message: `CaseFile created with ID: ${data.id}`,
      });
      form.reset();
    } catch (err: any) {
      notifications.show({
        title: 'Error creating CaseFile',
        message: err.message || 'Unknown error',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack>
        <TextInput label="Title" {...form.getInputProps('title')} required />
        <TextInput label="Category" {...form.getInputProps('category')} required />
        <NumberInput label="Post count" {...form.getInputProps('postCount')} required />
        <Button type="submit" loading={loading}>
          Create CaseFile
        </Button>
      </Stack>
    </form>
  );
}
