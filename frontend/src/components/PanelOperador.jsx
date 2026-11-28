import { useState } from "react";

import { registerEntryByImage } from "../api/accessService.js";
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
  const [carrilId, setCarrilId] = useState("");
  const [placaInput, setPlacaInput] = useState("");
  const [confianzaInput, setConfianzaInput] = useState("0.98");
  const [referenciaPago, setReferenciaPago] = useState("");
  const [imagenEntrada, setImagenEntrada] = useState(null);
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

  async function llamarApi(url, body) {
    setCargando(true);
    setErrorApi("");
    try {
      const headers = { "Content-Type": "application/json" };
      if (token.trim()) {
        headers.Authorization = `Bearer ${token.trim()}`;
      }
      const resp = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        const detalle =
          typeof data.detail === "string"
            ? data.detail
            : `Error ${resp.status} al comunicarse con la API.`;
        throw new Error(detalle);
      }
      return data;
    } catch (err) {
      setErrorApi(err.message || "Error inesperado de conexión con la API.");
      return null;
    } finally {
      setCargando(false);
    }
  }

  async function manejarEntradaSimulada(e) {
    e.preventDefault();
    const confianza = Number(confianzaInput);
    const data = await llamarApi("/accesos/entrada/simulada", {
      carril_id: carrilId,
      placa: placaInput.trim().toUpperCase() || null,
      confianza_lpr: Number.isNaN(confianza) ? null : confianza,
    });

    if (!data) {
      if (confianza < 0.85) {
        setMostrarManual(true);
        setOperacion((prev) => ({
          ...prev,
          estado: "BAJA_CONFIANZA",
          placa: placaInput.trim().toUpperCase() || prev.placa,
          confianza,
          barreraAbierta: false,
          motivoBarrera:
            "Lectura con baja confianza. Se requiere validación manual del operador.",
        }));
      }
      return;
    }

    const tieneCobroPendiente = data.cobro_creado && Number(data.valor || 0) > 0;
    setMostrarManual(false);
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
  }

  async function manejarCargaImagen() {
    if (!carrilId.trim()) {
      setErrorApi("Selecciona un carril de entrada antes de operar.");
      return;
    }
    if (!imagenEntrada) {
      setErrorApi("Selecciona una imagen de placa.");
      return;
    }

    const formData = new FormData();
    formData.append("imagen", imagenEntrada);
    formData.append("carril_id", carrilId.trim());
    if (placaInput.trim()) {
      formData.append("placa_simulada", placaInput.trim().toUpperCase());
    }
    if (confianzaInput.trim()) {
      formData.append("confianza_simulada", confianzaInput.trim());
    }

    setCargando(true);
    setErrorApi("");
    try {
      const data = await registerEntryByImage(formData);
      setMostrarManual(false);
      setOperacion({
        estado:
          data.cobro_creado && Number(data.valor || 0) > 0
            ? "COBRO_PENDIENTE"
            : "BARRERA_ABIERTA",
        placa: data.placa,
        confianza: Number(data.confianza_lpr),
        tipoVehiculo: clasificarTipoVehiculo(data.placa),
        valorPagar: Number(data.valor || 0),
        cobroId: data.cobro_id,
        barreraAbierta: true,
        motivoBarrera: `Ingreso registrado por imagen (${data.franja}).`,
      });
    } catch (err) {
      setErrorApi(err.message || "No fue posible cargar la imagen.");
      if (
        err.status === 422 &&
        String(err.detail).includes("CONFIANZA_LPR_INSUFICIENTE")
      ) {
        const coincidencia = imagenEntrada.name.match(
          /^([A-Za-z0-9]+)_([0-9]+(?:\.[0-9]+)?)\.[A-Za-z0-9]+$/,
        );
        setMostrarManual(true);
        setOperacion((prev) => ({
          ...prev,
          estado: "BAJA_CONFIANZA",
          placa:
            placaInput.trim().toUpperCase() ||
            coincidencia?.[1]?.toUpperCase() ||
            prev.placa,
          confianza: confianzaInput.trim()
            ? Number(confianzaInput)
            : Number(coincidencia?.[2] ?? prev.confianza),
          barreraAbierta: false,
          motivoBarrera:
            "Lectura con baja confianza. Se requiere validación manual del operador.",
        }));
      }
    } finally {
      setCargando(false);
    }
  }

  async function manejarLecturaManual(e) {
    e.preventDefault();
    const placaLimpia = placaInput.trim().toUpperCase();
    const data = await llamarApi("/accesos/entrada", {
      evento_id: crypto.randomUUID(),
      placa: placaLimpia,
      carril_id: carrilId,
      ocurrido_en: new Date().toISOString(),
      confianza_lpr: 1.0,
      lectura_manual: true,
    });
    if (!data) return;

    setMostrarManual(false);
    setOperacion({
      estado: data.cobro_creado ? "COBRO_PENDIENTE" : "BARRERA_ABIERTA",
      placa: data.placa,
      confianza: 1.0,
      tipoVehiculo: clasificarTipoVehiculo(data.placa),
      valorPagar: Number(data.valor || 0),
      cobroId: data.cobro_id,
      barreraAbierta: true,
      motivoBarrera: `Lectura manual confirmada para ${data.placa}.`,
    });
  }

  async function manejarSalida(e) {
    e.preventDefault();
    const placaLimpia = placaInput.trim().toUpperCase() || operacion.placa;
    const data = await llamarApi("/accesos/salida", {
      placa: placaLimpia,
      carril_id: carrilId,
    });
    if (!data) return;

    setOperacion((prev) => ({
      ...prev,
      estado: data.barrera_abre ? "BARRERA_ABIERTA" : "COBRO_PENDIENTE",
      placa: data.placa,
      tipoVehiculo: clasificarTipoVehiculo(data.placa),
      barreraAbierta: data.barrera_abre,
      motivoBarrera: data.motivo,
    }));
  }

  async function manejarPagoEfectivo(e) {
    e.preventDefault();
    if (!operacion.cobroId) {
      setErrorApi("No hay un cobro pendiente asociado para registrar pago.");
      return;
    }
    const data = await llamarApi("/pagos/efectivo", {
      cobro_id: operacion.cobroId,
      referencia_pago: referenciaPago.trim() || `EF-${Date.now()}`,
    });
    if (!data) return;

    setOperacion((prev) => ({
      ...prev,
      estado: "PAGADO",
      valorPagar: Number(data.valor_pagado || prev.valorPagar),
      barreraAbierta: true,
      motivoBarrera: `Pago en efectivo confirmado (${data.referencia_pago}). Salida autorizada.`,
    }));
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
              <label>
                Token operador (Bearer)
                <input
                  type="password"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="Pega tu JWT de operador"
                />
              </label>
            )}
            <label>
              ID del carril (UUID)
              <input
                type="text"
                value={carrilId}
                onChange={(e) => setCarrilId(e.target.value)}
                placeholder="00000000-0000-0000-0000-000000000000"
                required
              />
            </label>
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
              <label className="btn-secondary">
                Cargar imagen
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/gif,image/webp"
                  onChange={(event) =>
                    setImagenEntrada(event.target.files?.[0] ?? null)
                  }
                  hidden
                />
              </label>
              <button
                type="button"
                className="btn-secondary"
                disabled={cargando || !imagenEntrada}
                onClick={manejarCargaImagen}
              >
                Registrar por imagen
              </button>
              <button type="submit" className="btn-primary" disabled={cargando}>
                Registrar ingreso
              </button>
              <button
                type="button"
                className="btn-secondary"
                disabled={cargando}
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
          <form onSubmit={manejarPagoEfectivo} className="form-stack">
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
              disabled={cargando || !operacion.cobroId}
            >
              Confirmar pago en efectivo ({formatearCOP(operacion.valorPagar)})
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
            <button type="submit" className="btn-primary" disabled={cargando}>
              Confirmar placa manual
            </button>
          </form>
        </section>
      )}
    </div>
  );
}