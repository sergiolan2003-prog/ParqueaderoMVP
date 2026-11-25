import { apiClient } from "./client.js";

export function createOrUpdateTariff(payload) {
  return apiClient.post("/tarifas/", payload);
}
