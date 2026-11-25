import { apiClient } from "./client.js";

export function listSites() {
  return apiClient.get("/sedes/");
}

export function getSiteCapacity(siteId) {
  return apiClient.get(`/sedes/${siteId}/cupos`);
}

export function updateSiteCapacity(siteId, payload) {
  return apiClient.put(`/sedes/${siteId}/cupos`, payload);
}
