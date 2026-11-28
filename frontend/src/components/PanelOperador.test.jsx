import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { PanelOperador } from "./PanelOperador.jsx";

const carriles = [
  {
    id: "carril-entrada",
    sede_id: "sede-1",
    sede_nombre: "Sede Principal",
    sentido: "ENTRADA",
  },
  {
    id: "carril-salida",
    sede_id: "sede-1",
    sede_nombre: "Sede Principal",
    sentido: "SALIDA",
  },
];

function jsonResponse(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("muestra barrera abierta cuando un carro tiene cobro pagado", () => {
  render(
    <PanelOperador
      estadoInicial={{
        estado: "BARRERA_ABIERTA",
        placa: "ABC123",
        confianza: 0.987,
        tipoVehiculo: "Automóvil (CARRO)",
        valorPagar: 8500,
        cobroId: null,
        barreraAbierta: true,
        motivoBarrera: "Pago confirmado. Salida autorizada para ABC123.",
      }}
    />,
  );

  expect(screen.getByTestId("placa-leida")).toHaveTextContent("ABC123");
  expect(screen.getByTestId("estado-badge")).toHaveTextContent("Barrera abierta");
  expect(screen.getByText(/✓ ABIERTA/i)).toBeInTheDocument();
  expect(screen.getByText(/Salida autorizada para ABC123/i)).toBeInTheDocument();
});

it("muestra barrera cerrada con motivo cuando hay cobro pendiente", () => {
  render(
    <PanelOperador
      estadoInicial={{
        estado: "COBRO_PENDIENTE",
        placa: "XYZ789",
        confianza: 0.95,
        tipoVehiculo: "Automóvil (CARRO)",
        valorPagar: 5000,
        cobroId: "cobro-1",
        barreraAbierta: false,
        motivoBarrera: "F-05: Salida rechazada. El vehículo posee una deuda pendiente.",
      }}
    />,
  );

  expect(screen.getByTestId("estado-badge")).toHaveTextContent("Cobro pendiente");
  expect(screen.getByText(/✕ BARRERA CERRADA/i)).toBeInTheDocument();
  expect(screen.getByText(/deuda pendiente/i)).toBeInTheDocument();
});

it("muestra el formulario de lectura manual ante baja confianza", () => {
  render(
    <PanelOperador
      estadoInicial={{
        estado: "BAJA_CONFIANZA",
        placa: "ABC12B",
        confianza: 0.724,
        tipoVehiculo: "Automóvil (CARRO)",
        valorPagar: 0,
        cobroId: null,
        barreraAbierta: false,
        motivoBarrera: "Validación manual pendiente.",
        requiereManual: true,
      }}
    />,
  );

  expect(screen.getByLabelText(/Validación manual/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Confirmar placa manual/i })).toBeInTheDocument();
});

it("muestra error de la API sin dejar la pantalla en blanco", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url) => {
      if (url === "/carriles/") return jsonResponse(carriles);
      if (url === "/pagos/pendientes") return jsonResponse([]);
      return jsonResponse({ detail: "Error interno del servidor" }, 500);
    }),
  );

  render(<PanelOperador accessToken="test-token" />);
  expect(await screen.findByTestId("carriles-configurados")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /Registrar ingreso/i }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "El servidor encontró un error",
  );
  expect(screen.getByText(/Panel del carril/i)).toBeInTheDocument();
});

