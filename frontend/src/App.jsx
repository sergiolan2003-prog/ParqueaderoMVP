import { useEffect, useState } from "react";

import { apiClient } from "./api/client.js";
import AccessDenied from "./pages/AccessDenied.jsx";
import AdminPanel from "./pages/AdminPanel.jsx";
import LoginForm from "./components/LoginForm.jsx";
import RequireAuth from "./auth/RequireAuth.jsx";
import useAuth from "./auth/useAuth.js";

export default function App() {
  const [health, setHealth] = useState({ status: "loading", message: "" });
  const { error, isAuthenticated, isLoading, login, logout, user } = useAuth();

  useEffect(() => {
    let active = true;
    apiClient
      .get("/health")
      .then((data) => {
        if (active) {
          setHealth({ status: data.status, message: "" });
        }
      })
      .catch((error) => {
        if (active) {
          setHealth({ status: "error", message: error.message });
        }
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="app-root">
      <div className="health-strip">
        <p role="status">
          Estado de la API:{" "}
          {health.status === "loading" ? "consultando..." : health.status}
        </p>
        {health.message && <p role="alert">{health.message}</p>}
      </div>
      {isLoading ? (
        <main className="session-loading">
          <p className="eyebrow">Parqueadero</p>
          <h1>Validando sesión...</h1>
        </main>
      ) : !isAuthenticated ? (
        <LoginForm
          error={error?.message}
          loading={isLoading}
          onSubmit={login}
        />
      ) : (
        <RequireAuth
          allowedRoles={["ADMINISTRADOR"]}
          fallback={<AccessDenied onLogout={logout} username={user.username} />}
          loadingFallback={
            <main className="session-loading">
              <h1>Validando permisos...</h1>
            </main>
          }
        >
          <AdminPanel health={health} onLogout={logout} user={user} />
        </RequireAuth>
      )}
    </div>
  );
}
