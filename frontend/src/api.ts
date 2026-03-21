import { apiUrl } from "./apiBase";
import type { ReviewResult, SessionFull } from "./types";

function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  return fetch(url, { ...init, credentials: "include" });
}

export type GateStatus = { gate_enabled: boolean; authenticated: boolean };

export async function getGateStatus(): Promise<GateStatus> {
  const res = await apiFetch(apiUrl("/api/auth/gate/status"));
  if (!res.ok) throw new Error("Could not check access gate.");
  return res.json() as Promise<GateStatus>;
}

export async function gateLogin(password: string): Promise<void> {
  const res = await apiFetch(apiUrl("/api/auth/gate/login"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) {
    let msg = "Incorrect password.";
    try {
      const j = (await res.json()) as { detail?: unknown };
      if (typeof j.detail === "string") msg = j.detail;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
}

function parseApiError(res: Response, body: unknown): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d) && d.length > 0) {
      const first = d[0];
      if (first && typeof first === "object" && "msg" in first) {
        return String((first as { msg: string }).msg);
      }
    }
  }
  if (res.status === 404) return "Not found.";
  if (res.status === 503) return "Service unavailable. Check that the API is running and OPENAI_API_KEY is set.";
  if (res.status >= 500) return "Server error. Try again later.";
  return res.statusText || `HTTP ${res.status}`;
}

async function parseJson<T>(res: Response): Promise<T> {
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok) {
    throw new Error(parseApiError(res, body));
  }
  return body as T;
}

export async function createSession(body: {
  name: string;
  email: string;
  team_name: string;
}): Promise<SessionFull> {
  const res = await apiFetch(apiUrl("/api/sessions"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseJson<SessionFull>(res);
}

export async function getSession(sessionId: number): Promise<SessionFull> {
  const res = await apiFetch(apiUrl(`/api/sessions/${sessionId}`));
  return parseJson<SessionFull>(res);
}

export async function saveDraft(sessionId: number, practiceKey: string, narrative: string): Promise<SessionFull> {
  const res = await apiFetch(apiUrl(`/api/sessions/${sessionId}/practice/${practiceKey}/draft`), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ narrative }),
  });
  return parseJson<SessionFull>(res);
}

export async function uploadFile(sessionId: number, practiceKey: string, file: File): Promise<SessionFull> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await apiFetch(apiUrl(`/api/sessions/${sessionId}/practice/${practiceKey}/files`), {
    method: "POST",
    body: fd,
  });
  return parseJson<SessionFull>(res);
}

export async function deleteFile(sessionId: number, practiceKey: string, fileId: string): Promise<SessionFull> {
  const res = await apiFetch(apiUrl(`/api/sessions/${sessionId}/practice/${practiceKey}/files/${fileId}`), {
    method: "DELETE",
  });
  return parseJson<SessionFull>(res);
}

export async function runReview(sessionId: number, practiceKey: string): Promise<ReviewResult> {
  const res = await apiFetch(apiUrl(`/api/sessions/${sessionId}/practice/${practiceKey}/review`), { method: "POST" });
  return parseJson<ReviewResult>(res);
}

export async function submitFollowup(
  sessionId: number,
  practiceKey: string,
  answers: string[]
): Promise<ReviewResult> {
  const res = await apiFetch(apiUrl(`/api/sessions/${sessionId}/practice/${practiceKey}/followup`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers }),
  });
  return parseJson<ReviewResult>(res);
}

export async function confirmPractice(
  sessionId: number,
  practiceKey: string,
  body: { acknowledge_consolidated_response: boolean; final_narrative: string }
): Promise<SessionFull> {
  const res = await apiFetch(apiUrl(`/api/sessions/${sessionId}/practice/${practiceKey}/confirm`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      acknowledge_consolidated_response: body.acknowledge_consolidated_response,
      final_narrative: body.final_narrative,
    }),
  });
  return parseJson<SessionFull>(res);
}

export async function navigateSession(sessionId: number, index: number): Promise<SessionFull> {
  const res = await apiFetch(apiUrl(`/api/sessions/${sessionId}/navigate/${index}`), { method: "POST" });
  return parseJson<SessionFull>(res);
}

export async function downloadPartialExport(sessionId: number): Promise<{ blob: Blob; filename: string }> {
  const res = await apiFetch(apiUrl(`/api/sessions/${sessionId}/export-partial`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirm_partial: true }),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      if (j?.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail || `HTTP ${res.status}`);
  }
  const cd = res.headers.get("Content-Disposition") || "";
  const match = /filename="?([^";]+)"?/i.exec(cd);
  const filename = match?.[1] || `assessment_export_partial_${sessionId}.zip`;
  const blob = await res.blob();
  return { blob, filename };
}

export async function downloadExport(sessionId: number): Promise<{ blob: Blob; filename: string }> {
  const res = await apiFetch(apiUrl(`/api/sessions/${sessionId}/export`), { method: "POST" });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      if (j?.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail || `HTTP ${res.status}`);
  }
  const cd = res.headers.get("Content-Disposition") || "";
  const match = /filename="?([^";]+)"?/i.exec(cd);
  const filename = match?.[1] || `assessment_export_${sessionId}.zip`;
  const blob = await res.blob();
  return { blob, filename };
}
