import { apiClient } from "./client.js";

export function listCarriles(accessToken = "") {
  const token = accessToken.trim();
  const headers = token
    ? { Authorization: `Bearer ${token}` }
    : undefined;

  return apiClient.get("/carriles/", { headers });
}
