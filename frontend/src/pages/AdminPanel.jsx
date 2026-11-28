import { useState } from "react";

import { IconLogOut } from "../components/Icons.jsx";
import CapacityPage from "./CapacityPage.jsx";
import ConsultationsPage from "./ConsultationsPage.jsx";
import ConfigurationPage from "./ConfigurationPage.jsx";
import TariffsPage from "./TariffsPage.jsx";

const tabs = [
  { id: "tarifas", label: "Tarifas" },
  { id: "cupos", label: "Cupos" },
  { id: "consultas", label: "Consultas" },
  { id: "configuracion", label: "Configuración" },
];

export default function AdminPanel({ health, onLogout, user }) {
  const [activeTab, setActiveTab] = useState("tarifas");

  return (
    <div className="admin-shell">
      <header className="topbar">
        <div className="topbar-left">
          <a className="brand" href="/" aria-label="Parqueadero, inicio">
            PARQUEA<span>+</span>
          </a>
          <nav className="topbar-nav" role="tablist" aria-label="Administración">
            {tabs.map((tab) => (
              <button
                aria-selected={activeTab === tab.id}
                className="topbar-tab"
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
        </div>

        <div className="user-menu">
          <span className="role-label">Administración</span>
          <span className="user-name">{user.username}</span>
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

      <main className="admin-main">
        <div className="page-heading">
          <div>
            <p className="eyebrow eyebrow-accent">Panel de control</p>
            <h1>Administración del parqueadero</h1>
            <p className="muted">
              Gestiona la operación, tarifas, capacidad y auditoría del sistema.
            </p>
          </div>
          <span
            className={`status-badge ${
              health.status === "ok" ? "badge-success" : "badge-warning"
            }`}
          >
            <span className="status-badge-dot" aria-hidden="true" />
            API {health.status === "loading" ? "consultando" : health.status}
          </span>
        </div>

        <section
          aria-labelledby={`tab-${activeTab}`}
          className="admin-content"
          role="tabpanel"
        >
          {activeTab === "tarifas" && <TariffsPage />}
          {activeTab === "cupos" && <CapacityPage />}
          {activeTab === "consultas" && <ConsultationsPage />}
          {activeTab === "configuracion" && <ConfigurationPage />}
        </section>
      </main>
    </div>
  );
}
