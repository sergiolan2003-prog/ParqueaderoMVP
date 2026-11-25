import { apiClient } from "./client.js";

export function registerCashPayment(payload) {
  return apiClient.post("/pagos/efectivo", payload);
}
