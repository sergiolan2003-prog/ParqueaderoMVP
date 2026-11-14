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
    json: async () => ({ status: "ok" }),
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  expect(await screen.findByRole("status")).toHaveTextContent(
    "Estado de la API: ok",
  );
  expect(fetchMock).toHaveBeenCalledWith("/health");
});
