import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import App from "./App.jsx";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("consulta y muestra el estado de la API", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ status: "ok" }),
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  expect(await screen.findByRole("status")).toHaveTextContent(
    "Estado de la API: ok",
  );
  expect(fetchMock).toHaveBeenCalledWith(
    "/health",
    expect.objectContaining({
      method: "GET",
      headers: expect.any(Headers),
      signal: expect.any(AbortSignal),
    }),
  );
});
