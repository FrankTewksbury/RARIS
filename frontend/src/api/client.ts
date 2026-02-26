const BASE_URL = "/api";

let _apiKey: string | null = null;

/** Set the API key for authenticated requests. */
export function setApiKey(key: string | null) {
  _apiKey = key;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };

  if (_apiKey) {
    headers["X-API-Key"] = _apiKey;
  }

  let response = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  // Retry once on 429 with Retry-After
  if (response.status === 429) {
    const retryAfter = parseInt(response.headers.get("Retry-After") || "2", 10);
    await new Promise((resolve) => setTimeout(resolve, retryAfter * 1000));
    response = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) =>
    request<T>(path, { method: "DELETE" }),
};
