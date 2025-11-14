// src/App.tsx
import { MantineProvider } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import { Router } from './Router';
import { theme } from './theme';

// Create QueryClient with default options
function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000, // Data is fresh for 1 minute
        retry: 1, // Retry failed requests once
        refetchOnWindowFocus: false, // Don't refetch on window focus
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined = undefined;

function getQueryClient() {
  if (typeof window === 'undefined') {
    // Server: always make a new query client
    return makeQueryClient();
  } else {
    // Browser: make a new query client if we don't already have one
    if (!browserQueryClient) browserQueryClient = makeQueryClient();
    return browserQueryClient;
  }
}

export default function App() {
  const [queryClient] = useState(() => getQueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      <MantineProvider theme={theme}>
        <Notifications />
        <Router />
      </MantineProvider>
    </QueryClientProvider>
  );
}