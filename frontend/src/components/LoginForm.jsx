import { useState } from "react";

import Alert from "./Alert.jsx";
import Field from "./Field.jsx";

export default function LoginForm({ onSubmit, error, loading }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    await onSubmit(username.trim(), password);
  }

  return (
    <main className="login-layout">
      <section className="login-intro">
        <p className="eyebrow">Parqueadero · Administración</p>
        <h1>Cada acceso, bajo control.</h1>
        <p>
          Administra tarifas, cupos y consultas desde un solo lugar.
        </p>
      </section>
      <section className="login-card" aria-labelledby="login-title">
        <p className="eyebrow">Acceso seguro</p>
        <h2 id="login-title">Iniciar sesión</h2>
        <p className="muted">
          Ingresa tus credenciales de operador o administrador.
        </p>
        <form className="stack-form" onSubmit={handleSubmit}>
          <Field label="Usuario" htmlFor="login-username">
            <input
              autoComplete="username"
              id="login-username"
              onChange={(event) => setUsername(event.target.value)}
              required
              value={username}
            />
          </Field>
          <Field label="Contraseña" htmlFor="login-password">
            <input
              autoComplete="current-password"
              id="login-password"
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </Field>
          {error && <Alert variant="error">{error}</Alert>}
          <button className="button button-primary" disabled={loading} type="submit">
            {loading ? "Validando..." : "Ingresar al panel"}
          </button>
        </form>
      </section>
    </main>
  );
}
