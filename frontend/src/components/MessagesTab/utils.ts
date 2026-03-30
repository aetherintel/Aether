export const formatRelativeTime = (dateString: string) => {
  const now = new Date();
  const messageDate = new Date(dateString);
  const diffInSeconds = Math.floor((now.getTime() - messageDate.getTime()) / 1000);

  if (diffInSeconds < 60) {
    return `${diffInSeconds}s ago`;
  } else if (diffInSeconds < 3600) {
    const minutes = Math.floor(diffInSeconds / 60);
    return `${minutes}m ago`;
  } else if (diffInSeconds < 86400) {
    const hours = Math.floor(diffInSeconds / 3600);
    return `${hours}h ago`;
  } else if (diffInSeconds < 2592000) {
    const days = Math.floor(diffInSeconds / 86400);
    return `${days}d ago`;
  }
  return messageDate.toLocaleDateString();
};

export function escapeRegExp(str: string) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export const isVideoFile = (path: string): boolean => {
  const videoExtensions: string[] = ['.mp4', '.webm', '.ogg', '.avi', '.mov', '.wmv', '.flv', '.mkv'];
  return videoExtensions.some((ext: string) => path.toLowerCase().endsWith(ext));
};

export const isAudioFile = (path: string): boolean => {
  const audioExtensions: string[] = ['.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac'];
  return audioExtensions.some((ext: string) => path.toLowerCase().endsWith(ext));
};

export function formatDate(dateString: string | null): string {
  if (!dateString) return 'No valid date provided';
  return new Date(dateString).toLocaleString();
}

export function formatNumber(num?: number): string {
  if (!num) return '0';
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
  return num.toString();
}
