import { useState } from "react";

import Alert from "./Alert.jsx";
import Field from "./Field.jsx";
import { IconEye, IconEyeOff } from "./Icons.jsx";

export default function LoginForm({ onSubmit, error, loading }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    await onSubmit(username.trim(), password);
  }

  return (
    <div className="login-shell">
      <header className="topbar">
        <div className="topbar-left">
          <a className="brand" href="/" aria-label="Parqueadero, inicio">
            PARQUEA<span>+</span>
          </a>
        </div>
        <div className="topbar-right">
          <span className="topbar-subtitle">Sistema de Control y Tarifas</span>
        </div>
      </header>

      <main className="login-layout">
        <section className="login-intro">
          <div className="login-intro-body">
            <div className="login-accent-bar" aria-hidden="true" />
            <p className="eyebrow">Parqueadero · Administración</p>
            <h1>Cada acceso, bajo control.</h1>
            <p className="login-intro-lead">
              Administra tarifas, cupos y consultas desde un solo lugar con
              trazabilidad completa por carril.
            </p>
            <ul className="login-features">
              <li>
                <span className="login-feature-dot" aria-hidden="true" />
                <span>Lectura automática de placas (LPR) y validación manual</span>
              </li>
              <li>
                <span className="login-feature-dot" aria-hidden="true" />
                <span>Control de cupos por sede y apertura de barreras</span>
              </li>
              <li>
                <span className="login-feature-dot" aria-hidden="true" />
                <span>Historial versionado de tarifas, caja y auditoría</span>
              </li>
            </ul>
          </div>
          <div className="login-intro-footer">
            Acceso restringido a personal autorizado de operación y administración.
          </div>
        </section>

        <section className="login-stage" aria-labelledby="login-title">
          <div className="login-card">
            <p className="eyebrow eyebrow-accent">Acceso seguro</p>
            <h2 id="login-title">Iniciar sesión</h2>
            <p className="muted">
              Ingresa tus credenciales para acceder al sistema.
            </p>
            <form className="stack-form" onSubmit={handleSubmit}>
              <Field label="Usuario" htmlFor="login-username">
                <input
                  autoComplete="username"
                  id="login-username"
                  onChange={(event) => setUsername(event.target.value)}
                  placeholder="Ingresa tu usuario"
                  required
                  value={username}
                />
              </Field>
              <Field label="Contraseña" htmlFor="login-password">
                <div className="password-input-wrap">
                  <input
                    autoComplete="current-password"
                    id="login-password"
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="••••••••"
                    required
                    type={showPassword ? "text" : "password"}
                    value={password}
                  />
                  <button
                    aria-label={
                      showPassword ? "Ocultar contraseña" : "Mostrar contraseña"
                    }
                    className="password-toggle"
                    onClick={() => setShowPassword((prev) => !prev)}
                    type="button"
                  >
                    {showPassword ? <IconEyeOff /> : <IconEye />}
                  </button>
                </div>
              </Field>
              {error && <Alert variant="error">{error}</Alert>}
              <button
                className="button button-primary button-full"
                disabled={loading}
                type="submit"
              >
                {loading ? "Validando..." : "Ingresar al panel"}
              </button>
            </form>
            <p className="login-card-note">
              Sesión protegida mediante autenticación Bearer JWT.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}
