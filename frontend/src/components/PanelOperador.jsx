import { useCallback, useEffect, useState } from "react";

import { listCarriles } from "../api/carrilService.js";
import { apiClient } from "../api/client.js";
import { listPendingPayments } from "../api/paymentService.js";
import { EstadoBadge } from "./EstadoBadge.jsx";
import { PanelBarrera } from "./PanelBarrera.jsx";

function clasificarTipoVehiculo(placa) {
  const limpia = (placa || "").trim().toUpperCase();
  if (/^[A-Z]{3}\d{3}$/.test(limpia)) return "Automóvil (CARRO)";
  if (/^[A-Z]{3}\d{2}[A-Z]$/.test(limpia)) return "Motocicleta (MOTO)";
  return "Sin clasificar";
}

function formatearCOP(valor) {
  if (valor === null || valor === undefined) return "$ 0";
  return `$ ${Number(valor).toLocaleString("es-CO")}`;
}

export function PanelOperador({ estadoInicial = null, accessToken = "" }) {
  const [token, setToken] = useState(accessToken);
  const [carriles, setCarriles] = useState([]);
  const [carrilEntradaId, setCarrilEntradaId] = useState("");
  const [carrilSalidaId, setCarrilSalidaId] = useState("");
  const [cargandoCarriles, setCargandoCarriles] = useState(Boolean(accessToken));
  const [errorCarriles, setErrorCarriles] = useState("");
  const [cobrosPendientes, setCobrosPendientes] = useState([]);
  const [cargandoCobros, setCargandoCobros] = useState(Boolean(accessToken));
  const [errorCobros, setErrorCobros] = useState("");
  const [cobroSeleccionadoId, setCobroSeleccionadoId] = useState(
    estadoInicial?.cobroId || "",
  );
  const [placaInput, setPlacaInput] = useState("");
  const [confianzaInput, setConfianzaInput] = useState("0.98");
  const [referenciaPago, setReferenciaPago] = useState("");
  const [cargando, setCargando] = useState(false);
  const [errorApi, setErrorApi] = useState("");
  const [mostrarManual, setMostrarManual] = useState(
    Boolean(estadoInicial?.requiereManual),
  );

  const [operacion, setOperacion] = useState(
    estadoInicial || {
      estado: "ESPERANDO",
      placa: "---",
      confianza: null,
      tipoVehiculo: "---",
      valorPagar: 0,
      cobroId: null,
      barreraAbierta: false,
      motivoBarrera: "Esperando lectura de vehículo en el carril.",
    },
  );

  const cargarCarriles = useCallback(async (tokenAcceso) => {
    setCargandoCarriles(true);
    setErrorCarriles("");
    try {
      const resultado = await listCarriles(tokenAcceso);
      if (!Array.isArray(resultado)) {
        throw new Error("La API devolvió un catálogo de carriles inválido.");
      }
      setCarriles(resultado);
      setCarrilEntradaId((seleccionActual) =>
        resultado.some(
          (carril) =>
            carril.id === seleccionActual && carril.sentido === "ENTRADA",
        )
          ? seleccionActual
          : (resultado.find((carril) => carril.sentido === "ENTRADA")?.id ?? ""),
      );
      setCarrilSalidaId((seleccionActual) =>
        resultado.some(
          (carril) =>
            carril.id === seleccionActual && carril.sentido === "SALIDA",
        )
          ? seleccionActual
          : (resultado.find((carril) => carril.sentido === "SALIDA")?.id ?? ""),
      );
    } catch (error) {
      setCarriles([]);
      setErrorCarriles(
        error.message || "No fue posible consultar los carriles configurados.",
      );
    } finally {
      setCargandoCarriles(false);
    }
  }, []);

  const cargarCobrosPendientes = useCallback(async (tokenAcceso) => {
    setCargandoCobros(true);
    setErrorCobros("");
    try {
      const resultado = await listPendingPayments(tokenAcceso);
      if (!Array.isArray(resultado)) {
        throw new Error("La API devolvió una lista de cobros inválida.");
      }
      setCobrosPendientes(resultado);
      setCobroSeleccionadoId((seleccionActual) =>
        resultado.some((cobro) => cobro.cobro_id === seleccionActual)
          ? seleccionActual
          : (resultado[0]?.cobro_id ?? ""),
      );
    } catch (error) {
      setCobrosPendientes([]);
      setErrorCobros(
        error.message || "No fue posible consultar los cobros pendientes.",
      );
    } finally {
      setCargandoCobros(false);
    }
  }, []);

  useEffect(() => {
    if (accessToken) {
      void cargarCarriles(accessToken);
      void cargarCobrosPendientes(accessToken);
    }
  }, [accessToken, cargarCarriles, cargarCobrosPendientes]);

  const carrilesEntrada = carriles.filter(
    (carril) => carril.sentido === "ENTRADA",
  );
  const carrilEntrada =
    carrilesEntrada.find((carril) => carril.id === carrilEntradaId) ?? null;
  const carrilesSalida = carriles.filter(
    (carril) =>
      carril.sentido === "SALIDA" &&
      (!carrilEntrada || carril.sede_id === carrilEntrada.sede_id),
  );
  const carrilSalida =
    carrilesSalida.find((carril) => carril.id === carrilSalidaId) ?? null;
  const carrilesConfigurados = carrilEntrada !== null && carrilSalida !== null;
  const cobroSeleccionado =
    cobrosPendientes.find(
      (cobro) => cobro.cobro_id === cobroSeleccionadoId,
    ) ?? null;
  const valorCobroSeleccionado = Number(
    cobroSeleccionado?.valor ?? operacion.valorPagar,
  );
  const errorConfiguracionCarriles =
    !cargandoCarriles && !errorCarriles && (token.trim() || accessToken)
      ? !carrilEntrada
        ? "No hay un carril de entrada disponible para operar."
        : carrilesSalida.length === 0
          ? "No hay un carril de salida en la sede seleccionada."
        : !carrilSalida
          ? "Selecciona un carril de salida de la misma sede."
          : ""
      : "";

  async function llamarApi(url, body) {
    setCargando(true);
    setErrorApi("");
    try {
      const headers = {};
      if (token.trim()) {
        headers.Authorization = `Bearer ${token.trim()}`;
      }
      return await apiClient.post(url, body, { headers });
    } catch (err) {
      setErrorApi(err.message || "Error inesperado de conexión con la API.");
      if (
        url === "/accesos/entrada/simulada" &&
        err.status === 422 &&
        String(err.detail).includes("CONFIANZA_LPR_INSUFICIENTE")
      ) {
        setMostrarManual(true);
        setOperacion((prev) => ({
          ...prev,
          estado: "BAJA_CONFIANZA",
          placa: placaInput.trim().toUpperCase() || prev.placa,
          confianza: Number(body.confianza_lpr),
          barreraAbierta: false,
          motivoBarrera:
            "Lectura con baja confianza. Se requiere validación manual del operador.",
        }));
      }
      return null;
    } finally {
      setCargando(false);
    }
  }

  async function manejarEntradaSimulada(e) {
    e.preventDefault();
    if (!carrilEntrada) {
      setErrorApi("Selecciona o carga un carril de entrada antes de operar.");
      return;
    }
    const confianza = Number(confianzaInput);
    const data = await llamarApi("/accesos/entrada/simulada", {
      carril_id: carrilEntrada.id,
      placa: placaInput.trim().toUpperCase() || null,
      confianza_lpr: Number.isNaN(confianza) ? null : confianza,
    });

    if (!data) {
      return;
    }

    const tieneCobroPendiente =
      Boolean(data.cobro_id) && Number(data.valor || 0) > 0;
    setMostrarManual(false);
    setCobroSeleccionadoId(data.cobro_id || "");
    setOperacion({
      estado: tieneCobroPendiente ? "COBRO_PENDIENTE" : "BARRERA_ABIERTA",
      placa: data.placa,
      confianza,
      tipoVehiculo: clasificarTipoVehiculo(data.placa),
      valorPagar: Number(data.valor || 0),
      cobroId: data.cobro_id,
      barreraAbierta: true,
      motivoBarrera: data.pase_vigente
        ? `Ingreso autorizado para ${data.placa} con pase vigente.`
        : `Ingreso registrado (${data.franja}).`,
    });
    void cargarCobrosPendientes(token);
  }

  async function manejarLecturaManual(e) {
    e.preventDefault();
    if (!carrilEntrada) {
      setErrorApi("Selecciona o carga un carril de entrada antes de operar.");
      return;
    }
    const placaLimpia = placaInput.trim().toUpperCase();
    const data = await llamarApi("/accesos/entrada", {
      evento_id: crypto.randomUUID(),
      placa: placaLimpia,
      carril_id: carrilEntrada.id,
      ocurrido_en: new Date().toISOString(),
      confianza_lpr: 1.0,
      lectura_manual: true,
    });
    if (!data) return;

    setMostrarManual(false);
    setCobroSeleccionadoId(data.cobro_id || "");
    setOperacion({
      estado:
        data.cobro_id && Number(data.valor || 0) > 0
          ? "COBRO_PENDIENTE"
          : "BARRERA_ABIERTA",
      placa: data.placa,
      confianza: 1.0,
      tipoVehiculo: clasificarTipoVehiculo(data.placa),
      valorPagar: Number(data.valor || 0),
      cobroId: data.cobro_id,
      barreraAbierta: true,
      motivoBarrera: `Lectura manual confirmada para ${data.placa}.`,
    });
    void cargarCobrosPendientes(token);
  }

  async function manejarSalida(e) {
    e.preventDefault();
    if (!carrilSalida) {
      setErrorApi("Selecciona un carril de salida de la sede antes de operar.");
      return;
    }
    const placaLimpia = placaInput.trim().toUpperCase() || operacion.placa;
    const data = await llamarApi("/accesos/salida", {
      placa: placaLimpia,
      carril_id: carrilSalida.id,
    });
    if (!data) return;

    const cobroPendiente = cobrosPendientes.find(
      (cobro) => cobro.placa === data.placa,
    );
    if (!data.barrera_abre && cobroPendiente) {
      setCobroSeleccionadoId(cobroPendiente.cobro_id);
    }
    setOperacion((prev) => ({
      ...prev,
      estado: data.barrera_abre ? "BARRERA_ABIERTA" : "COBRO_PENDIENTE",
      placa: data.placa,
      tipoVehiculo: clasificarTipoVehiculo(data.placa),
      cobroId: cobroPendiente?.cobro_id ?? prev.cobroId,
      valorPagar: Number(cobroPendiente?.valor ?? prev.valorPagar),
      barreraAbierta: data.barrera_abre,
      motivoBarrera: data.motivo,
    }));
  }

  async function manejarPagoEfectivo(e) {
    e.preventDefault();
    if (!cobroSeleccionadoId) {
      setErrorApi("Selecciona un cobro pendiente para registrar el pago.");
      return;
    }
    const data = await llamarApi("/pagos/efectivo", {
      cobro_id: cobroSeleccionadoId,
      referencia_pago: referenciaPago.trim() || `EF-${Date.now()}`,
    });
    if (!data) return;

    const cobroPagado = cobrosPendientes.find(
      (cobro) => cobro.cobro_id === cobroSeleccionadoId,
    );
    setOperacion((prev) => ({
      ...prev,
      estado: "PAGADO",
      placa: cobroPagado?.placa ?? prev.placa,
      cobroId: null,
      valorPagar: Number(data.valor_pagado || prev.valorPagar),
      barreraAbierta: true,
      motivoBarrera: `Pago en efectivo confirmado (${data.referencia_pago}). Salida autorizada.`,
    }));
    setCobrosPendientes((actuales) =>
      actuales.filter((cobro) => cobro.cobro_id !== cobroSeleccionadoId),
    );
    setCobroSeleccionadoId("");
    setReferenciaPago("");
  }

  return (
    <div className="operador-layout">
      <div className="panel-header">
        <div>
          <span className="eyebrow">OPERACIÓN EN VIVO</span>
          <h1>Panel del carril</h1>
        </div>
        <EstadoBadge estado={operacion.estado} />
      </div>

      {errorApi && (
        <div className="alerta-error" role="alert">
          <strong>Error de operación:</strong> {errorApi}
        </div>
      )}

      {operacion.estado === "LLENO" && (
        <div className="alerta-lleno" role="alert">
          <strong>LLENO:</strong> No se permiten nuevos ingresos. Las salidas
          continúan habilitadas.
        </div>
      )}

      <div className="grid-principal">
        <section className="card lectura-card" aria-label="Última lectura">
          <span className="eyebrow">ÚLTIMA LECTURA</span>
          <div className="lectura-top">
            <div className="placa-display" data-testid="placa-leida">
              {operacion.placa}
            </div>
            <div className="confianza-box">
              <span className="eyebrow">CONFIANZA OCR</span>
              <strong data-testid="confianza-ocr">
                {operacion.confianza !== null
                  ? `${(operacion.confianza * 100).toFixed(1)} %`
                  : "-- %"}
              </strong>
            </div>
          </div>

          <div className="lectura-detalles">
            <div>
              <span className="eyebrow">TIPO DE VEHÍCULO</span>
              <p data-testid="tipo-vehiculo">{operacion.tipoVehiculo}</p>
            </div>
            <div>
              <span className="eyebrow">VALOR A PAGAR</span>
              <p className="valor-cop" data-testid="valor-pagar">
                {formatearCOP(operacion.valorPagar)}
              </p>
            </div>
          </div>
        </section>

        <PanelBarrera
          abierta={operacion.barreraAbierta}
          motivo={operacion.motivoBarrera}
        />
      </div>

      <div className="grid-acciones">
        <section className="card">
          <span className="eyebrow">CONTROL DE CARRIL</span>
          <form onSubmit={manejarEntradaSimulada} className="form-stack">
            {!accessToken && (
              <>
                <label>
                  Token operador (Bearer)
                  <input
                    type="password"
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                    placeholder="Pega tu JWT de operador"
                  />
                </label>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => {
                    void cargarCarriles(token);
                    void cargarCobrosPendientes(token);
                  }}
                  disabled={cargandoCarriles || cargandoCobros || !token.trim()}
                >
                  Cargar datos de operación
                </button>
              </>
            )}
            {cargandoCarriles && (
              <p role="status">Consultando carriles configurados...</p>
            )}
            {errorCarriles && (
              <div className="alerta-error" role="alert">
                {errorCarriles}
              </div>
            )}
            {errorConfiguracionCarriles && (
              <div className="alerta-error" role="alert">
                {errorConfiguracionCarriles}
              </div>
            )}
            <div className="form-row">
              <label>
                Carril de entrada
                <select
                  aria-label="Carril de entrada"
                  disabled={cargandoCarriles || carrilesEntrada.length === 0}
                  onChange={(event) => {
                    const selectedId = event.target.value;
                    const selectedLane = carrilesEntrada.find(
                      (carril) => carril.id === selectedId,
                    );
                    setCarrilEntradaId(selectedId);
                    setCarrilSalidaId((current) => {
                      const compatibleLanes = carriles.filter(
                        (carril) =>
                          carril.sentido === "SALIDA" &&
                          carril.sede_id === selectedLane?.sede_id,
                      );
                      return compatibleLanes.some(
                        (carril) => carril.id === current,
                      )
                        ? current
                        : (compatibleLanes[0]?.id ?? "");
                    });
                  }}
                  value={carrilEntradaId}
                >
                  {carrilesEntrada.length === 0 && (
                    <option value="">No hay carriles de entrada</option>
                  )}
                  {carrilesEntrada.map((carril) => (
                    <option key={carril.id} value={carril.id}>
                      {carril.sede_nombre} · {carril.id.slice(0, 8)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Carril de salida
                <select
                  aria-label="Carril de salida"
                  disabled={cargandoCarriles || carrilesSalida.length === 0}
                  onChange={(event) => setCarrilSalidaId(event.target.value)}
                  value={carrilSalidaId}
                >
                  {carrilesSalida.length === 0 && (
                    <option value="">No hay carriles para esta sede</option>
                  )}
                  {carrilesSalida.map((carril) => (
                    <option key={carril.id} value={carril.id}>
                      {carril.sede_nombre} · {carril.id.slice(0, 8)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {carrilesConfigurados && (
              <p className="muted" data-testid="carriles-configurados">
                Ingreso: {carrilEntrada.sede_nombre} ·{" "}
                {carrilEntrada.id.slice(0, 8)}. Salida:{" "}
                {carrilSalida.sede_nombre} · {carrilSalida.id.slice(0, 8)}.
              </p>
            )}
            <div className="form-row">
              <label>
                Placa
                <input
                  type="text"
                  value={placaInput}
                  onChange={(e) => setPlacaInput(e.target.value)}
                  placeholder="ABC123"
                />
              </label>
              <label>
                Confianza LPR (0 a 1)
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="1"
                  value={confianzaInput}
                  onChange={(e) => setConfianzaInput(e.target.value)}
                />
              </label>
            </div>
            <div className="btn-group">
              <button
                type="submit"
                className="btn-primary"
                disabled={
                  cargando ||
                  cargandoCarriles ||
                  cargandoCobros ||
                  !carrilesConfigurados
                }
              >
                Registrar ingreso
              </button>
              <button
                type="button"
                className="btn-secondary"
                disabled={
                  cargando ||
                  cargandoCarriles ||
                  cargandoCobros ||
                  !carrilSalida
                }
                onClick={manejarSalida}
              >
                Validar salida
              </button>
              <button
                type="button"
                className="btn-warning"
                onClick={() => setMostrarManual((v) => !v)}
              >
                Validar placa manualmente
              </button>
            </div>
          </form>
        </section>

        <section className="card">
          <span className="eyebrow">CAJA · PAGO EN EFECTIVO</span>
          {errorCobros && (
            <div className="alerta-error" role="alert">
              {errorCobros}
            </div>
          )}
          {cargandoCobros && (
            <p role="status">Consultando cobros pendientes...</p>
          )}
          <form onSubmit={manejarPagoEfectivo} className="form-stack">
            <label>
              Cobro pendiente
              <select
                aria-label="Cobro pendiente"
                disabled={cargandoCobros}
                onChange={(event) => {
                  const selectedId = event.target.value;
                  const selectedCharge = cobrosPendientes.find(
                    (cobro) => cobro.cobro_id === selectedId,
                  );
                  setCobroSeleccionadoId(selectedId);
                  if (selectedCharge) {
                    setOperacion((previous) => ({
                      ...previous,
                      placa: selectedCharge.placa,
                      cobroId: selectedId,
                      valorPagar: Number(selectedCharge.valor),
                    }));
                  }
                }}
                value={cobroSeleccionadoId}
              >
                <option value="">
                  {cobrosPendientes.length
                    ? "Selecciona un cobro"
                    : "No hay cobros pendientes"}
                </option>
                {cobrosPendientes.map((cobro) => (
                  <option key={cobro.cobro_id} value={cobro.cobro_id}>
                    {cobro.placa} · {cobro.sede_nombre} ·{" "}
                    {formatearCOP(cobro.valor)}
                  </option>
                ))}
                {cobroSeleccionadoId &&
                  !cobroSeleccionado &&
                  cobroSeleccionadoId === operacion.cobroId && (
                    <option value={cobroSeleccionadoId}>
                      Último ingreso · {operacion.placa}
                    </option>
                  )}
              </select>
            </label>
            <label>
              Referencia de pago
              <input
                type="text"
                value={referenciaPago}
                onChange={(e) => setReferenciaPago(e.target.value)}
                placeholder="REC-001"
              />
            </label>
            <button
              type="submit"
              className="btn-primary"
              disabled={cargando || cargandoCobros || !cobroSeleccionadoId}
            >
              Confirmar pago en efectivo (
              {formatearCOP(valorCobroSeleccionado)})
            </button>
          </form>
        </section>
      </div>

      {mostrarManual && (
        <section className="card card-manual" aria-label="Validación manual">
          <div className="alerta-warning">
            <strong>Lectura con baja confianza:</strong> Verifica la placa física
            del vehículo antes de confirmar.
          </div>
          <form onSubmit={manejarLecturaManual} className="form-row">
            <label>
              Placa corregida
              <input
                type="text"
                value={placaInput}
                onChange={(e) => setPlacaInput(e.target.value)}
                placeholder="ABC123"
                required
              />
            </label>
            <button
              type="submit"
              className="btn-primary"
              disabled={
                cargando ||
                cargandoCarriles ||
                cargandoCobros ||
                !carrilesConfigurados
              }
            >
              Confirmar placa manual
            </button>
          </form>
        </section>
      )}
    </div>
  );
}