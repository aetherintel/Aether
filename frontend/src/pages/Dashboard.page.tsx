import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import { useEffect } from 'react';

export function Dashboard() {
  useEffect(() => {
    document.title = 'Dashboard - Æther';
  }, []);
  
  return (
    <>
      <BreadcrumbsBar />
    </>
  );
}
