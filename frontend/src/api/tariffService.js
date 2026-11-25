import { apiClient } from "./client.js";

export function listTariffs(filters = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  }
  const query = params.toString();
  return apiClient.get(query ? `/tarifas/?${query}` : "/tarifas/");
}

export function createOrUpdateTariff(payload) {
  return apiClient.post("/tarifas/", payload);
}
