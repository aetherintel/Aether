import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Text, Button, Group, Slider, Stack, Stepper, TextInput, Textarea } from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { TgChannelMultiSelect } from '../TgChannelMultiSelect';
import { authFetch } from '@/utils/authFetch';

const apiUrl = import.meta.env.VITE_API_URL;

interface CaseFileFormValues {
  title: string;
  category: string;
  postCount: number;
  tgchannels: string[],
  topics: string[],
  terms: string[],
  duration: number,
}

const marks = [
  { value: 0, label: '3 days' },
  { value: 20, label: '1 week' },
  { value: 40, label: '1 month' },
  { value: 60, label: '3 mouths' },
  { value: 80, label: '6 mouths' },
  { value: 100, label: '1 year' },
];

export function CreateCaseFileForm() {
  const [active, setActive] = useState(0);
  const nextStep = () => setActive((current) => (current < 4 ? current + 1 : current));
  const prevStep = () => setActive((current) => (current > 0 ? current - 1 : current));

  const navigate = useNavigate();

  const form = useForm<CaseFileFormValues>({
    initialValues: {
      title: '',
      category: '',
      postCount: 0,
      tgchannels: [],
      topics: [],
      terms: [],
      duration: 20,
    },
  });

  const [loading, setLoading] = useState(false);

  const handleSubmit = async (values: CaseFileFormValues) => {
    setLoading(true);
    try {
      const res = await authFetch(`${apiUrl ? apiUrl : 'http://localhost:8000/api'}/casefiles/`, {
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
      navigate('/cases');
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
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <form onSubmit={form.onSubmit(handleSubmit)} onKeyDown={(e) => {
        if (e.key === 'Enter' && (e.target as any).tagName !== 'TEXTAREA') {
          e.preventDefault();
        }
      }}>
      <Stepper active={active} onStepClick={setActive} mt="xl">
        <Stepper.Step label="Case" description="Basics">
          <Stack>
            <TextInput label="Name of the case" {...form.getInputProps('title')} required />
            <TextInput label="Category of the case" {...form.getInputProps('category')} required />
            <Textarea
              placeholder="Description of the case"
              label="Description of the case"
              autosize
              minRows={3}
            />
          </Stack>
        </Stepper.Step>
        <Stepper.Step label="Telegram Channels" description="Which telegram channels?">
          <Stack>
            <Text mt="md">Telegram channels start searching from?</Text>
            <TgChannelMultiSelect
              value={form.values.tgchannels}
              onChange={(val) => form.setFieldValue('tgchannels', val)}
            />
          </Stack>
        </Stepper.Step>
        <Stepper.Step label="Settings" description="Case settings">
          <Stack>
            <Text mt="md">How long should this case stay active?</Text>
            <Slider
              {...form.getInputProps('duration')}
              defaultValue={20}
              label={(val) => marks.find((mark) => mark.value === val)!.label}
              step={20}
              marks={marks}
              styles={{ markLabel: { display: 'none' } }}
            />
            
          </Stack>
        </Stepper.Step>
        <Stepper.Completed>
          Completed, click back button to get to previous step
        </Stepper.Completed>
      </Stepper>

      <Group justify="end" mt="xl">
        {active > 0 && (
          <Button variant="default" onClick={prevStep}>
            Back
          </Button>
        )}

        {active <= 1 && (
          <Button
            onClick={() => {
              const isValid = form.validate().hasErrors === false;
              if (isValid) {nextStep();}
            }}
          >
            Next
          </Button>
        )}

        {active === 2 && (
          <Button
            type="submit"
            loading={loading}
          >
            Create Case
          </Button>
        )}
      </Group>
    </form>
  );
}
