import { afterEach, expect, it, vi } from "vitest";

import { getCurrentUser, login } from "./authService.js";

afterEach(() => {
  vi.unstubAllGlobals();
});

it("uses the existing OAuth form contract and authenticated-user route", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ access_token: "jwt", token_type: "bearer" }),
    })
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        username: "operator",
        rol: "OPERADOR",
        activo: true,
      }),
    });
  vi.stubGlobal("fetch", fetchMock);

  await login("operator", "not-stored");
  await getCurrentUser();

  expect(fetchMock.mock.calls[0][0]).toBe("/auth/login");
  expect(fetchMock.mock.calls[0][1].body).toBe(
    "username=operator&password=not-stored",
  );
  expect(fetchMock.mock.calls[1][0]).toBe("/auth/me");
});
