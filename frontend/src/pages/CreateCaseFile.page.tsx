import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import { CreateCaseFileForm } from '../components/CreateCaseFile/CreateCaseFileForm';

export function CreateCaseFilePage() {
  return (
    <div>
      <BreadcrumbsBar overrides={{ [`/cases/createCaseFile`]: "Create new case" }} />
      <CreateCaseFileForm />
    </div>
  );
}
