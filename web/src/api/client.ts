import { currentToken, userManager } from "../auth/AuthProvider";

/** "central" is the referral platform; the others are each institution's own system. */
export type Service = "central" | "drali" | "chughtai" | "ziauddin" | "akuh";

export class ApiError extends Error {
  status: number;
  code: string;
  detail: Record<string, unknown>;
  constructor(status: number, code: string, message: string, detail: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

async function parseError(resp: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await resp.json();
  } catch {
    /* not JSON */
  }
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (detail && typeof detail === "object") {
    const d = detail as Record<string, unknown>;
    return new ApiError(resp.status, String(d.code ?? resp.status), String(d.message ?? resp.statusText), d);
  }
  const fallback: Record<number, string> = {
    401: "Your session has ended. Please sign in again.",
    403: "You do not have permission for this action.",
    404: "Not found.",
    409: "This item changed or is in a state that does not allow this action.",
    503: "A service is temporarily unavailable. Try again shortly.",
  };
  return new ApiError(resp.status, String(resp.status), typeof detail === "string" ? detail : fallback[resp.status] ?? "Request failed");
}

export async function request<T = unknown>(service: Service, path: string, init: RequestInit = {}): Promise<T> {
  const token = await currentToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const resp = await fetch(`/api/${service}${path}`, { ...init, headers });
  if (resp.status === 401) {
    const err = await parseError(resp);
    if (err.code === "account_disabled" || err.code === "unauthenticated") {
      await userManager.removeUser();
    }
    throw err;
  }
  if (!resp.ok) throw await parseError(resp);
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const api = {
  get: <T,>(path: string, service: Service = "central") => request<T>(service, path),
  post: <T,>(path: string, body?: unknown, service: Service = "central") =>
    request<T>(service, path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
  put: <T,>(path: string, body: unknown, service: Service = "central") =>
    request<T>(service, path, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T,>(path: string, body: unknown, service: Service = "central") =>
    request<T>(service, path, { method: "PATCH", body: JSON.stringify(body) }),
  upload: <T,>(path: string, form: FormData) => request<T>("central", path, { method: "POST", body: form }),
};

/** Fetch a protected binary (document, page image or result image) and return an object URL. */
export async function fetchBlobUrl(path: string, service: Service = "central"): Promise<string> {
  const token = await currentToken();
  const resp = await fetch(`/api/${service}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!resp.ok) throw await parseError(resp);
  return URL.createObjectURL(await resp.blob());
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong";
}
