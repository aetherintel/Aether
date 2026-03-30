export interface ContainerInfo {
  id: string;
  name: string;
  image: string;
  status: string;
  labels?: {
    queue?: string;
    channels?: string;
    mode?: string;
    case_id?: string;
  };
  queue?: string;
  channels?: string;
  mode?: string;
  case_id?: string | number;
  session?: string;
  runtime?: string;
  created?: string;
}

export const mapJobStatus = (status: string): string => {
  const statusMap: Record<string, string> = {
    queued: 'pending',
    pending: 'pending',
    started: 'running',
    running: 'running',
    finished: 'exited',
    exited: 'exited',
    failed: 'failed',
  };
  return statusMap[status] || status;
};
