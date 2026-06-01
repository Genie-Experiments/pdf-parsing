/**
 * API client for the PDF Parser backend.
 *
 * All requests use `credentials: "include"` so the browser automatically
 * sends the httpOnly session cookie set by the OAuth flow.
 * No token is ever stored in or read from JavaScript (XSS-safe).
 *
 * On 401 / 403, the client redirects to /login.
 */

export const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export type JobStatus = "queued" | "running" | "done" | "failed" | "cancelled";

export interface Job {
  id: string;
  user_email: string;
  filename: string;
  status: JobStatus;
  page?: number | null;  // null/undefined = full PDF; N = single page (1-indexed)
  created_at: string;
  updated_at: string;
  error_message?: string;
  current_step: number;
}

export interface JobResult {
  markdown: string;
  pdf_url: string;
}

export interface JobStats {
  queued: number;
  running: number;
  done: number;
  failed: number;
}


// ── internal helpers ─────────────────────────────────────────────────────────

function redirectToLogin(): never {
  if (typeof window !== "undefined") window.location.href = "/login";
  throw new Error("Not authenticated");
}

async function apiFetch(input: RequestInfo, init?: RequestInit): Promise<Response> {
  const res = await fetch(input, { credentials: "include", ...init });
  if (res.status === 401 || res.status === 403) redirectToLogin();
  return res;
}

// ── auth ─────────────────────────────────────────────────────────────────────

export async function getMe(): Promise<{ email: string }> {
  const res = await fetch(`${BASE}/auth/me`, { credentials: "include" });
  if (!res.ok) throw new Error("Not authenticated");
  return res.json();
}

export interface UserQuota {
  bypassed: boolean;
  pages_used: number;
  page_quota: number;
  pages_remaining: number;
}

export async function getQuota(): Promise<UserQuota> {
  const res = await apiFetch(`${BASE}/auth/quota`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function logout(): Promise<void> {
  await fetch(`${BASE}/auth/logout`, { method: "POST", credentials: "include" });
}

// ── job CRUD ─────────────────────────────────────────────────────────────────

export interface UploadOptions {
  page?: number;
  segmentsToRefine?: string[];
}

export async function uploadPdf(file: File, options?: UploadOptions): Promise<Job> {
  const form = new FormData();
  form.append("file", file);
  if (options?.page !== undefined) form.append("page", String(options.page));
  if (options?.segmentsToRefine?.length) {
    form.append("segments_to_refine", options.segmentsToRefine.join(","));
  }
  const res = await apiFetch(`${BASE}/jobs`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listJobs(scope: "mine" | "all" = "all"): Promise<Job[]> {
  const res = await apiFetch(`${BASE}/jobs?scope=${scope}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getJob(id: string): Promise<Job> {
  const res = await apiFetch(`${BASE}/jobs/${id}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getJobResult(id: string): Promise<JobResult> {
  const res = await apiFetch(`${BASE}/jobs/${id}/result`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getJobPdfUrl(id: string): Promise<string> {
  const res = await apiFetch(`${BASE}/jobs/${id}/pdf`);
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data.pdf_url;
}

export async function deleteJob(id: string): Promise<void> {
  const res = await apiFetch(`${BASE}/jobs/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error(await res.text());
}

export async function getJobStats(scope: "mine" | "all" = "all"): Promise<JobStats> {
  const res = await apiFetch(`${BASE}/jobs/stats?scope=${scope}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── SSE log stream ────────────────────────────────────────────────────────────

export function streamLogs(
  jobId: string,
  onLine: (line: string) => void,
  onDone: () => void,
  onError: () => void,
): () => void {
  // withCredentials=true ensures the browser sends the session cookie with the
  // EventSource request (EventSource cannot set custom Authorization headers).
  const es = new EventSource(`${BASE}/jobs/${jobId}/logs`, { withCredentials: true });

  es.onmessage = (e) => {
    const line: string = e.data;
    if (line === "__DONE__") {
      onDone();
      es.close();
    } else if (line === "__ERROR__") {
      onError();
      es.close();
    } else {
      onLine(line);
    }
  };

  es.onerror = () => {
    onError();
    es.close();
  };

  return () => es.close();
}
