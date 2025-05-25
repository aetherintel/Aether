import { Link, useNavigate } from 'react-router-dom';
import {
  Anchor,
  Button,
  Container,
  Paper,
  PasswordInput,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { keycloakRegister } from '../../context/auth';
import classes from './Register.module.css';

export function Register() {
  const navigate = useNavigate();

  const form = useForm({
    initialValues: {
      username: '',
      email: '',
      firstname: '',
      lastname: '',
      password: '',
      confirmPassword: '',
    },

    validate: {
      username: (value) => (value.trim().length > 0 ? null : 'Benutzername erforderlich'),
      password: (value) => (value.length >= 6 ? null : 'Mindestens 6 Zeichen'),
      confirmPassword: (value, values) =>
        value === values.password ? null : 'Passwörter stimmen nicht überein',
    },
  });

  const handleRegister = async (values: typeof form.values) => {
    try {
      const { username, email, firstname, lastname, password } = values;
      const response = await keycloakRegister({ username, email, firstname, lastname, password });

      notifications.show({
        title: 'Login erfolgreich',
        message: response.token_type || 'Welcone back!',
        color: 'green',
      });
      navigate('/login');
    } catch (err: any) {
      notifications.show({
        title: 'Login fehlgeschlagen',
        message: err.message || 'Unknown error',
        color: 'red',
      });
    }
  };

  return (
    <Container size={420} my={40}>
      <Title ta="center" className={classes.title}>
        HTIT-Monitor
      </Title>

      <Text className={classes.subtitle}>
        Already have an account?{' '}
        <Anchor component={Link} to="/login">
          Sign in
        </Anchor>
      </Text>

      <Paper withBorder shadow="sm" p={22} mt={30} radius="md">
        <form onSubmit={form.onSubmit(handleRegister)}>
          <TextInput
            label="Username"
            placeholder="Username"
            required
            mt="md"
            radius="md"
            {...form.getInputProps('username')}
          />
          <TextInput
            label="Email"
            placeholder="you@example.com"
            required
            mt="md"
            radius="md"
            {...form.getInputProps('email')}
          />
          <TextInput
            label="Firstname"
            placeholder="Firstname"
            required
            mt="md"
            radius="md"
            {...form.getInputProps('firstname')}
          />
          <TextInput
            label="Lastname"
            placeholder="Lastname"
            required
            mt="md"
            radius="md"
            {...form.getInputProps('lastname')}
          />
          <PasswordInput
            label="Password"
            placeholder="Your password"
            required
            mt="md"
            radius="md"
            {...form.getInputProps('password')}
          />
          <PasswordInput
            label="Repeat password"
            placeholder="Your password again"
            required
            mt="md"
            radius="md"
            {...form.getInputProps('confirmPassword')}
          />
          <Button fullWidth mt="xl" radius="md" type="submit">
            Create account
          </Button>
        </form>
      </Paper>
    </Container>
  );
}
