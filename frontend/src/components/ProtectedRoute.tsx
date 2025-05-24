import { Navigate, Outlet } from 'react-router-dom';

export function ProtectedRoute() {
  const token = localStorage.getItem('token');

  // TODO: verify token with backend here
  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
