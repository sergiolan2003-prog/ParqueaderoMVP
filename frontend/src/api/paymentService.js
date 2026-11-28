import { apiClient } from "./client.js";

export function listPendingPayments(accessToken = "") {
  const token = accessToken.trim();
  const headers = token
    ? { Authorization: `Bearer ${token}` }
    : undefined;

  return apiClient.get("/pagos/pendientes", { headers });
}

export function registerCashPayment(payload) {
  return apiClient.post("/pagos/efectivo", payload);
}
