import { useEffect, useRef } from 'react';
import { useAuthStore } from '@/store/client/authStore';

const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api';

export type SSEEvent = {
  type: 'message_status_changed';
  message_id: string;
  owner_id?: string;
  updates: Record<string, string | null>;
} | {
  type: 'new_message';
  channel_id: string;
  [key: string]: unknown;
} | {
  type: 'new_channel';
  channel_id: string;
  [key: string]: unknown;
} | {
  type: 'heartbeat';
};

type SSEHandler = (event: SSEEvent) => void;

/**
 * Opens a persistent SSE connection to /events/stream.
 * Calls `onEvent` whenever the server pushes an event.
 * Automatically reconnects on connection drop.
 * Closes cleanly when the component unmounts.
 */
export function useSSE(onEvent: SSEHandler) {
  const token = useAuthStore((s) => s.token);
  const onEventRef = useRef<SSEHandler>(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!token) return;

    let es: EventSource | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
    let destroyed = false;

    const connect = () => {
      if (destroyed) return;

      // EventSource doesn't support custom headers — pass token as query param.
      // The backend reads it from Authorization header via Depends(user_ctx).
      // We work around this by using a short-lived token in the URL, which the
      // backend already supports via the ?token= query parameter fallback.
      const url = `${apiUrl}/events/stream?token=${encodeURIComponent(token)}`;
      es = new EventSource(url);

      es.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data) as SSEEvent;
          onEventRef.current(data);
        } catch {
          // ignore malformed frames
        }
      };

      es.onerror = () => {
        es?.close();
        es = null;
        if (!destroyed) {
          reconnectTimeout = setTimeout(connect, 3000);
        }
      };
    };

    connect();

    return () => {
      destroyed = true;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      es?.close();
    };
  }, [token]);
}
