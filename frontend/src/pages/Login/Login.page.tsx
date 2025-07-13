import { Link, useNavigate } from 'react-router-dom';
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
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { keycloakLogin, type LoginCredentials } from '../../context/auth';
import { useAuthStore } from '../../store/client/authStore';
import classes from './Login.module.css';
import { useEffect } from 'react';
import Logo from '@/components/Logo';

export function Login() {
  useEffect(() => {
    document.title = 'Login - Æther';

    // Force a custom background color for the login page
    document.body.style.backgroundColor = '#238be6';

    return () => {
      document.body.style.backgroundColor = '';
    };
  }, []);

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
        title: 'Login successful',
        message: 'Welcome back!',
        color: 'green',
      });
    } catch (err) {
      notifications.show({
        title: 'Login failed',
        message: 'E-mail or password is wrong',
        color: 'red',
      });
    }
  };

  return (
    <Container size={420} my={40}>
      <Logo />

      <Text className={classes.subtitle} c="white">
        Do not have an account yet?{' '}
        <Anchor component={Link} to="/register" c="white" td="underline">
          Create account
        </Anchor>
      </Text>

      <Paper withBorder shadow="sm" p={22} mt={30} radius="md">
        <form onSubmit={form.onSubmit(handleLogin)}>
          <TextInput
            label="Username"
            placeholder="Your username"
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
          </Group>
          <Button fullWidth mt="xl" radius="md" type="submit">
            Sign in
          </Button>
        </form>
      </Paper>
    </Container>
  );
}
