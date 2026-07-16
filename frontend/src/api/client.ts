import { TOKEN_KEY } from "../constants";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (response.status === 204) {
    return undefined as T;
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "요청에 실패했습니다.";
    throw new Error(detail);
  }
  return data as T;
}

export async function authorizedRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) throw new Error("로그인이 필요합니다.");
  return request<T>(path, { ...options, headers: { Authorization: `Bearer ${token}`, ...options.headers } });
}

export async function uploadRequest<T>(path: string, body: FormData): Promise<T> {
  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) throw new Error("로그인이 필요합니다.");
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "업로드에 실패했습니다.";
    throw new Error(detail);
  }
  return data as T;
}

export async function authorizedBlob(path: string): Promise<Blob> {
  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) throw new Error("로그인이 필요합니다.");
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = typeof data.detail === "string" ? data.detail : "파일을 불러오지 못했습니다.";
    throw new Error(detail);
  }
  return response.blob();
}
