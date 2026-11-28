import { apiClient } from "./client.js";

export function listCarriles(accessToken) {
  return apiClient.get("/accesos/carriles", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}
