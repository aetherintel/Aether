// src/components/WidgetGrid/SimpleErrorBoundary.tsx
import React, { Component, ReactNode } from 'react';
import { Box, Text, Button, Center, Stack } from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class SimpleErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Widget error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return <>{this.props.fallback}</>;
      }

      return (
        <Center h="100%" p="md">
          <Stack align="center" gap="xs">
            <IconAlertCircle size={32} color="red" />
            <Text c="red" fw={500}>Widget Error</Text>
            <Text size="sm" c="dimmed" ta="center">
              {this.state.error?.message || 'An unexpected error occurred'}
            </Text>
            <Button size="xs" variant="subtle" onClick={this.handleReset}>
              Try Again
            </Button>
          </Stack>
        </Center>
      );
    }

    return this.props.children;
  }
}