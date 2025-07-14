import { useEffect } from 'react';
import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import { TelegramSessionSetup } from '@/components/TelegramSessionSetup';

export function Settings() {
  useEffect(() => {
    document.title = 'Settings - Æther';
  }, []);

  return (
    <>
      <BreadcrumbsBar />
      <TelegramSessionSetup />
    </>
  );
}
