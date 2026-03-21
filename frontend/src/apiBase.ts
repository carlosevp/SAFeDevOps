/** Base URL for the FastAPI service (no trailing slash). Empty = same-origin `/api` (dev proxy). */
export function apiUrl(path: string): string {
  const raw = import.meta.env.VITE_API_BASE_URL;
  const base = (typeof raw === "string" ? raw : "").trim().replace(/\/$/, "");
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${base}${p}`;
}
