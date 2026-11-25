import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import App from "./App.jsx";
import AuthProvider from "./auth/AuthProvider.jsx";
import { clearAccessToken, setAccessToken } from "./auth/tokenStore.js";

const site = {
  id: "site-1",
  nombre: "Sede Centro",
  cupos_carro: 20,
  cupos_moto: 10,
};

const existingTariff = {
  id: "tariff-1",
  sede_id: site.id,
  tipo_vehiculo: "CARRO",
  franja: "DIURNA",
  valor: "12000.00",
  vigente_desde: "2026-03-10",
  vigente_hasta: null,
};

const accessEvent = {
  id: "event-1",
  placa: "ABC123",
  carril_id: "lane-1",
  ocurrido_en: "2026-03-10T14:00:00Z",
  confianza_lpr: 0.99,
  lectura_manual: false,
  foto_url: null,
};

const operationalConfiguration = {
  daytime_start: "06:00:00",
  daytime_end: "18:00:00",
  nighttime_start: "18:00:00",
  nighttime_end: "06:00:00",
  lpr_confidence_threshold: 0.8,
};

function jsonResponse(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  };
}

function installApiMock({ role = "ADMINISTRADOR", rejectTariff = false } = {}) {
  const tariffs = [existingTariff];
  const siteState = { ...site };
  const configurationState = { ...operationalConfiguration };
  const calls = [];
  const fetchMock = vi.fn(async (input, options = {}) => {
    const url = new URL(input, window.location.origin);
    const method = options.method ?? "GET";
    calls.push({ method, url, body: options.body });

    if (url.pathname === "/health") {
      return jsonResponse({ status: "ok" });
    }
    if (url.pathname === "/auth/login") {
      return jsonResponse({ access_token: "test-token", token_type: "bearer" });
    }
    if (url.pathname === "/auth/me") {
      return jsonResponse({ username: "test-user", rol: role, activo: true });
    }
    if (url.pathname === "/tarifas/" && method === "GET") {
      return jsonResponse(tariffs);
    }
    if (url.pathname === "/tarifas/" && method === "POST") {
      const payload = JSON.parse(options.body);
      if (rejectTariff) {
        return jsonResponse(
          {
            detail:
              "RN-02: La tarifa nocturna no puede ser mayor o igual a la diurna.",
          },
          400,
        );
      }
      const created = {
        ...payload,
        id: "tariff-new",
        vigente_hasta: payload.vigente_hasta ?? null,
      };
      tariffs.unshift(created);
      return jsonResponse(created, 201);
    }
    if (url.pathname === "/sedes/") {
      return jsonResponse([siteState]);
    }
    if (url.pathname === `/sedes/${site.id}/cupos` && method === "GET") {
      return jsonResponse(siteState);
    }
    if (url.pathname === `/sedes/${site.id}/cupos` && method === "PUT") {
      Object.assign(siteState, JSON.parse(options.body));
      return jsonResponse(siteState);
    }
    if (url.pathname === "/consultas/eventos") {
      return jsonResponse({
        items: [accessEvent],
        total: 1,
        page: Number(url.searchParams.get("page") ?? 1),
        page_size: 10,
        total_pages: 1,
      });
    }
    if (url.pathname === "/consultas/cobros") {
      return jsonResponse({
        items: [],
        total: 0,
        page: Number(url.searchParams.get("page") ?? 1),
        page_size: 10,
        total_pages: 0,
      });
    }
    if (url.pathname === "/configuracion/operativa" && method === "GET") {
      return jsonResponse(configurationState);
    }
    if (url.pathname === "/configuracion/operativa" && method === "PUT") {
      Object.assign(configurationState, JSON.parse(options.body));
      return jsonResponse(configurationState);
    }
    return jsonResponse({ detail: "Not found" }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock, tariffs };
}

function renderApp() {
  return render(
    <AuthProvider>
      <App />
    </AuthProvider>,
  );
}

async function signIn(user, role = "ADMINISTRADOR") {
  installApiMock({ role });
  renderApp();
  await user.type(screen.getByLabelText("Usuario"), "test-user");
  await user.type(screen.getByLabelText("Contraseña"), "test-password");
  await user.click(screen.getByRole("button", { name: "Ingresar al panel" }));
}

afterEach(() => {
  cleanup();
  clearAccessToken();
  vi.unstubAllGlobals();
});

it("requires login before showing the administration panel", async () => {
  installApiMock();
  renderApp();

  expect(
    await screen.findByRole("heading", { name: "Iniciar sesión" }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "Tarifas" })).not.toBeInTheDocument();
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Estado de la API: ok",
  );
});

it("denies the administration panel to an operator", async () => {
  const user = userEvent.setup();
  await signIn(user, "OPERADOR");

  expect(
    await screen.findByRole("heading", { name: "Panel del carril" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Acceso al panel administrativo denegado/i),
  ).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "Tarifas" })).not.toBeInTheDocument();
  expect(
    screen.queryByLabelText("Token operador (Bearer)"),
  ).not.toBeInTheDocument();
});

