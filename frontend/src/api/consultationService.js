import { apiClient } from "./client.js";

function withQuery(path, filters) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  }
  const query = params.toString();
  return apiClient.get(query ? `${path}?${query}` : path);
}

export function listAccessEvents(filters) {
  return withQuery("/consultas/eventos", {
    ...filters,
    placa: filters.placa?.trim().toUpperCase(),
  });
}

export function listCharges(filters) {
  return withQuery("/consultas/cobros", {
    ...filters,
    placa: filters.placa?.trim().toUpperCase(),
  });
}
