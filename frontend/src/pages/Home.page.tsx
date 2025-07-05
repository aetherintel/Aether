import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import { useEffect } from 'react';

export function HomePage() {
  useEffect(() => {
    document.title = 'Home - Æther';
  }, []);
  
  return (
    <>
      <BreadcrumbsBar />
    </>
  );
}
