import { useEffect, useState } from "react";

import { apiClient } from "./api/client.js";
import AccessDenied from "./pages/AccessDenied.jsx";
import AdminPanel from "./pages/AdminPanel.jsx";
import LoginForm from "./components/LoginForm.jsx";
import RequireAuth from "./auth/RequireAuth.jsx";
import useAuth from "./auth/useAuth.js";
import { PanelOperador } from "./components/PanelOperador.jsx";
import Alert from "./components/Alert.jsx";
import { IconLogOut } from "./components/Icons.jsx";

function OperatorExperience({ accessToken, onLogout, username }) {
  return (
    <section className="operator-shell">
      <header className="topbar">
        <div className="topbar-left">
          <a className="brand" href="/" aria-label="Parqueadero, inicio">
            PARQUEA<span>+</span>
          </a>
          <nav className="topbar-nav" aria-label="Operación de carril">
            <span className="topbar-tab is-active">Panel del carril</span>
          </nav>
        </div>
        <div className="user-menu">
          <span className="role-label">Operación</span>
          <span className="user-name">{username}</span>
          <button
            className="button button-quiet button-small"
            onClick={onLogout}
            type="button"
          >
            <IconLogOut />
            Cerrar sesión
          </button>
        </div>
      </header>
      <main className="main-container">
        <div style={{ marginBottom: "1.25rem" }}>
          <Alert variant="warning">
            Acceso al panel administrativo denegado. El rol OPERADOR solo puede
            usar el panel de operación.
          </Alert>
        </div>
        <PanelOperador accessToken={accessToken} />
      </main>
    </section>
  );
}

export default function App() {
  const [health, setHealth] = useState({ status: "loading", message: "" });
  const {
    accessToken,
    error,
    isAuthenticated,
    isLoading,
    login,
    logout,
    user,
  } = useAuth();

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

  const healthDotClass =
    health.status === "ok"
      ? "health-ok"
      : health.status === "loading"
        ? "health-loading"
        : "health-error";

  return (
    <div className="app-root">
      <div className="app-main-slot">
        {isLoading ? (
          <main className="session-loading">
            <div style={{ textAlign: "center" }}>
              <p className="eyebrow eyebrow-accent">Parqueadero</p>
              <h1>Validando sesión...</h1>
            </div>
          </main>
        ) : !isAuthenticated ? (
          <LoginForm
            error={error?.message}
            loading={isLoading}
            onSubmit={login}
          />
        ) : user.rol === "ADMINISTRADOR" ? (
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
        ) : user.rol === "OPERADOR" ? (
          <RequireAuth
            allowedRoles={["OPERADOR"]}
            fallback={<AccessDenied onLogout={logout} username={user.username} />}
          >
            <OperatorExperience
              accessToken={accessToken}
              onLogout={logout}
              username={user.username}
            />
          </RequireAuth>
        ) : (
          <AccessDenied onLogout={logout} username={user.username} />
        )}
      </div>

      <footer className="app-footer">
        <div className="health-strip-inline">
          <span className={`health-dot ${healthDotClass}`} aria-hidden="true" />
          <p role="status">
            Estado de la API:{" "}
            {health.status === "loading" ? "consultando..." : health.status}
          </p>
          {health.message && <p role="alert">{health.message}</p>}
        </div>
        <span className="footer-meta">PARQUEA+ · Control operativo LPR</span>
      </footer>
    </div>
  );
}
