import process from "node:process";

const baseUrl = process.env.FRONTEND_BASE_URL || "http://localhost:5173";
const apiBaseUrl = process.env.API_BASE_URL || "http://localhost:8000";
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

function resolveSchema(openApi, schema) {
  let current = schema;
  while (current?.$ref) {
    const name = current.$ref.split("/").pop();
    current = openApi.components?.schemas?.[name];
    if (!current) {
      throw new Error(`OpenAPI contiene una referencia de esquema no resuelta: ${name}.`);
    }
  }
  return current;
}

function assertOperationContract(openApi, path, method, contract) {
  const operation = openApi.paths?.[path]?.[method];
  if (!operation) {
    throw new Error(`OpenAPI no registra ${method.toUpperCase()} ${path}.`);
  }

  if (contract.requestContentType) {
    const requestSchema = operation.requestBody?.content?.[contract.requestContentType]?.schema;
    if (!requestSchema) {
      throw new Error(
        `${method.toUpperCase()} ${path} no declara cuerpo ${contract.requestContentType}.`,
      );
    }

    const resolvedRequest = resolveSchema(openApi, requestSchema);
    const requestFields = Object.keys(resolvedRequest.properties ?? {});
    for (const field of contract.requestFields) {
      if (!requestFields.includes(field)) {
        throw new Error(`${method.toUpperCase()} ${path} no declara el campo ${field}.`);
      }
    }

    for (const field of contract.requiredFields ?? []) {
      if (!resolvedRequest.required?.includes(field)) {
        throw new Error(`${method.toUpperCase()} ${path} no requiere el campo ${field}.`);
      }
    }
  }

  for (const [status, responseFields] of Object.entries(contract.responses)) {
    const responseSchema =
      operation.responses?.[status]?.content?.["application/json"]?.schema;
    if (!responseSchema) {
      throw new Error(
        `${method.toUpperCase()} ${path} no documenta respuesta JSON HTTP ${status}.`,
      );
    }

    const resolvedResponse = resolveSchema(openApi, responseSchema);
    const fields = Object.keys(resolvedResponse.properties ?? {});
    for (const field of responseFields) {
      if (!fields.includes(field)) {
        throw new Error(
          `${method.toUpperCase()} ${path} no devuelve el campo ${field} en HTTP ${status}.`,
        );
      }
    }
  }

  console.log(`PASS OpenAPI ${method.toUpperCase()} ${path}`);
}

async function expectStatus(response, expectedStatus, description) {
  if (response.status !== expectedStatus) {
    throw new Error(
      `${description}: se esperaba HTTP ${expectedStatus} y llegó HTTP ${response.status}.`,
    );
  }
  console.log(`PASS ${description}: HTTP ${expectedStatus}`);
}

const openApiResponse = await fetch(new URL("/openapi.json", apiBaseUrl), {
  signal: AbortSignal.timeout(timeoutMs),
});
await expectStatus(openApiResponse, 200, "OpenAPI real de FastAPI");
const openApi = await openApiResponse.json();
assertOperationContract(openApi, "/auth/login", "post", {
  requestContentType: "application/x-www-form-urlencoded",
  requestFields: ["username", "password"],
  requiredFields: ["username", "password"],
  responses: { 200: ["access_token", "token_type"] },
});
assertOperationContract(openApi, "/auth/me", "get", {
  responses: { 200: ["username", "rol", "activo"] },
});
assertOperationContract(openApi, "/accesos/entrada", "post", {
  requestContentType: "application/json",
  requestFields: ["evento_id", "placa", "carril_id", "ocurrido_en"],
  requiredFields: ["evento_id", "placa", "carril_id", "ocurrido_en"],
  responses: { 201: ["evento_id", "placa", "cobro_creado", "pase_vigente"] },
});
assertOperationContract(openApi, "/accesos/salida", "post", {
  requestContentType: "application/json",
  requestFields: ["placa", "carril_id"],
  requiredFields: ["placa", "carril_id"],
  responses: { 200: ["placa", "barrera_abre", "motivo", "registrado_en"] },
});
assertOperationContract(openApi, "/pagos/efectivo", "post", {
  requestContentType: "application/json",
  requestFields: ["cobro_id", "referencia_pago"],
  requiredFields: ["cobro_id", "referencia_pago"],
  responses: {
    200: ["pago_id", "cobro_id", "valor_pagado", "estado_cobro"],
    201: ["pago_id", "cobro_id", "valor_pagado", "estado_cobro"],
  },
});
assertOperationContract(openApi, "/tarifas/", "post", {
  requestContentType: "application/json",
  requestFields: [
    "sede_id",
    "tipo_vehiculo",
    "franja",
    "valor",
    "vigente_desde",
  ],
  requiredFields: [
    "sede_id",
    "tipo_vehiculo",
    "franja",
    "valor",
    "vigente_desde",
  ],
  responses: { 201: ["id", "sede_id", "tipo_vehiculo", "franja", "valor"] },
});

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

const tariffWithoutTrailingSlash = await request("/tarifas");
await expectStatus(
  tariffWithoutTrailingSlash,
  405,
  "proxy de ruta tarifaria sin barra final y respuesta del backend",
);
if (tariffWithoutTrailingSlash.url !== new URL("/tarifas/", baseUrl).href) {
  throw new Error("La redirección de tarifas salió del origen del frontend.");
}

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
    placa: "INVALID",
    carril_id: "00000000-0000-0000-0000-000000000000",
  }),
});
await expectStatus(exitResponse, 422, "proxy de salida y validación real de placa");
