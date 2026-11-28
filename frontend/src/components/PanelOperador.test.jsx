import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { registerEntryByImage } from "../api/accessService.js";
import { listCarriles } from "../api/carrilService.js";
import { PanelOperador } from "./PanelOperador.jsx";

vi.mock("../api/accessService.js", () => ({
  registerEntryByImage: vi.fn(),
}));
vi.mock("../api/carrilService.js", () => ({
  listCarriles: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
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

it("carga los carriles desde la API y separa entrada de salida", async () => {
  listCarriles.mockResolvedValue([
    {
      id: "lane-in-a-12345678",
      sentido: "ENTRADA",
      sede_id: "site-a",
      sede_nombre: "Sede A",
    },
    {
      id: "lane-out-a-12345678",
      sentido: "SALIDA",
      sede_id: "site-a",
      sede_nombre: "Sede A",
    },
    {
      id: "lane-in-b-12345678",
      sentido: "ENTRADA",
      sede_id: "site-b",
      sede_nombre: "Sede B",
    },
    {
      id: "lane-out-b-12345678",
      sentido: "SALIDA",
      sede_id: "site-b",
      sede_nombre: "Sede B",
    },
  ]);
  render(<PanelOperador accessToken="operator-token" />);

  await waitFor(() => expect(listCarriles).toHaveBeenCalledWith("operator-token"));
  expect(screen.getByRole("combobox", { name: "Carril de entrada" })).toHaveValue(
    "lane-in-a-12345678",
  );
  expect(screen.getByRole("combobox", { name: "Carril de salida" })).toHaveValue(
    "lane-out-a-12345678",
  );
  expect(
    screen.getByRole("combobox", { name: "Carril de salida" }).options,
  ).toHaveLength(2);
  fireEvent.change(screen.getByRole("combobox", { name: "Carril de entrada" }), {
    target: { value: "lane-in-b-12345678" },
  });
  expect(screen.getByRole("combobox", { name: "Carril de salida" })).toHaveValue(
    "lane-out-b-12345678",
  );
});

it("envía la imagen automáticamente al seleccionarla usando el carril de entrada", async () => {
  listCarriles.mockResolvedValue([
    {
      id: "lane-in-12345678",
      sentido: "ENTRADA",
      sede_nombre: "Sede central",
    },
    {
      id: "lane-out-12345678",
      sentido: "SALIDA",
      sede_nombre: "Sede central",
    },
  ]);
  registerEntryByImage.mockResolvedValue({
    placa: "ABC123",
    confianza_lpr: 0.92,
    cobro_creado: true,
    valor: "12000.00",
    cobro_id: "charge-1",
    franja: "DIURNA",
  });
  render(<PanelOperador accessToken="operator-token" />);
  await waitFor(() =>
    expect(screen.getByRole("combobox", { name: "Carril de entrada" })).toHaveValue(
      "lane-in-12345678",
    ),
  );

  const image = new File(["jpeg"], "ABC123_0.92.jpg", { type: "image/jpeg" });
  fireEvent.change(screen.getByLabelText("Cargar imagen de placa"), {
    target: { files: [image] },
  });

  await waitFor(() => expect(registerEntryByImage).toHaveBeenCalledTimes(1));
  const formData = registerEntryByImage.mock.calls[0][0];
  expect(formData.get("imagen")).toBe(image);
  expect(formData.get("carril_id")).toBe("lane-in-12345678");
  expect(screen.queryByRole("button", { name: /Registrar por imagen/i })).toBeNull();
  expect(await screen.findByTestId("placa-leida")).toHaveTextContent("ABC123");
});

it("abre lectura manual cuando la imagen tiene confianza baja", async () => {
  listCarriles.mockResolvedValue([
    {
      id: "lane-in-12345678",
      sentido: "ENTRADA",
      sede_nombre: "Sede central",
    },
    {
      id: "lane-out-12345678",
      sentido: "SALIDA",
      sede_nombre: "Sede central",
    },
  ]);
  registerEntryByImage.mockRejectedValue({
    status: 422,
    detail: "CONFIANZA_LPR_INSUFICIENTE: validar manualmente",
    message: "La confianza de la lectura es baja.",
  });
  render(<PanelOperador accessToken="operator-token" />);
  await waitFor(() =>
    expect(screen.getByRole("combobox", { name: "Carril de entrada" })).toHaveValue(
      "lane-in-12345678",
    ),
  );

  fireEvent.change(screen.getByLabelText("Cargar imagen de placa"), {
    target: {
      files: [new File(["jpeg"], "ABC123_0.40.jpg", { type: "image/jpeg" })],
    },
  });

  expect(
    await screen.findByRole("button", { name: /Confirmar placa manual/i }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Placa corregida")).toHaveValue("ABC123");
});

it("muestra error de la API sin dejar la pantalla en blanco", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: "Error interno del servidor" }),
    }),
  );

  listCarriles.mockResolvedValue([
    {
      id: "lane-in-12345678",
      sentido: "ENTRADA",
      sede_nombre: "Sede central",
    },
    {
      id: "lane-out-12345678",
      sentido: "SALIDA",
      sede_nombre: "Sede central",
    },
  ]);
  render(<PanelOperador accessToken="operator-token" />);
  await waitFor(() => expect(listCarriles).toHaveBeenCalled());
  fireEvent.change(screen.getByRole("combobox", { name: "Carril de entrada" }), {
    target: { value: "lane-in-12345678" },
  });
  fireEvent.click(screen.getByRole("button", { name: /Registrar ingreso/i }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Error interno del servidor",
  );
  expect(screen.getByText(/Panel del carril/i)).toBeInTheDocument();
});

