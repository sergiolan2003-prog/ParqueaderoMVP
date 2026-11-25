import { useEffect, useState } from "react";

import { apiClient } from "./api/client.js";
import { PanelOperador } from "./components/PanelOperador.jsx";

export default function App() {
  const [health, setHealth] = useState({ status: "loading", message: "" });

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
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <strong>PARQUEA</strong> <span className="brand-tag">LPR</span>
        </div>
        <nav className="topbar-nav">
          <span className="nav-active">Operación</span>
        </nav>
      </header>

      <main className="main-container">
        <PanelOperador />
      </main>

      <footer className="statusbar">
        <p role="status">
          Estado de la API:{" "}
          {health.status === "loading" ? "consultando..." : health.status}
        </p>
        {health.message && <p role="alert">{health.message}</p>}
      </footer>
    </div>
  );
}