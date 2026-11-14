import { useEffect, useState } from "react";

export default function App() {
  const [health, setHealth] = useState({ status: "loading", message: "" });

  useEffect(() => {
    fetch("/health")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`La API respondió con HTTP ${response.status}`);
        }
        return response.json();
      })
      .then((data) => setHealth({ status: data.status, message: "" }))
      .catch((error) =>
        setHealth({ status: "error", message: error.message }),
      );
  }, []);

  return (
    <main>
      <h1>Sistema de Parqueadero</h1>
      <p role="status">
        Estado de la API:{" "}
        {health.status === "loading" ? "consultando..." : health.status}
      </p>
      {health.message && <p role="alert">{health.message}</p>}
    </main>
  );
}