it("detecta salida cuando se vuelve a subir la imagen de una placa ya registrada", async () => {
  listCarriles.mockResolvedValue([
    {
      id: "lane-in-12345678",
      sentido: "ENTRADA",
      sede_id: "site-1",
      sede_nombre: "Sede central",
    },
    {
      id: "lane-out-12345678",
      sentido: "SALIDA",
      sede_id: "site-1",
      sede_nombre: "Sede central",
    },
  ]);
  registerEntryByImage
    .mockResolvedValueOnce({
      placa: "ABC123",
      confianza_lpr: 0.92,
      cobro_creado: true,
      valor: "12000.00",
      cobro_id: "charge-1",
      franja: "DIURNA",
      tipo_movimiento: "ENTRADA",
      barrera_abre: true,
    })
    .mockResolvedValueOnce({
      placa: "ABC123",
      confianza_lpr: 0.92,
      cobro_creado: false,
      valor: "12000.00",
      cobro_id: "charge-1",
      tipo_movimiento: "SALIDA",
      barrera_abre: false,
      motivo: "F-05: Salida rechazada. El vehículo posee una deuda pendiente.",
    });

  render(<PanelOperador accessToken="operator-token" />);
  await waitFor(() =>
    expect(screen.getByRole("combobox", { name: "Carril de entrada" })).toHaveValue(
      "lane-in-12345678",
    ),
  );

  const image = new File(["jpeg"], "ABC123_0.92.jpg", { type: "image/jpeg" });
  fireEvent.change(screen.getByLabelText("Cargar imagen de placa"), {
    target: { files: [image] },
  });
  expect(await screen.findByText(/Entrada registrada/i)).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Cargar imagen de placa"), {
    target: { files: [image] },
  });

  expect(await screen.findByText(/Salida detectada/i)).toBeInTheDocument();
  expect(screen.getByText(/✕ BARRERA CERRADA/i)).toBeInTheDocument();
  expect(screen.getByTestId("estado-badge")).toHaveTextContent("Cobro pendiente");
  expect(
    screen.getByRole("button", { name: /Confirmar pago en efectivo/i }),
  ).toBeEnabled();
});

it("elimina el botón redundante y normaliza la placa al registrar ingreso o salida directo", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({
      placa: "ABC123",
      carril_id: "lane-out-12345678",
      barrera_abre: false,
      motivo: "F-05: Salida rechazada. El vehículo posee una deuda pendiente.",
      registrado_en: "2026-03-10T14:00:00Z",
      cobro_id: "charge-99",
      valor: "12000.00",
    }),
  });
  vi.stubGlobal("fetch", fetchMock);

  listCarriles.mockResolvedValue([
    {
      id: "lane-in-12345678",
      sentido: "ENTRADA",
      sede_id: "site-1",
      sede_nombre: "Sede central",
    },
    {
      id: "lane-out-12345678",
      sentido: "SALIDA",
      sede_id: "site-1",
      sede_nombre: "Sede central",
    },
  ]);

  render(<PanelOperador accessToken="operator-token" />);
  await waitFor(() =>
    expect(screen.getByRole("combobox", { name: "Carril de entrada" })).toHaveValue(
      "lane-in-12345678",
    ),
  );

  expect(
    screen.queryByRole("button", { name: /Validar placa manualmente/i }),
  ).not.toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Placa"), {
    target: { value: "  abc-123  " },
  });
  fireEvent.click(screen.getByRole("button", { name: /Validar salida/i }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
    placa: "ABC123",
    carril_id: "lane-out-12345678",
  });
  expect(await screen.findByTestId("placa-leida")).toHaveTextContent("ABC123");
  expect(screen.getByTestId("estado-badge")).toHaveTextContent("Cobro pendiente");
  expect(
    screen.getByRole("button", { name: /Confirmar pago en efectivo/i }),
  ).toBeEnabled();
});