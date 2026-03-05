import { useState } from 'react';
import { Modal, Stack, Text, TextInput, PasswordInput, Button, Group, Alert } from '@mantine/core';
import { IconLock, IconAlertCircle } from '@tabler/icons-react';
import { useAuthStore } from '@/store/client/authStore';
import { keycloakLogin } from '@/context/auth';

export function SessionExpiredModal() {
  const { sessionExpired, setSessionExpired, login, logout } = useAuthStore();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleReLogin = async () => {
    if (!username || !password) return;
    setLoading(true);
    setError('');
    try {
      const response = await keycloakLogin({ username, password });
      login(
        response.access_token,
        (response as any).refresh_token,
        (response as any).expires_in
      );
      setSessionExpired(false);
      setUsername('');
      setPassword('');
    } catch {
      setError('Invalid credentials, please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    window.location.href = '/login';
  };

  return (
    <Modal
      opened={sessionExpired}
      onClose={() => {}} // not closeable — user must re-auth or logout
      withCloseButton={false}
      closeOnClickOutside={false}
      closeOnEscape={false}
      title={
        <Group gap="xs">
          <IconLock size={18} />
          <Text fw={600}>Session expired</Text>
        </Group>
      }
      centered
      size="sm"
      overlayProps={{ blur: 4, backgroundOpacity: 0.6 }}
    >
      <Stack gap="md">
        <Text size="sm" c="dimmed">
          Your session has expired. Re-enter your credentials to continue — your current page and work are preserved.
        </Text>

        {error && (
          <Alert icon={<IconAlertCircle size={16} />} color="red" variant="light">
            {error}
          </Alert>
        )}

        <TextInput
          label="Username"
          placeholder="Your username"
          value={username}
          onChange={(e) => setUsername(e.currentTarget.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleReLogin()}
          autoFocus
        />
        <PasswordInput
          label="Password"
          placeholder="Your password"
          value={password}
          onChange={(e) => setPassword(e.currentTarget.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleReLogin()}
        />

        <Group justify="space-between" mt="xs">
          <Button variant="subtle" color="gray" size="sm" onClick={handleLogout}>
            Log out
          </Button>
          <Button
            size="sm"
            loading={loading}
            disabled={!username || !password}
            onClick={handleReLogin}
          >
            Continue
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
