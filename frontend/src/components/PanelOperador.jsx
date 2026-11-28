import { useEffect, useState } from "react";

import { registerEntryByImage } from "../api/accessService.js";
import { listCarriles } from "../api/carrilService.js";
import { getAccessToken } from "../auth/tokenStore.js";
import Alert from "./Alert.jsx";
import { EstadoBadge } from "./EstadoBadge.jsx";
import { IconUpload } from "./Icons.jsx";
import { PanelBarrera } from "./PanelBarrera.jsx";

function normalizarPlaca(placa) {
  return (placa || "").trim().toUpperCase().replace(/[\s-]+/g, "");
}

function clasificarTipoVehiculo(placa) {
  const limpia = normalizarPlaca(placa);
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
  const [errorCarriles, setErrorCarriles] = useState("");
  const [cargandoCarriles, setCargandoCarriles] = useState(Boolean(accessToken));
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
      tipoMovimiento: null,
      valorPagar: 0,
      cobroId: null,
      barreraAbierta: false,
      motivoBarrera: "Esperando lectura de vehículo en el carril.",
    },
  );
  const carrilesEntrada = carriles.filter(
    (carril) =>
      carril.sentido === "ENTRADA" &&
      carriles.some(
        (posibleSalida) =>
          posibleSalida.sentido === "SALIDA" &&
          posibleSalida.sede_id === carril.sede_id,
      ),
  );
  const carrilEntradaSeleccionado = carriles.find(
    (carril) => carril.id === carrilEntradaId,
  );
  const carrilesSalida = carriles.filter(
    (carril) =>
      carril.sentido === "SALIDA" &&
      carril.sede_id === carrilEntradaSeleccionado?.sede_id,
  );

  useEffect(() => {
    const tokenCarriles = (accessToken || token).trim();
    if (!tokenCarriles) {
      setCargandoCarriles(false);
      setCarriles([]);
      setCarrilEntradaId("");
      setCarrilSalidaId("");
      setErrorCarriles("");
      return undefined;
    }

    let active = true;
    setCargandoCarriles(true);
    setCarriles([]);
    setCarrilEntradaId("");
    setCarrilSalidaId("");
    setErrorCarriles("");
    const timeoutId = setTimeout(() => {
      listCarriles(tokenCarriles)
        .then((resultado) => {
          if (!active) return;
          if (!Array.isArray(resultado)) {
            throw new Error("La API devolvió un listado de carriles inválido.");
          }
          setCarriles(resultado);
          const entradaConSalida = resultado.find(
            (carril) =>
              carril.sentido === "ENTRADA" &&
              resultado.some(
                (posibleSalida) =>
                  posibleSalida.sentido === "SALIDA" &&
                  posibleSalida.sede_id === carril.sede_id,
              ),
          );
          if (!entradaConSalida) {
            setErrorCarriles(
              "La base de datos no tiene configurado un par de carriles de entrada y salida para la misma sede.",
            );
            return;
          }
          setCarrilEntradaId(entradaConSalida.id);
          setCarrilSalidaId(
            resultado.find(
              (carril) =>
                carril.sentido === "SALIDA" &&
                carril.sede_id === entradaConSalida.sede_id,
            ).id,
          );
        })
        .catch((error) => {
          if (active) {
            setErrorCarriles(
              error.message ||
                "No fue posible consultar los carriles de la base de datos.",
            );
          }
        })
        .finally(() => {
          if (active) setCargandoCarriles(false);
        });
    }, 250);

    return () => {
      active = false;
      clearTimeout(timeoutId);
    };
  }, [accessToken, token]);

  async function llamarApi(url, body) {
    setCargando(true);
    setErrorApi("");
    try {
      const headers = { "Content-Type": "application/json" };
      const tokenActivo = (accessToken || token).trim();
      if (tokenActivo) {
        headers.Authorization = `Bearer ${tokenActivo}`;
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
            : Array.isArray(data.detail)
              ? data.detail.map((item) => item?.msg).filter(Boolean).join("; ")
              : `Error ${resp.status} al comunicarse con la API.`;
        throw new Error(detalle || `Error ${resp.status} al comunicarse con la API.`);
      }
      return { data, error: null };
    } catch (err) {
      const mensaje = err.message || "Error inesperado de conexión con la API.";
      setErrorApi(mensaje);
      return { data: null, error: mensaje };
    } finally {
      setCargando(false);
    }
  }

  async function manejarEntradaSimulada(e) {
    e.preventDefault();
    if (!carrilEntradaId) {
      setErrorApi("No hay un carril de entrada disponible en la base de datos.");
      return;
    }
    const placaLimpia = normalizarPlaca(placaInput);
    const confianza = Number(confianzaInput);
    const { data, error } = await llamarApi("/accesos/entrada/simulada", {
      carril_id: carrilEntradaId,
      placa: placaLimpia || null,
      confianza_lpr: Number.isNaN(confianza) ? null : confianza,
    });

    if (!data) {
      if (String(error).includes("LLENO")) {
        setOperacion((prev) => ({
          ...prev,
          estado: "LLENO",
          placa: placaLimpia || prev.placa,
          barreraAbierta: false,
          motivoBarrera: error,
        }));
      } else if (
        String(error).includes("CONFIANZA_LPR_INSUFICIENTE") ||
        confianza < 0.85
      ) {
        setMostrarManual(true);
        setOperacion((prev) => ({
          ...prev,
          estado: "BAJA_CONFIANZA",
          placa: placaLimpia || prev.placa,
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
    setPlacaInput(data.placa);
    setOperacion({
      estado: tieneCobroPendiente ? "COBRO_PENDIENTE" : "BARRERA_ABIERTA",
      placa: data.placa,
      confianza,
      tipoVehiculo: clasificarTipoVehiculo(data.placa),
      tipoMovimiento: "ENTRADA",
      valorPagar: Number(data.valor || 0),
      cobroId: data.cobro_id,
      barreraAbierta: true,
      motivoBarrera: data.pase_vigente
        ? `Ingreso autorizado para ${data.placa} con pase vigente.`
        : `Ingreso registrado (${data.franja}).`,
    });
  }

  async function manejarCargaImagen(imagen = imagenEntrada) {
    if (!carrilEntradaId) {
      setErrorApi("No hay un carril de entrada disponible en la base de datos.");
      return;
    }
    if (!imagen) {
      setErrorApi("Selecciona una imagen de placa.");
      return;
    }

    const formData = new FormData();
    formData.append("imagen", imagen);
    formData.append("carril_id", carrilEntradaId);
    if (carrilSalidaId) {
      formData.append("carril_salida_id", carrilSalidaId);
    }

    const tokenActivo = (accessToken || token).trim();
    const requestOptions =
      tokenActivo && !getAccessToken()
        ? { headers: { Authorization: `Bearer ${tokenActivo}` } }
        : undefined;

    setCargando(true);
    setErrorApi("");
    try {
      const data = requestOptions
        ? await registerEntryByImage(formData, requestOptions)
        : await registerEntryByImage(formData);
      setMostrarManual(false);
      setPlacaInput(data.placa);
      if (data.tipo_movimiento === "SALIDA") {
        const barreraAbierta = Boolean(data.barrera_abre);
        setOperacion({
          estado: barreraAbierta ? "BARRERA_ABIERTA" : "COBRO_PENDIENTE",
          placa: data.placa,
          confianza: Number(data.confianza_lpr),
          tipoVehiculo: clasificarTipoVehiculo(data.placa),
          tipoMovimiento: "SALIDA",
          valorPagar: barreraAbierta ? 0 : Number(data.valor || 0),
          cobroId: barreraAbierta ? null : (data.cobro_id ?? null),
          barreraAbierta,
          motivoBarrera:
            data.motivo ||
            (barreraAbierta
              ? `Salida detectada y autorizada para ${data.placa}.`
              : `Salida detectada para ${data.placa} con cobro pendiente.`),
        });
        return;
      }

      setOperacion({
        estado:
          data.cobro_creado && Number(data.valor || 0) > 0
            ? "COBRO_PENDIENTE"
            : "BARRERA_ABIERTA",
        placa: data.placa,
        confianza: Number(data.confianza_lpr),
        tipoVehiculo: clasificarTipoVehiculo(data.placa),
        tipoMovimiento: "ENTRADA",
        valorPagar: Number(data.valor || 0),
        cobroId: data.cobro_id,
        barreraAbierta: true,
        motivoBarrera:
          data.motivo || `Ingreso registrado por imagen (${data.franja}).`,
      });
    } catch (err) {
      setErrorApi(err.message || "No fue posible cargar la imagen.");
      const detalle = String(err.detail || err.message || "");
      if (err.status === 409 && detalle.includes("LLENO")) {
        setOperacion((prev) => ({
          ...prev,
          estado: "LLENO",
          barreraAbierta: false,
          motivoBarrera: err.message || detalle,
        }));
      } else if (
        err.status === 422 &&
        detalle.includes("CONFIANZA_LPR_INSUFICIENTE")
      ) {
        const coincidencia = imagen.name.match(
          /^([A-Za-z0-9 -]+)_([0-9]+(?:\.[0-9]+)?)\.[A-Za-z0-9]+$/,
        );
        const placaExtraida = normalizarPlaca(coincidencia?.[1]);
        setPlacaInput(placaExtraida);
        setMostrarManual(true);
        setOperacion((prev) => ({
          ...prev,
          estado: "BAJA_CONFIANZA",
          placa: placaExtraida || prev.placa,
          confianza: Number(coincidencia?.[2] ?? prev.confianza),
          barreraAbierta: false,
          motivoBarrera:
            "Lectura con baja confianza. Se requiere validación manual del operador.",
        }));
      }
    } finally {
      setCargando(false);
    }
  }

  function manejarSeleccionImagen(event) {
    const imagen = event.target.files?.[0] ?? null;
    event.target.value = "";
    if (!imagen) return;
    setImagenEntrada(imagen);
    void manejarCargaImagen(imagen);
  }

  async function manejarLecturaManual(e) {
    e.preventDefault();
    if (!carrilEntradaId) {
      setErrorApi("No hay un carril de entrada disponible en la base de datos.");
      return;
    }
    const placaLimpia = normalizarPlaca(placaInput);
    if (!placaLimpia) {
      setErrorApi("Ingresa una placa válida para confirmar la lectura manual.");
      return;
    }
    const { data, error } = await llamarApi("/accesos/entrada", {
      evento_id: crypto.randomUUID(),
      placa: placaLimpia,
      carril_id: carrilEntradaId,
      ocurrido_en: new Date().toISOString(),
      confianza_lpr: 1.0,
      lectura_manual: true,
    });
    if (!data) {
      if (String(error).includes("LLENO")) {
        setOperacion((prev) => ({
          ...prev,
          estado: "LLENO",
          placa: placaLimpia,
          barreraAbierta: false,
          motivoBarrera: error,
        }));
      }
      return;
    }

    setMostrarManual(false);
    setPlacaInput(data.placa);
    setOperacion({
      estado: data.cobro_creado ? "COBRO_PENDIENTE" : "BARRERA_ABIERTA",
      placa: data.placa,
      confianza: 1.0,
      tipoVehiculo: clasificarTipoVehiculo(data.placa),
      tipoMovimiento: "ENTRADA",
      valorPagar: Number(data.valor || 0),
      cobroId: data.cobro_id,
      barreraAbierta: true,
      motivoBarrera: `Lectura manual confirmada para ${data.placa}.`,
    });
  }

  async function manejarSalida(e) {
    e.preventDefault();
    if (!carrilSalidaId) {
      setErrorApi("No hay un carril de salida disponible en la base de datos.");
      return;
    }
    const placaLimpia =
      normalizarPlaca(placaInput) ||
      (operacion.placa !== "---" ? normalizarPlaca(operacion.placa) : "");
    if (!placaLimpia) {
      setErrorApi("Ingresa o detecta una placa válida para validar la salida.");
      return;
    }
    const { data } = await llamarApi("/accesos/salida", {
      placa: placaLimpia,
      carril_id: carrilSalidaId,
    });
    if (!data) return;

    const barreraAbierta = Boolean(data.barrera_abre);
    setMostrarManual(false);
    setPlacaInput(data.placa);
    setOperacion((prev) => ({
      ...prev,
      estado: barreraAbierta ? "BARRERA_ABIERTA" : "COBRO_PENDIENTE",
      placa: data.placa,
      tipoVehiculo: clasificarTipoVehiculo(data.placa),
      tipoMovimiento: "SALIDA",
      valorPagar: barreraAbierta
        ? 0
        : data.valor !== undefined && data.valor !== null
          ? Number(data.valor)
          : prev.valorPagar,
      cobroId: barreraAbierta ? null : (data.cobro_id ?? prev.cobroId),
      barreraAbierta,
      motivoBarrera: data.motivo,
    }));
  }

  function seleccionarCarrilEntrada(id) {
    setCarrilEntradaId(id);
    const entrada = carriles.find((carril) => carril.id === id);
    const salida = carriles.find(
      (carril) =>
        carril.sentido === "SALIDA" && carril.sede_id === entrada?.sede_id,
    );
    setCarrilSalidaId(salida?.id ?? "");
  }

  async function manejarPagoEfectivo(e) {
    e.preventDefault();
    if (!operacion.cobroId) {
      setErrorApi("No hay un cobro pendiente asociado para registrar pago.");
      return;
    }
    const { data } = await llamarApi("/pagos/efectivo", {
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

  const confianzaAlta =
    operacion.confianza !== null && operacion.confianza >= 0.85;

  return (
    <div className="operador-layout">
      <div className="page-heading">
        <div>
          <span className="eyebrow eyebrow-accent">OPERACIÓN EN VIVO</span>
          <h1>Panel del carril</h1>
          <p className="muted">
            Lectura automática de placas, validación directa y control de caja.
          </p>
        </div>
        <EstadoBadge estado={operacion.estado} />
      </div>

      {errorApi && (
        <Alert variant="error">
          <strong>Error de operación:</strong> {errorApi}
        </Alert>
      )}

      {operacion.estado === "LLENO" && (
        <Alert variant="error">
          <strong>LLENO:</strong> No se permiten nuevos ingresos. Las salidas
          continúan habilitadas.
        </Alert>
      )}

      {mostrarManual && (
        <section
          className="surface-card card-manual"
          aria-label="Validación manual"
        >
          <Alert variant="warning">
            <strong>Lectura con baja confianza:</strong> Verifica la placa física
            del vehículo antes de confirmar.
          </Alert>
          <div className="manual-split">
            <div className="manual-preview-box">
              <span className="eyebrow">LECTURA CAPTURADA</span>
              <div className="placa-display tabular-nums">
                {operacion.placa}
              </div>
              <div className="manual-meta-row">
                <span className="muted">Confianza detectada</span>
                <strong className="tabular-nums">
                  {operacion.confianza !== null
                    ? `${(operacion.confianza * 100).toFixed(1)} %`
                    : "-- %"}
                </strong>
              </div>
            </div>
            <form onSubmit={manejarLecturaManual} className="form-stack">
              <div className="surface-card-header" style={{ marginBottom: 0 }}>
                <div>
                  <h3>Confirmación de placa</h3>
                  <p className="muted">
                    Corrige o confirma los caracteres visibles en el carril.
                  </p>
                </div>
              </div>
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
              <div className="btn-group">
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => setMostrarManual(false)}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="button button-primary"
                  disabled={cargando}
                >
                  Confirmar placa manual
                </button>
              </div>
            </form>
          </div>
        </section>
      )}

      <div className="operator-hero-grid">
        <section
          className="surface-card lectura-card"
          aria-label="Última lectura"
        >
          <div className="lectura-header-row">
            <span className="eyebrow">ÚLTIMA LECTURA</span>
            <span className="muted" style={{ fontSize: "0.78rem" }}>
              {operacion.tipoMovimiento === "SALIDA"
                ? "Salida detectada"
                : operacion.tipoMovimiento === "ENTRADA"
                  ? "Entrada registrada"
                  : operacion.cobroId
                    ? "Cobro generado"
                    : "Monitoreo activo"}
            </span>
          </div>
          <div className="lectura-top">
            <div className="placa-display tabular-nums" data-testid="placa-leida">
              {operacion.placa}
            </div>
            <div className="confianza-box">
              <span className="eyebrow">CONFIANZA OCR</span>
              <strong
                className={`confianza-value tabular-nums ${
                  operacion.confianza === null
                    ? ""
                    : confianzaAlta
                      ? "is-high"
                      : "is-low"
                }`}
                data-testid="confianza-ocr"
              >
                {operacion.confianza !== null
                  ? `${(operacion.confianza * 100).toFixed(1)} %`
                  : "-- %"}
              </strong>
            </div>
          </div>

          <div className="lectura-detalles">
            <div className="lectura-metric">
              <span className="eyebrow">TIPO DE VEHÍCULO</span>
              <p data-testid="tipo-vehiculo">{operacion.tipoVehiculo}</p>
            </div>
            <div className="lectura-metric">
              <span className="eyebrow">ESTADO DE COBRO</span>
              <p>{operacion.cobroId ? "Pendiente" : "Sin cobro activo"}</p>
            </div>
            <div className="lectura-metric">
              <span className="eyebrow">VALOR A PAGAR</span>
              <p className="valor-cop tabular-nums" data-testid="valor-pagar">
                {formatearCOP(operacion.valorPagar)}
              </p>
            </div>
          </div>
        </section>

        <div className="operator-right-stack">
          <PanelBarrera
            abierta={operacion.barreraAbierta}
            motivo={operacion.motivoBarrera}
          />

          <section className="surface-card">
            <div className="surface-card-header" style={{ marginBottom: "0.75rem" }}>
              <div>
                <span className="eyebrow">CAJA · PAGO EN EFECTIVO</span>
                <h3>Liquidación de salida</h3>
              </div>
            </div>
            <div className="cash-total-banner">
              <span className="cash-total-label">Total a cobrar</span>
              <strong className="cash-total-amount tabular-nums">
                {formatearCOP(operacion.valorPagar)}
              </strong>
            </div>
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
                className="button button-primary button-full"
                disabled={cargando || !operacion.cobroId}
              >
                Confirmar pago en efectivo ({formatearCOP(operacion.valorPagar)})
              </button>
            </form>
          </section>
        </div>
      </div>

      <section className="surface-card">
        <div className="surface-card-header">
          <div>
            <span className="eyebrow">CONTROL DE CARRIL</span>
            <h3>Operación de entrada y salida</h3>
          </div>
        </div>
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
          {(errorCarriles || (!cargandoCarriles && carriles.length === 0)) && (
            <Alert variant="error">
              {errorCarriles || "No se encontraron carriles en la base de datos."}
            </Alert>
          )}
          <div className="form-row">
            <label>
              Carril de entrada
              <select
                aria-label="Carril de entrada"
                value={carrilEntradaId}
                onChange={(event) =>
                  seleccionarCarrilEntrada(event.target.value)
                }
                disabled={cargandoCarriles || !carrilesEntrada.length}
                required
              >
                <option value="">Selecciona carril de entrada</option>
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
                value={carrilSalidaId}
                onChange={(event) => setCarrilSalidaId(event.target.value)}
                disabled={cargandoCarriles || !carrilSalidaId}
                required
              >
                <option value="">Selecciona carril de salida</option>
                {carrilesSalida.map((carril) => (
                  <option key={carril.id} value={carril.id}>
                    {carril.sede_nombre} · {carril.id.slice(0, 8)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="image-upload-row">
            <label className="image-upload-button">
              <IconUpload />
              <span>
                {cargando ? "Procesando imagen..." : "Cargar imagen de placa"}
              </span>
              <input
                type="file"
                accept="image/jpeg,image/png,image/gif,image/webp"
                aria-label="Cargar imagen de placa"
                onChange={manejarSeleccionImagen}
                disabled={cargando || cargandoCarriles || !carrilEntradaId}
                hidden
              />
            </label>
            <span className="image-upload-hint">
              {imagenEntrada?.name
                ? `Imagen seleccionada: ${imagenEntrada.name}`
                : "Se procesa automáticamente al seleccionar la imagen: registra entrada o valida salida si la placa ya está dentro."}
            </span>
          </div>

          <span className="eyebrow divider-eyebrow">INGRESO Y SALIDA DIRECTA</span>
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
              className="button button-primary"
              disabled={cargando || !carrilEntradaId}
            >
              Registrar ingreso
            </button>
            <button
              type="button"
              className="button button-navy"
              disabled={cargando || !carrilSalidaId}
              onClick={manejarSalida}
            >
              Validar salida
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
