import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { PanelOperador } from "./PanelOperador.jsx";

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
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: "Error interno del servidor" }),
    }),
  );

  render(<PanelOperador />);
  fireEvent.change(screen.getByPlaceholderText(/00000000-0000/i), {
    target: { value: "11111111-1111-1111-1111-111111111111" },
  });
  fireEvent.click(screen.getByRole("button", { name: /Registrar ingreso/i }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Error interno del servidor",
  );
  expect(screen.getByText(/Panel del carril/i)).toBeInTheDocument();
});