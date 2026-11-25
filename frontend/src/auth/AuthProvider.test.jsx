import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import AuthProvider from "./AuthProvider.jsx";
import RequireAuth from "./RequireAuth.jsx";
import useAuth from "./useAuth.js";
import { clearAccessToken } from "./tokenStore.js";

function AuthProbe() {
  const { isAuthenticated, login, logout, user } = useAuth();

  return (
    <>
      <button onClick={() => login("operator", "test-password")}>Iniciar sesión</button>
      <button onClick={logout}>Cerrar sesión</button>
      <p role="status">{user?.rol ?? "sin sesión"}</p>
      <p>{isAuthenticated ? "autenticado" : "no autenticado"}</p>
      <RequireAuth
        allowedRoles={["OPERADOR"]}
        fallback={<p>Acceso denegado</p>}
      >
        <p>Área de operador</p>
      </RequireAuth>
      <RequireAuth
        allowedRoles={["ADMINISTRADOR"]}
        fallback={<p>Acceso de administrador denegado</p>}
      >
        <p>Área administrativa</p>
      </RequireAuth>
    </>
  );
}

afterEach(() => {
  clearAccessToken();
  vi.unstubAllGlobals();
});

it("keeps the JWT in memory, loads the current role, and clears on logout", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ access_token: "test-jwt", token_type: "bearer" }),
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
  render(
    <AuthProvider>
      <AuthProbe />
    </AuthProvider>,
  );

  fireEvent.click(screen.getByRole("button", { name: "Iniciar sesión" }));

  expect(await screen.findByText("Área de operador")).toBeInTheDocument();
  expect(screen.getByText("Acceso de administrador denegado")).toBeInTheDocument();
  expect(screen.queryByText("Área administrativa")).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("OPERADOR");
  expect(fetchMock.mock.calls[1][1].headers.get("Authorization")).toBe(
    "Bearer test-jwt",
  );
  expect(localStorage.getItem("access_token")).toBeNull();

  fireEvent.click(screen.getByRole("button", { name: "Cerrar sesión" }));
  await waitFor(() => {
    expect(screen.getByRole("status")).toHaveTextContent("sin sesión");
    expect(screen.getByText("Acceso denegado")).toBeInTheDocument();
  });
});
