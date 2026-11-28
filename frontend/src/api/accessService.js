import { apiClient } from "./client.js";

export function registerEntry(payload) {
  return apiClient.post("/accesos/entrada", payload);
}

export function registerEntryByImage(formData, options) {
  return apiClient.post("/accesos/entrada/imagen", formData, options);
}

export function registerExit(payload) {
  return apiClient.post("/accesos/salida", payload);
}
