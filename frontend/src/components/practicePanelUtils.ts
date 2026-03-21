export function saveStatusMessage(
  userConfirmed: boolean,
  saving: boolean,
  dirty: boolean,
  lastSavedAt: number | null
): string {
  if (userConfirmed) return "Locked after confirmation.";
  if (saving) return "Saving draft…";
  if (dirty) return "Unsaved changes — will autosave shortly.";
  if (lastSavedAt != null) return "All changes saved.";
  return "Draft autosaves as you type.";
}

export function fileExt(filename: string): string {
  const i = filename.lastIndexOf(".");
  return i >= 0 ? filename.slice(i + 1).toUpperCase() : "FILE";
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
