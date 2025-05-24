import { useNavigate } from 'react-router-dom';
import {
  Anchor,
  Button,
  Checkbox,
  Container,
  Group,
  Paper,
  PasswordInput,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { keycloakLogin, type LoginCredentials } from '../../context/auth';
import { useAuthStore } from '../../store/client/authStore';
import classes from './Authentication.module.css';

export function Authentication() {
  const { login } = useAuthStore();
  const navigate = useNavigate();

  const form = useForm<LoginCredentials>({
    initialValues: {
      username: '',
      password: '',
    },

    validate: {
      username: (value) => (value.trim().length > 0 ? null : 'Benutzername erforderlich'),
      password: (value) => (value.length >= 6 ? null : 'Mindestens 6 Zeichen'),
    },
  });

  const handleLogin = async (values: LoginCredentials) => {
    try {
      const response = await keycloakLogin(values);
      // Store token (localStorage, context, etc.)
      login(response.access_token);

      navigate('/'); // Redirect after successful login

      notifications.show({
        title: 'Login erfolgreich',
        message: 'Willkommen zurück!',
        color: 'green',
      });
    } catch (err) {
      notifications.show({
        title: 'Login fehlgeschlagen',
        message: 'E-Mail oder Passwort ist falsch',
        color: 'red',
      });
    }
  };

  return (
    <Container size={420} my={40}>
      <Title ta="center" className={classes.title}>
        Welcome back!
      </Title>

      <Text className={classes.subtitle}>
        Do not have an account yet? <Anchor>Create account</Anchor>
      </Text>

      <Paper withBorder shadow="sm" p={22} mt={30} radius="md">
        <form onSubmit={form.onSubmit(handleLogin)}>
          <TextInput
            label="Email"
            placeholder="you@mantine.dev"
            required
            radius="md"
            {...form.getInputProps('username')}
          />
          <PasswordInput
            label="Password"
            placeholder="Your password"
            required
            mt="md"
            radius="md"
            {...form.getInputProps('password')}
          />
          <Group justify="space-between" mt="lg">
            <Checkbox label="Remember me" />
            <Anchor component="button" size="sm">
              Forgot password?
            </Anchor>
          </Group>
          <Button fullWidth mt="xl" radius="md" type="submit">
            Sign in
          </Button>
        </form>
      </Paper>
    </Container>
  );
}