it("restores a valid administrator session from session storage", async () => {
  const { fetchMock } = installApiMock();
  setAccessToken("restored-token");
  renderApp();

  expect(await screen.findByRole("tab", { name: "Tarifas" })).toBeInTheDocument();
  const profileRequest = fetchMock.mock.calls.find(
    ([url]) => new URL(url, window.location.origin).pathname === "/auth/me",
  );
  expect(profileRequest[1].headers.get("Authorization")).toBe(
    "Bearer restored-token",
  );
});

it("creates and lists a tariff through the administrator panel", async () => {
  const user = userEvent.setup();
  const { calls } = installApiMock();
  renderApp();
  await user.type(screen.getByLabelText("Usuario"), "test-user");
  await user.type(screen.getByLabelText("Contraseña"), "test-password");
  await user.click(screen.getByRole("button", { name: "Ingresar al panel" }));

  expect(await screen.findByText("Historial de tarifas")).toBeInTheDocument();
  await user.clear(screen.getByLabelText("Valor (COP)"));
  await user.type(screen.getByLabelText("Valor (COP)"), "14000");
  await user.click(screen.getByRole("button", { name: "Crear tarifa" }));

  expect(
    await screen.findByText("Tarifa creada correctamente."),
  ).toBeInTheDocument();
  await waitFor(() => {
    expect(
      screen.getByText((content) => content.includes("14.000")),
    ).toBeInTheDocument();
  });
  expect(
    calls.some(
      (call) =>
        call.method === "GET" && call.url.pathname === "/tarifas/",
    ),
  ).toBe(true);
  expect(
    calls.some(
      (call) =>
        call.method === "POST" && call.url.pathname === "/tarifas/",
    ),
  ).toBe(true);
  expect(sessionStorage.getItem("access_token")).toBe("test-token");
});

