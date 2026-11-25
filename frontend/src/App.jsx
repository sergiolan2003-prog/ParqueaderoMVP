import { useEffect, useState } from "react";

import { apiClient } from "./api/client.js";

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