it("usa automáticamente el carril del sentido correspondiente", async () => {
  const fetchMock = vi.fn(async (url) => {
    if (url === "/carriles/") {
      return jsonResponse(carriles);
    }
    if (url === "/pagos/pendientes") {
      return jsonResponse([]);
    }
    if (url === "/accesos/entrada/simulada") {
      return jsonResponse({
        cobro_creado: false,
        valor: 0,
        placa: "ABC123",
        cobro_id: null,
        franja: "DIURNA",
        pase_vigente: false,
      });
    }
    if (url === "/accesos/salida") {
      return jsonResponse({
        barrera_abre: true,
        placa: "ABC123",
        motivo: "Salida autorizada.",
      });
    }
    return jsonResponse({ detail: "No se esperaba esta solicitud." }, 500);
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<PanelOperador accessToken="test-token" />);
  expect(await screen.findByTestId("carriles-configurados")).toHaveTextContent(
    "Sede Principal",
  );
  fireEvent.change(screen.getByPlaceholderText("ABC123"), {
    target: { value: "ABC123" },
  });

  fireEvent.click(screen.getByRole("button", { name: /Registrar ingreso/i }));
  await screen.findByText(/Ingreso registrado/i);

  const entryCall = fetchMock.mock.calls.find(
    ([url]) => url === "/accesos/entrada/simulada",
  );
  expect(JSON.parse(entryCall[1].body).carril_id).toBe("carril-entrada");
  const catalogCall = fetchMock.mock.calls.find(([url]) => url === "/carriles/");
  expect(catalogCall[1].headers.get("Authorization")).toBe("Bearer test-token");

  fireEvent.click(screen.getByRole("button", { name: /Validar salida/i }));
  await screen.findByText("Salida autorizada.");

  const exitCall = fetchMock.mock.calls.find(
    ([url]) => url === "/accesos/salida",
  );
  expect(JSON.parse(exitCall[1].body).carril_id).toBe("carril-salida");
});

it("bloquea la operación si la sede no tiene carril de salida", async () => {
  const fetchMock = vi.fn(async (url) =>
    url === "/carriles/" ? jsonResponse([carriles[0]]) : jsonResponse([]),
  );
  vi.stubGlobal("fetch", fetchMock);

  render(<PanelOperador accessToken="test-token" />);

  expect(
    await screen.findByText(/No hay un carril de salida en la sede seleccionada/i),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /Registrar ingreso/i }),
  ).toBeDisabled();
  expect(
    screen.getByRole("button", { name: /Validar salida/i }),
  ).toBeDisabled();
});