it("shows the backend RN-02 validation beside the tariff form", async () => {
  const user = userEvent.setup();
  installApiMock({ rejectTariff: true });
  renderApp();
  await user.type(screen.getByLabelText("Usuario"), "test-user");
  await user.type(screen.getByLabelText("Contraseña"), "test-password");
  await user.click(screen.getByRole("button", { name: "Ingresar al panel" }));

  expect(await screen.findByText("Historial de tarifas")).toBeInTheDocument();
  await user.selectOptions(
    screen.getAllByLabelText("Franja")[0],
    "NOCTURNA",
  );
  await user.clear(screen.getByLabelText("Valor (COP)"));
  await user.type(screen.getByLabelText("Valor (COP)"), "15000");
  await user.click(screen.getByRole("button", { name: "Crear tarifa" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "RN-02: La tarifa nocturna no puede ser mayor o igual a la diurna.",
  );
});

it("edits a tariff by submitting a new version", async () => {
  const user = userEvent.setup();
  const { calls } = installApiMock();
  renderApp();
  await user.type(screen.getByLabelText("Usuario"), "test-user");
  await user.type(screen.getByLabelText("Contraseña"), "test-password");
  await user.click(screen.getByRole("button", { name: "Ingresar al panel" }));

  await user.click(
    await screen.findByRole("button", { name: "Nueva versión" }),
  );
  expect(
    screen.getByRole("heading", { name: "Crear nueva versión" }),
  ).toBeInTheDocument();
  await user.clear(screen.getByLabelText("Valor (COP)"));
  await user.type(screen.getByLabelText("Valor (COP)"), "13500");
  await user.click(screen.getByRole("button", { name: "Guardar versión" }));

  expect(
    await screen.findByText(
      "Nueva versión creada; el historial anterior se conservó.",
    ),
  ).toBeInTheDocument();
  const versions = calls.filter(
    (call) =>
      call.method === "POST" && call.url.pathname === "/tarifas/",
  );
  expect(versions).toHaveLength(1);
  expect(JSON.parse(versions[0].body)).toMatchObject({
    sede_id: site.id,
    tipo_vehiculo: "CARRO",
    franja: "DIURNA",
    valor: "13500",
  });
  expect(
    JSON.parse(versions[0].body).vigente_desde > existingTariff.vigente_desde,
  ).toBe(true);
});

it("saves site capacities from the Cupos tab", async () => {
  const user = userEvent.setup();
  const { calls } = installApiMock();
  renderApp();
  await user.type(screen.getByLabelText("Usuario"), "test-user");
  await user.type(screen.getByLabelText("Contraseña"), "test-password");
  await user.click(screen.getByRole("button", { name: "Ingresar al panel" }));
  await user.click(await screen.findByRole("tab", { name: "Cupos" }));

  await user.clear(await screen.findByLabelText("Cupos para carros"));
  await user.type(screen.getByLabelText("Cupos para carros"), "30");
  await user.clear(screen.getByLabelText("Cupos para motos"));
  await user.type(screen.getByLabelText("Cupos para motos"), "12");
  await user.click(screen.getByRole("button", { name: "Guardar cupos" }));

  expect(
    await screen.findByText("Cupos actualizados para Sede Centro."),
  ).toBeInTheDocument();
  const updateCall = calls.find(
    (call) =>
      call.method === "PUT" &&
      call.url.pathname === `/sedes/${site.id}/cupos`,
  );
  expect(JSON.parse(updateCall.body)).toEqual({
    cupos_carro: 30,
    cupos_moto: 12,
  });
});

it("normalizes the consultation plate and submits event filters", async () => {
  const user = userEvent.setup();
  const { calls } = installApiMock();
  renderApp();
  await user.type(screen.getByLabelText("Usuario"), "test-user");
  await user.type(screen.getByLabelText("Contraseña"), "test-password");
  await user.click(screen.getByRole("button", { name: "Ingresar al panel" }));
  await user.click(await screen.findByRole("tab", { name: "Consultas" }));
  await user.type(screen.getByLabelText("Placa"), "abc123");
  await user.type(screen.getByLabelText("Desde"), "2026-03-10");
  await user.type(screen.getByLabelText("Hasta"), "2026-03-10");
  await user.click(screen.getByRole("button", { name: "Buscar" }));

  expect(await screen.findByText("ABC123")).toBeInTheDocument();
  const queryCall = calls.find(
    (call) =>
      call.method === "GET" &&
      call.url.pathname === "/consultas/eventos",
  );
  expect(queryCall.url.searchParams.get("placa")).toBe("ABC123");
  expect(queryCall.url.searchParams.get("desde")).toBe("2026-03-10");
  expect(queryCall.url.searchParams.get("hasta")).toBe("2026-03-10");
});

it("sends the selected charge state to the paginated consultation", async () => {
  const user = userEvent.setup();
  const { calls } = installApiMock();
  renderApp();
  await user.type(screen.getByLabelText("Usuario"), "test-user");
  await user.type(screen.getByLabelText("Contraseña"), "test-password");
  await user.click(screen.getByRole("button", { name: "Ingresar al panel" }));
  await user.click(await screen.findByRole("tab", { name: "Consultas" }));
  await user.click(screen.getByRole("button", { name: "Cobros" }));
  await user.selectOptions(screen.getByLabelText("Estado"), "PENDIENTE");
  await user.click(screen.getByRole("button", { name: "Buscar" }));

  await waitFor(() => {
    expect(
      calls.some(
        (call) =>
          call.method === "GET" &&
          call.url.pathname === "/consultas/cobros" &&
          call.url.searchParams.get("estado") === "PENDIENTE",
      ),
    ).toBe(true);
  });
  expect(screen.getByText(/0 resultados/)).toBeInTheDocument();
});

it("updates the global schedule and LPR threshold from Configuration", async () => {
  const user = userEvent.setup();
  const { calls } = installApiMock();
  renderApp();
  await user.type(screen.getByLabelText("Usuario"), "test-user");
  await user.type(screen.getByLabelText("Contraseña"), "test-password");
  await user.click(screen.getByRole("button", { name: "Ingresar al panel" }));
  await user.click(
    await screen.findByRole("tab", { name: "Configuración" }),
  );

  expect(
    await screen.findByRole("heading", { name: "Configuración operativa" }),
  ).toBeInTheDocument();
  await user.clear(screen.getByLabelText("Inicio de franja diurna"));
  await user.type(screen.getByLabelText("Inicio de franja diurna"), "07:00");
  await user.clear(screen.getByLabelText("Fin de franja diurna"));
  await user.type(screen.getByLabelText("Fin de franja diurna"), "19:00");
  await user.clear(screen.getByLabelText("Inicio de franja nocturna"));
  await user.type(screen.getByLabelText("Inicio de franja nocturna"), "19:00");
  await user.clear(screen.getByLabelText("Fin de franja nocturna"));
  await user.type(screen.getByLabelText("Fin de franja nocturna"), "07:00");
  const confidenceInput = screen.getByRole("spinbutton", {
    name: /Umbral de confianza LPR/,
  });
  await user.clear(confidenceInput);
  await user.type(confidenceInput, "0.85");
  await user.click(
    screen.getByRole("button", { name: "Guardar configuración" }),
  );

  expect(
    await screen.findByText(
      "Configuración operativa actualizada correctamente.",
    ),
  ).toBeInTheDocument();
  const updateCall = calls.find(
    (call) =>
      call.method === "PUT" &&
      call.url.pathname === "/configuracion/operativa",
  );
  expect(JSON.parse(updateCall.body)).toEqual({
    daytime_start: "07:00",
    daytime_end: "19:00",
    nighttime_start: "19:00",
    nighttime_end: "07:00",
    lpr_confidence_threshold: 0.85,
  });
});
