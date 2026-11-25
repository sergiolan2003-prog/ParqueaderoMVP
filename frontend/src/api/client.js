import { clearAccessToken, getAccessToken } from "../auth/tokenStore.js";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");
const DEFAULT_TIMEOUT_MS = 10000;

export class ApiError extends Error {
  constructor(message, { status = null, code = "API_ERROR", detail = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

function formatDetail(detail) {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item?.msg === "string" ? item.msg : null))
      .filter(Boolean)
      .join("; ");
  }

  return null;
}

function errorMessage(status, detail) {
  if (status === 401) {
    return "La sesión no es válida o ha expirado.";
  }

  if (status === 403) {
    return "No tiene permisos para realizar esta operación.";
  }

  if (status >= 500) {
    return "El servidor encontró un error. Inténtelo de nuevo más tarde.";
  }

  return formatDetail(detail) || `La API respondió con HTTP ${status}.`;
}

function serializeBody(body, headers) {
  if (body === undefined || body === null) {
    return body;
  }

  if (body instanceof URLSearchParams) {
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/x-www-form-urlencoded;charset=UTF-8");
    }
    return body.toString();
  }

  if (typeof FormData !== "undefined" && body instanceof FormData) {
    return body;
  }

  if (typeof body === "string") {
    return body;
  }

  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return JSON.stringify(body);
}

async function readResponse(response) {
  if (response.status === 204) {
    return null;
  }

  try {
    return await response.json();
  } catch {
    if (response.ok) {
      throw new ApiError("La API devolvió una respuesta JSON inválida.", {
        status: response.status,
        code: "INVALID_RESPONSE",
      });
    }
    return null;
  }
}

export class ApiClient {
  constructor({
    baseUrl = API_BASE_URL,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    fetchImpl = (...args) => fetch(...args),
    getToken = getAccessToken,
    onUnauthorized = clearAccessToken,
  } = {}) {
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
      throw new RangeError("timeoutMs debe ser un número positivo.");
    }

    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.timeoutMs = timeoutMs;
    this.fetchImpl = fetchImpl;
    this.getToken = getToken;
    this.onUnauthorized = onUnauthorized;
  }

  get(path, options = {}) {
    return this.request(path, { ...options, method: "GET" });
  }

  post(path, body, options = {}) {
    return this.request(path, { ...options, method: "POST", body });
  }

  put(path, body, options = {}) {
    return this.request(path, { ...options, method: "PUT", body });
  }

  async request(path, { method = "GET", headers: inputHeaders, body } = {}) {
    const requestHeaders = new Headers(inputHeaders);
    const token = this.getToken();
    if (token) {
      requestHeaders.set("Authorization", `Bearer ${token}`);
    }

    const requestBody = serializeBody(body, requestHeaders);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);
    const url = `${this.baseUrl}${path.startsWith("/") ? path : `/${path}`}`;

    let response;
    try {
      response = await this.fetchImpl(url, {
        method,
        headers: requestHeaders,
        body: requestBody,
        signal: controller.signal,
      });
    } catch {
      if (controller.signal.aborted) {
        throw new ApiError("La solicitud superó el tiempo de espera.", {
          code: "TIMEOUT",
        });
      }

      throw new ApiError("No fue posible conectarse con el servidor.", {
        code: "NETWORK_ERROR",
      });
    } finally {
      clearTimeout(timeoutId);
    }

    const data = await readResponse(response);
    if (!response.ok) {
      if (response.status === 401) {
        this.onUnauthorized();
      }

      throw new ApiError(errorMessage(response.status, data?.detail), {
        status: response.status,
        code: `HTTP_${response.status}`,
        detail:
          response.status >= 500 ? null : (data?.detail ?? data),
      });
    }

    return data;
  }
}

export const apiClient = new ApiClient();
