import { useEffect, useState } from "react";

import { registerEntryByImage } from "../api/accessService.js";
import { listCarriles } from "../api/carrilService.js";
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
    const tokenCarriles = accessToken || token.trim();
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
    if (!carrilEntradaId) {
      setErrorApi("No hay un carril de entrada disponible en la base de datos.");
      return;
    }
    const confianza = Number(confianzaInput);
    const data = await llamarApi("/accesos/entrada/simulada", {
      carril_id: carrilEntradaId,
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
        const coincidencia = imagen.name.match(
          /^([A-Za-z0-9]+)_([0-9]+(?:\.[0-9]+)?)\.[A-Za-z0-9]+$/,
        );
        setPlacaInput(coincidencia?.[1]?.toUpperCase() ?? "");
        setMostrarManual(true);
        setOperacion((prev) => ({
          ...prev,
          estado: "BAJA_CONFIANZA",
          placa:
            coincidencia?.[1]?.toUpperCase() ||
            prev.placa,
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
    const placaLimpia = placaInput.trim().toUpperCase();
    const data = await llamarApi("/accesos/entrada", {
      evento_id: crypto.randomUUID(),
      placa: placaLimpia,
      carril_id: carrilEntradaId,
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
    if (!carrilSalidaId) {
      setErrorApi("No hay un carril de salida disponible en la base de datos.");
      return;
    }
    const placaLimpia = placaInput.trim().toUpperCase() || operacion.placa;
    const data = await llamarApi("/accesos/salida", {
      placa: placaLimpia,
      carril_id: carrilSalidaId,
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
            {(errorCarriles || (!cargandoCarriles && carriles.length === 0)) && (
              <div className="alerta-error" role="alert">
                {errorCarriles || "No se encontraron carriles en la base de datos."}
              </div>
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
                <span>{cargando ? "Procesando imagen..." : "Cargar imagen de placa"}</span>
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
                  : "La lectura se procesa automáticamente al seleccionar una imagen."}
              </span>
            </div>
            <span className="eyebrow">SIMULACIÓN DE PRUEBA</span>
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
                disabled={cargando || !carrilEntradaId}
              >
                Registrar ingreso simulado
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