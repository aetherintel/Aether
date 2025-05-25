import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import { CreateCaseFileForm } from '../components/CreateCaseFile/CreateCaseFileForm';

export function CreateCaseFilePage() {
  return (
    <div>
      <BreadcrumbsBar />
      <h1>Create New Case File</h1>
      <CreateCaseFileForm />
    </div>
  );
}
