import process from "node:process";

const baseUrl = process.env.FRONTEND_BASE_URL || "http://localhost:5173";
const username = process.env.INTEGRATION_OPERATOR_USERNAME;
const password = process.env.INTEGRATION_OPERATOR_PASSWORD;
const timeoutMs = 10000;

if (!username || !password) {
  throw new Error(
    "Define INTEGRATION_OPERATOR_USERNAME e INTEGRATION_OPERATOR_PASSWORD para la prueba real.",
  );
}

async function request(path, options = {}) {
  return fetch(new URL(path, baseUrl), {
    ...options,
    signal: AbortSignal.timeout(timeoutMs),
  });
}

async function expectStatus(response, expectedStatus, description) {
  if (response.status !== expectedStatus) {
    throw new Error(
      `${description}: se esperaba HTTP ${expectedStatus} y llegó HTTP ${response.status}.`,
    );
  }
  console.log(`PASS ${description}: HTTP ${expectedStatus}`);
}

const healthResponse = await request("/health");
await expectStatus(healthResponse, 200, "proxy de salud frontend -> FastAPI");
const health = await healthResponse.json();
if (health.status !== "ok") {
  throw new Error("FastAPI devolvió un estado de salud inesperado.");
}

const unauthenticatedResponse = await request("/auth/me");
await expectStatus(unauthenticatedResponse, 401, "rechazo de /auth/me sin JWT");

const loginResponse = await request("/auth/login", {
  method: "POST",
  headers: { "Content-Type": "application/x-www-form-urlencoded" },
  body: new URLSearchParams({ username, password }),
});
await expectStatus(loginResponse, 200, "login real a través del proxy frontend");
const tokenResponse = await loginResponse.json();
if (!tokenResponse.access_token || tokenResponse.token_type !== "bearer") {
  throw new Error("La respuesta real de login no contiene el contrato JWT esperado.");
}

const authorization = { Authorization: `Bearer ${tokenResponse.access_token}` };
const userResponse = await request("/auth/me", { headers: authorization });
await expectStatus(userResponse, 200, "consulta real del usuario autenticado");
const user = await userResponse.json();
if (user.username !== username || user.rol !== "OPERADOR" || !user.activo) {
  throw new Error("El usuario autenticado no coincide con el contrato esperado.");
}

const forbiddenResponse = await request("/auth/admin-check", {
  headers: authorization,
});
await expectStatus(forbiddenResponse, 403, "rechazo por rol en ruta administrativa");

const entryResponse = await request("/accesos/entrada", {
  method: "POST",
  headers: {
    ...authorization,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({}),
});
await expectStatus(entryResponse, 422, "proxy de registro de entrada y validación real");

const paymentResponse = await request("/pagos/efectivo", {
  method: "POST",
  headers: {
    ...authorization,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({}),
});
await expectStatus(paymentResponse, 422, "proxy de pago y validación real");

const exitResponse = await request("/accesos/salida", {
  method: "POST",
  headers: {
    ...authorization,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    placa: "ZZZ000",
    carril_id: "00000000-0000-0000-0000-000000000000",
  }),
});
await expectStatus(exitResponse, 404, "ruta de salida consulta un carril inexistente");
const exitError = await exitResponse.json();
if (exitError.detail !== "El carril especificado no existe.") {
  throw new Error("La API devolvió un error inesperado para la salida de prueba.");
}
