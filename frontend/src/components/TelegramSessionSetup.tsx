import React, { useState } from 'react';
import {
  IconAlertCircle,
  IconCheck,
  IconKey,
  IconLock,
  IconPhone,
  IconPlus,
  IconRefresh,
  IconTrash,
  IconUser,
} from '@tabler/icons-react';
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  LoadingOverlay,
  Modal,
  Paper,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useSessionSetup } from '../hooks/useSessionSetup';
import type { Session } from '../types/sessionSetup';

export const TelegramSessionSetup: React.FC = () => {
  const {
    sessions,
    isLoading,
    setupStep,
    currentSetup,
    error,
    startSetup,
    verifyCode,
    verifyPassword,
    deleteSession,
    cancelSetup,
    resetSetup,
    loadSessions,
  } = useSessionSetup();

  const [showSetup, setShowSetup] = useState<boolean>(false);
  const [phone, setPhone] = useState<string>('');
  const [sessionName, setSessionName] = useState<string>('');
  const [code, setCode] = useState<string>('');
  const [password, setPassword] = useState<string>('');

  const handleStartSetup = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    if (!phone.trim() || !sessionName.trim()) {
      return;
    }

    try {
      await startSetup(phone, sessionName);
    } catch (err) {
      console.error('Setup failed:', err);
    }
  };

  const handleVerifyCode = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    if (!code.trim()) {
      return;
    }

    try {
      await verifyCode(code);
    } catch (err) {
      console.error('Code verification failed:', err);
    }
  };

  const handleVerifyPassword = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    if (!password.trim()) {
      return;
    }

    try {
      await verifyPassword(password);
    } catch (err) {
      console.error('Password verification failed:', err);
    }
  };

  const handleDeleteSession = async (sessionName: string): Promise<void> => {
    if (window.confirm(`Session "${sessionName}" wirklich löschen?`)) {
      await deleteSession(sessionName);
    }
  };

  const handleCompleteSetup = (): void => {
    resetSetup();
    setShowSetup(false);
    setPhone('');
    setSessionName('');
    setCode('');
    setPassword('');
  };

  const handleCloseModal = (): void => {
    if (setupStep === 'completed') {
      handleCompleteSetup();
    } else {
      cancelSetup();
      setShowSetup(false);
    }
  };

  const activeSessions = sessions.filter((s: Session) => s.active);
  const inactiveSessions = sessions.filter((s: Session) => !s.active);

  return (
    <>
      <Stack gap="xl">
        <Group justify="space-between">
          <div>
            <Title order={2}>Telegram Sessions</Title>
            <Text c="dimmed" size="sm">
              Managing Telegram session files
            </Text>
          </div>
          <Group>
            <Button
              variant="subtle"
              leftSection={<IconRefresh size={16} />}
              onClick={loadSessions}
              loading={isLoading}
            >
              Refresh
            </Button>
            <Button leftSection={<IconPlus size={16} />} onClick={() => setShowSetup(true)}>
              New Session
            </Button>
          </Group>
        </Group>

        {activeSessions.length > 0 && (
          <Card shadow="sm" padding="lg" radius="md" withBorder>
            <Card.Section withBorder inheritPadding py="xs">
              <Group>
                <IconCheck size={20} color="green" />
                <Text fw={500}>Active Sessions</Text>
                <Badge color="green" variant="light">
                  {activeSessions.length}
                </Badge>
              </Group>
            </Card.Section>

            <Table mt="md">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Session Name</Table.Th>
                  <Table.Th>User</Table.Th>
                  <Table.Th>Username</Table.Th>
                  <Table.Th>ID</Table.Th>
                  <Table.Th>Actions</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {activeSessions.map((session: Session) => (
                  <Table.Tr key={session.name}>
                    <Table.Td>
                      <Text fw={500}>{session.name}</Text>
                    </Table.Td>
                    <Table.Td>
                      {session.user?.first_name} {session.user?.last_name}
                    </Table.Td>
                    <Table.Td>
                      {session.user?.username ? `@${session.user.username}` : '-'}
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs" c="dimmed">
                        {session.user?.id}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <ActionIcon
                        color="red"
                        variant="subtle"
                        onClick={() => handleDeleteSession(session.name)}
                        aria-label={`Delete session ${session.name}`}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Card>
        )}

        {inactiveSessions.length > 0 && (
          <Card shadow="sm" padding="lg" radius="md" withBorder>
            <Card.Section withBorder inheritPadding py="xs">
              <Group>
                <IconAlertCircle size={20} color="orange" />
                <Text fw={500}>Inactive Sessions</Text>
                <Badge color="orange" variant="light">
                  {inactiveSessions.length}
                </Badge>
              </Group>
            </Card.Section>

            <Table mt="md">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Session Name</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>Actions</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {inactiveSessions.map((session: Session) => (
                  <Table.Tr key={session.name}>
                    <Table.Td>
                      <Text fw={500}>{session.name}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" c="dimmed">
                        {session.error || 'Not authenticated'}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <ActionIcon
                        color="red"
                        variant="subtle"
                        onClick={() => handleDeleteSession(session.name)}
                        aria-label={`Delete session ${session.name}`}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Card>
        )}

        {sessions.length === 0 && !isLoading && (
          <Paper p="xl" ta="center" c="dimmed">
            <IconUser size={48} stroke={1} />
            <Text mt="md">No sessions found</Text>
            <Text size="sm">Create new session to start</Text>
          </Paper>
        )}
      </Stack>

      <Modal
        opened={showSetup || setupStep !== 'initial'}
        onClose={handleCloseModal}
        title="Create new Telegram Session"
        size="md"
        closeOnClickOutside={setupStep === 'initial'}
      >
        <LoadingOverlay visible={isLoading} />

        {error && (
          <Alert
            icon={<IconAlertCircle size={16} />}
            title="Fehler"
            color="red"
            mb="md"
            onClose={() => resetSetup()}
            withCloseButton={setupStep === 'initial'}
          >
            {error}
          </Alert>
        )}

        {setupStep === 'completed' && currentSetup && (
          <Stack>
            <Alert color="green" icon={<IconCheck size={16} />}>
              Session "{currentSetup.sessionName}" created successfully!
            </Alert>

            {currentSetup.user && (
              <Card withBorder>
                <Stack gap="xs">
                  <Text size="sm" c="dimmed">
                    Authenticated as:
                  </Text>
                  <Text fw={500}>
                    {currentSetup.user.first_name} {currentSetup.user.last_name}
                  </Text>
                  {currentSetup.user.username && (
                    <Text size="sm" c="dimmed">
                      @{currentSetup.user.username}
                    </Text>
                  )}
                  <Text size="xs" c="dimmed">
                    ID: {currentSetup.user.id}
                  </Text>
                </Stack>
              </Card>
            )}

            <Button fullWidth onClick={handleCompleteSetup}>
              Finish
            </Button>
          </Stack>
        )}

        {setupStep === 'initial' && (
          <form onSubmit={handleStartSetup}>
            <Stack>
              <TextInput
                label="Session Name"
                placeholder="z.B. main, bot, test"
                value={sessionName}
                onChange={(e) => setSessionName(e.target.value)}
                required
                data-autofocus
              />

              <TextInput
                label="Phone Number"
                placeholder="+49123456789"
                leftSection={<IconPhone size={16} />}
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
              />

              <Text size="xs" c="dimmed">
                The session file will be saved as "{sessionName}.session".
              </Text>

              <Button type="submit" fullWidth disabled={!phone.trim() || !sessionName.trim()}>
                Request 2FA-Code
              </Button>
            </Stack>
          </form>
        )}

        {setupStep === 'code_sent' && currentSetup && (
          <form onSubmit={handleVerifyCode}>
            <Stack>
              <Alert color="blue" icon={<IconCheck size={16} />}>
                {currentSetup.message}
              </Alert>

              <TextInput
                label="2FA-Code"
                placeholder="12345"
                leftSection={<IconKey size={16} />}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
                data-autofocus
              />

              <Group justify="space-between">
                <Button variant="subtle" onClick={cancelSetup}>
                  Cancel
                </Button>
                <Button type="submit" disabled={!code.trim()}>
                  Confirm Code
                </Button>
              </Group>
            </Stack>
          </form>
        )}

        {setupStep === 'password_required' && (
          <form onSubmit={handleVerifyPassword}>
            <Stack>
              <Alert color="orange" icon={<IconLock size={16} />}>
                Two-factor authentication is enabled. Please enter your password.
              </Alert>

              <TextInput
                label="2FA-Passwort"
                type="password"
                placeholder="Dein 2FA-Passwort"
                leftSection={<IconLock size={16} />}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                data-autofocus
              />

              <Group justify="space-between">
                <Button variant="subtle" onClick={cancelSetup}>
                  Cancel
                </Button>
                <Button type="submit" disabled={!password.trim()}>
                  Authenticate
                </Button>
              </Group>
            </Stack>
          </form>
        )}
      </Modal>
    </>
  );
};
