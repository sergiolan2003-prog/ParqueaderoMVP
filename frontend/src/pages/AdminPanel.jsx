import { useState } from "react";

import CapacityPage from "./CapacityPage.jsx";
import ConsultationsPage from "./ConsultationsPage.jsx";
import TariffsPage from "./TariffsPage.jsx";

const tabs = [
  { id: "tarifas", label: "Tarifas" },
  { id: "cupos", label: "Cupos" },
  { id: "consultas", label: "Consultas" },
];

export default function AdminPanel({ health, onLogout, user }) {
  const [activeTab, setActiveTab] = useState("tarifas");

  return (
    <div className="admin-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Parqueadero, inicio">
          PARQUEA<span>+</span>
        </a>
        <div className="topbar-status">
          <span className="role-label">Administración</span>
          <span
            className={`health-dot ${health.status === "ok" ? "health-ok" : "health-error"}`}
            aria-hidden="true"
          />
          <span className="health-label">
            API {health.status === "loading" ? "consultando" : health.status}
          </span>
        </div>
        <div className="user-menu">
          <span>{user.username}</span>
          <button className="button button-quiet" onClick={onLogout} type="button">
            Cerrar sesión
          </button>
        </div>
      </header>

      <main className="admin-main">
        <div className="page-heading">
          <div>
            <p className="eyebrow">Panel de control</p>
            <h1>Administración del parqueadero</h1>
            <p className="muted">
              Gestiona la operación y consulta su actividad.
            </p>
          </div>
        </div>

        <nav className="tab-list" role="tablist" aria-label="Administración">
          {tabs.map((tab) => (
            <button
              aria-selected={activeTab === tab.id}
              className="tab-button"
              id={`tab-${tab.id}`}
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              role="tab"
              type="button"
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <section
          aria-labelledby={`tab-${activeTab}`}
          className="panel-card"
          role="tabpanel"
        >
          {activeTab === "tarifas" && <TariffsPage />}
          {activeTab === "cupos" && <CapacityPage />}
          {activeTab === "consultas" && <ConsultationsPage />}
        </section>
      </main>
    </div>
  );
}
