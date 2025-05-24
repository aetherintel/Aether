import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import AppContainer from './components/AppContainer/AppContainer';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Authentication } from './pages/Authentication/Authentication.page';
import { HomePage } from './pages/Home.page';

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppContainer />,
    children: [
      {
        element: <ProtectedRoute />,
        children: [{ path: '/', element: <HomePage /> }],
      },
    ],
  },
  { path: '/login', element: <Authentication /> },
]);

export function Router() {
  return <RouterProvider router={router} />;
}
