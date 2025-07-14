import { useEffect } from 'react';
import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import { CreateCaseFileForm } from '../components/CreateCaseFile/CreateCaseFileForm';

export function CreateCaseFilePage() {
  useEffect(() => {
    document.title = 'Create Case - Æther';
  }, []);

  return (
    <div>
      <BreadcrumbsBar overrides={{ [`/cases/createCaseFile`]: 'Create new case' }} />
      <CreateCaseFileForm />
    </div>
  );
}
