import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClient, ApiError } from "./client.js";

function response(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  };
}

afterEach(() => {
  vi.useRealTimers();
});

describe("ApiClient", () => {
  it("uses the configured base URL, bearer token, and JSON contract", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(response({ ok: true }));
    const client = new ApiClient({
      baseUrl: "/gateway/",
      fetchImpl,
      getToken: () => "signed-token",
    });

    await client.post("/accesos/entrada", { placa: "ABC123" });

    expect(fetchImpl).toHaveBeenCalledWith(
      "/gateway/accesos/entrada",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ placa: "ABC123" }),
      }),
    );
    const [, options] = fetchImpl.mock.calls[0];
    expect(options.headers.get("Authorization")).toBe("Bearer signed-token");
    expect(options.headers.get("Content-Type")).toBe("application/json");
  });

  it("uses form encoding without serializing login credentials as JSON", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(response({ access_token: "jwt" }));
    const client = new ApiClient({ fetchImpl });
    const form = new URLSearchParams({ username: "operator", password: "secret" });

    await client.post("/auth/login", form);

    const [, options] = fetchImpl.mock.calls[0];
    expect(options.headers.get("Content-Type")).toContain(
      "application/x-www-form-urlencoded",
    );
    expect(options.body).toBe("username=operator&password=secret");
  });

  it("clears the client session on 401", async () => {
    const onUnauthorized = vi.fn();
    const client = new ApiClient({
      fetchImpl: vi.fn().mockResolvedValue(response({ detail: "expired" }, 401)),
      onUnauthorized,
    });

    await expect(client.get("/auth/me")).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      message: "La sesión no es válida o ha expirado.",
    });
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("reports 403 without clearing the current session", async () => {
    const onUnauthorized = vi.fn();
    const client = new ApiClient({
      fetchImpl: vi
        .fn()
        .mockResolvedValue(response({ detail: "No autorizado." }, 403)),
      onUnauthorized,
    });

    await expect(client.get("/auth/admin-check")).rejects.toMatchObject({
      status: 403,
      message: "No tiene permisos para realizar esta operación.",
    });
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it("preserves FastAPI validation details for 422", async () => {
    const client = new ApiClient({
      fetchImpl: vi
        .fn()
        .mockResolvedValue(response({ detail: [{ msg: "placa requerida" }] }, 422)),
    });

    await expect(client.post("/accesos/entrada", {})).rejects.toMatchObject({
      status: 422,
      message: "placa requerida",
    });
  });

  it("does not expose server details for 500 responses", async () => {
    const client = new ApiClient({
      fetchImpl: vi
        .fn()
        .mockResolvedValue(response({ detail: "database password leaked" }, 500)),
    });

    await expect(client.get("/health")).rejects.toMatchObject({
      status: 500,
      message: "El servidor encontró un error. Inténtelo de nuevo más tarde.",
    });
  });

  it("distinguishes timeout from a connection failure", async () => {
    vi.useFakeTimers();
    const fetchImpl = vi.fn(
      (_url, { signal }) =>
        new Promise((resolve, reject) => {
          signal.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        }),
    );
    const client = new ApiClient({ fetchImpl, timeoutMs: 25 });
    const pendingRequest = client.get("/health");
    const timeoutAssertion = expect(pendingRequest).rejects.toMatchObject({
      code: "TIMEOUT",
      message: "La solicitud superó el tiempo de espera.",
    });

    await vi.advanceTimersByTimeAsync(25);
    await timeoutAssertion;
  });

  it("converts network failures into a user-safe API error", async () => {
    const client = new ApiClient({
      fetchImpl: vi.fn().mockRejectedValue(new TypeError("fetch failed")),
    });
    const request = client.get("/health");
    const error = await request.catch((requestError) => requestError);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: "NETWORK_ERROR" });
  });
});
