import { apiClient } from "./client.js";

export function getOperationalConfiguration() {
  return apiClient.get("/configuracion/operativa");
}

export function updateOperationalConfiguration(payload) {
  return apiClient.put("/configuracion/operativa", payload);
}
