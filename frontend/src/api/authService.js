import { apiClient } from "./client.js";

export function login(username, password) {
  const form = new URLSearchParams({ username, password });
  return apiClient.post("/auth/login", form);
}

export function getCurrentUser() {
  return apiClient.get("/auth/me");
}
