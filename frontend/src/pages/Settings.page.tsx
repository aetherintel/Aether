import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import { TelegramSessionSetup } from '@/components/TelegramSessionSetup';
import { useEffect } from 'react';

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