it("permite elegir entre varios carriles y envía el seleccionado", async () => {
  const multipleLanes = [
    ...carriles,
    { ...carriles[0], id: "carril-entrada-2" },
    { ...carriles[1], id: "carril-salida-2" },
  ];
  const fetchMock = vi.fn(async (url) => {
    if (url === "/carriles/") return jsonResponse(multipleLanes);
    if (url === "/pagos/pendientes") return jsonResponse([]);
    if (url === "/accesos/entrada/simulada") {
      return jsonResponse({
        cobro_creado: false,
        valor: 0,
        placa: "ABC123",
        cobro_id: null,
        franja: "DIURNA",
        pase_vigente: false,
      });
    }
    if (url === "/accesos/salida") {
      return jsonResponse({
        barrera_abre: true,
        placa: "ABC123",
        motivo: "Salida autorizada.",
      });
    }
    return jsonResponse({ detail: "Solicitud inesperada" }, 500);
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<PanelOperador accessToken="test-token" />);
  await screen.findByTestId("carriles-configurados");
  fireEvent.change(screen.getByRole("combobox", { name: "Carril de entrada" }), {
    target: { value: "carril-entrada-2" },
  });
  fireEvent.change(screen.getByRole("combobox", { name: "Carril de salida" }), {
    target: { value: "carril-salida-2" },
  });
  fireEvent.click(screen.getByRole("button", { name: /Registrar ingreso/i }));

  const entryCall = fetchMock.mock.calls.find(
    ([url]) => url === "/accesos/entrada/simulada",
  );
  expect(JSON.parse(entryCall[1].body).carril_id).toBe("carril-entrada-2");
  await screen.findByText(/Ingreso registrado/i);
  fireEvent.click(screen.getByRole("button", { name: /Validar salida/i }));
  await screen.findByText("Salida autorizada.");
  const exitCall = fetchMock.mock.calls.find(
    ([url]) => url === "/accesos/salida",
  );
  expect(JSON.parse(exitCall[1].body).carril_id).toBe("carril-salida-2");
});

it("usa el rechazo de confianza del servidor para ofrecer lectura manual", async () => {
  const fetchMock = vi.fn(async (url) => {
    if (url === "/carriles/") return jsonResponse(carriles);
    if (url === "/pagos/pendientes") return jsonResponse([]);
    return jsonResponse(
      {
        detail:
          "CONFIANZA_LPR_INSUFICIENTE: La confianza no alcanza el umbral requerido.",
      },
      422,
    );
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<PanelOperador accessToken="test-token" />);
  await screen.findByTestId("carriles-configurados");
  fireEvent.change(screen.getByLabelText(/Confianza LPR/i), {
    target: { value: "0.9" },
  });
  fireEvent.click(screen.getByRole("button", { name: /Registrar ingreso/i }));

  expect(
    await screen.findByRole("button", { name: /Confirmar placa manual/i }),
  ).toBeInTheDocument();
  expect(screen.getByTestId("confianza-ocr")).toHaveTextContent("90.0 %");
});

it("muestra para pago un cobro existente aunque no se haya creado en este ingreso", async () => {
  const pendingCharge = {
    cobro_id: "cobro-preexistente",
    placa: "ABC123",
    sede_id: "sede-1",
    sede_nombre: "Sede Principal",
    dia_operativo: "2026-03-10",
    valor: "12000.00",
  };
  let pendingRequestCount = 0;
  const fetchMock = vi.fn(async (url) => {
    if (url === "/carriles/") return jsonResponse(carriles);
    if (url === "/pagos/pendientes") {
      pendingRequestCount += 1;
      return jsonResponse(pendingRequestCount === 1 ? [] : [pendingCharge]);
    }
    if (url === "/accesos/entrada/simulada") {
      return jsonResponse({
        cobro_creado: false,
        valor: "12000.00",
        placa: "ABC123",
        cobro_id: "cobro-preexistente",
        franja: "DIURNA",
        pase_vigente: false,
      });
    }
    return jsonResponse({ detail: "Solicitud inesperada" }, 500);
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<PanelOperador accessToken="test-token" />);
  await screen.findByTestId("carriles-configurados");
  fireEvent.click(screen.getByRole("button", { name: /Registrar ingreso/i }));

  expect(await screen.findByTestId("estado-badge")).toHaveTextContent(
    "Cobro pendiente",
  );
  expect(
    screen.getByRole("button", { name: /Confirmar pago en efectivo/i }),
  ).toBeEnabled();
});

it("recupera un cobro pendiente y permite pagarlo", async () => {
  const pendingCharge = {
    cobro_id: "cobro-recoverable",
    placa: "ABC123",
    sede_id: "sede-1",
    sede_nombre: "Sede Principal",
    dia_operativo: "2026-03-10",
    valor: "12000.00",
  };
  const fetchMock = vi.fn(async (url) => {
    if (url === "/carriles/") return jsonResponse(carriles);
    if (url === "/pagos/pendientes") return jsonResponse([pendingCharge]);
    if (url === "/pagos/efectivo") {
      return jsonResponse({
        valor_pagado: "12000.00",
        referencia_pago: "EF-1",
      });
    }
    return jsonResponse({ detail: "Solicitud inesperada" }, 500);
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<PanelOperador accessToken="test-token" />);
  await screen.findByRole("option", {
    name: /ABC123 · Sede Principal ·/,
  });
  fireEvent.click(
    screen.getByRole("button", { name: /Confirmar pago en efectivo/i }),
  );

  const paymentCall = fetchMock.mock.calls.find(
    ([url]) => url === "/pagos/efectivo",
  );
  expect(JSON.parse(paymentCall[1].body)).toMatchObject({
    cobro_id: "cobro-recoverable",
  });
  expect(await screen.findByTestId("estado-badge")).toHaveTextContent("Pagado");
});