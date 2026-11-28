import Alert from "../components/Alert.jsx";

export default function AccessDenied({ onLogout, username }) {
  return (
    <main className="access-denied">
      <section className="surface-card">
        <p className="eyebrow eyebrow-accent">Acceso restringido</p>
        <h1>Acceso denegado</h1>
        <Alert variant="error">
          La cuenta {username} tiene rol OPERADOR. Este panel es exclusivo para
          administradores.
        </Alert>
        <button className="button button-primary" onClick={onLogout} type="button">
          Cerrar sesión
        </button>
      </section>
    </main>
  );
}
