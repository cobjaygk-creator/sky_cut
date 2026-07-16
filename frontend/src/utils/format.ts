export function formatTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remain = Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0");
  return `${minutes}:${remain}`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
