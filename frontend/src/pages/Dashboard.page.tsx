import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import { CaseFileList } from '@/components/CaseFileList/CaseFileList';
import { useEffect } from 'react';

export function Dashboard() {
  useEffect(() => {
    document.title = 'Dashboard - Æther';
  }, []);
  
  return (
    <>
      <BreadcrumbsBar />
      <CaseFileList archived={false} />
    </>
  );
}
