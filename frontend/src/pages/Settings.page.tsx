import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import { TelegramSessionSetup } from '@/components/TelegramSessionSetup';

export function Settings() {
  return (
    <>
      <BreadcrumbsBar />
      <TelegramSessionSetup />
    </>
  );
}
