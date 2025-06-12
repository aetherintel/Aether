import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import AppContainer from './components/AppContainer/AppContainer';
import { ProtectedRoute } from './components/ProtectedRoute';
import { CaseFileDetail } from './pages/CaseFileDetail.page';
import CaseOverview from './pages/CaseOverview.page';
import { CreateCaseFilePage } from './pages/CreateCaseFile.page';
import { HomePage } from './pages/Home.page';
import { Settings } from './pages/Settings.page';
import { Login } from './pages/Login/Login.page';
import { Register } from './pages/Register/Register.page';

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppContainer />,
    children: [
      {
        element: <ProtectedRoute />,
        children: [{ path: '/', element: <HomePage /> }],
      },
      {
        element: <ProtectedRoute />,
        children: [{ path: '/cases', element: <CaseOverview /> }],
      },
      {
        element: <ProtectedRoute />,
        children: [{ path: '/cases/:id', element: <CaseFileDetail /> }],
      },
      {
        element: <ProtectedRoute />,
        children: [{ path: '/cases/createCaseFile', element: <CreateCaseFilePage /> }],
      },
      {
        element: <ProtectedRoute />,
        children: [{ path: '/account', element: <HomePage /> }],
      },
      {
        element: <ProtectedRoute />,
        children: [{ path: '/settings', element: <Settings /> }],
      },
    ],
  },
  { path: '/login', element: <Login /> },
  { path: '/register', element: <Register /> },
]);

export function Router() {
  return <RouterProvider router={router} />;
}
