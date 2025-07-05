import { useEffect, useState } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { authFetch } from '@/utils/authFetch';

const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api';

export function ProtectedRoute() {
  const [allowed, setAllowed] = useState<boolean | null>(null); // null = checking

  useEffect(() => {
    authFetch(`${apiUrl}/auth/user`)
      .then((res) => setAllowed(res.ok))
      .catch(() => setAllowed(false));
  }, []);

  // still checking? render nothing or a spinner
  if (allowed === null) return null;                 // or <Loader />

  // not allowed → bounce to login
  if (!allowed) return <Navigate to="/login" replace />;

  // allowed → show the protected tree
  return <Outlet />;
}
