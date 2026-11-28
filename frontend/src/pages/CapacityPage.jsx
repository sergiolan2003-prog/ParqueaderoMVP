import { useEffect, useState } from "react";

import {
  getSiteCapacity,
  listSites,
  updateSiteCapacity,
} from "../api/capacityService.js";
import Alert from "../components/Alert.jsx";
import Field from "../components/Field.jsx";

export default function CapacityPage() {
  const [sedes, setSedes] = useState([]);
  const [sedeId, setSedeId] = useState("");
  const [cupos, setCupos] = useState({ cupos_carro: "", cupos_moto: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    let active = true;
    listSites()
      .then((items) => {
        if (active) {
          setSedes(items);
          setSedeId(items[0]?.id ?? "");
        }
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError.message);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!sedeId) {
      return undefined;
    }

    let active = true;
    setLoading(true);
    getSiteCapacity(sedeId)
      .then((site) => {
        if (active) {
          setCupos({
            cupos_carro: String(site.cupos_carro),
            cupos_moto: String(site.cupos_moto),
          });
          setError("");
        }
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError.message);
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [sedeId]);

  function updateValue(event) {
    setCupos((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  }

  async function submit(event) {
    event.preventDefault();
    setError("");
    setSuccess("");
    const payload = {
      cupos_carro: Number(cupos.cupos_carro),
      cupos_moto: Number(cupos.cupos_moto),
    };
    if (
      !Number.isInteger(payload.cupos_carro) ||
      !Number.isInteger(payload.cupos_moto) ||
      payload.cupos_carro < 0 ||
      payload.cupos_moto < 0
    ) {
      setError("Los cupos deben ser números enteros mayores o iguales a cero.");
      return;
    }

    setLoading(true);
    try {
      const updated = await updateSiteCapacity(sedeId, payload);
      setCupos({
        cupos_carro: String(updated.cupos_carro),
        cupos_moto: String(updated.cupos_moto),
      });
      setSuccess(`Cupos actualizados para ${updated.nombre}.`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  const selectedSite = sedes.find((site) => site.id === sedeId);
  const totalCupos =
    (Number(cupos.cupos_carro) || 0) + (Number(cupos.cupos_moto) || 0);

  return (
    <div className="page-content">
      {error && <Alert variant="error">{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      {sedes.length === 0 ? (
        <div className="surface-card">
          <Alert>No hay sedes disponibles para administrar.</Alert>
        </div>
      ) : (
        <div className="two-col-asymmetric">
          <section className="surface-card">
            <div className="surface-card-header">
              <div>
                <p className="eyebrow eyebrow-accent">Capacidad operativa</p>
                <h2>Cupos por sede</h2>
                <p className="muted">
                  Consulta y actualiza la capacidad disponible para cada tipo de
                  vehículo.
                </p>
              </div>
              {selectedSite && (
                <span className="status-badge badge-neutral">
                  {selectedSite.nombre}
                </span>
              )}
            </div>

            <div className="capacity-grid">
              <div className="metric-tile">
                <p className="metric-tile-label">Cupos carros</p>
                <p className="metric-tile-value tabular-nums">
                  {cupos.cupos_carro || 0}
                </p>
              </div>
              <div className="metric-tile">
                <p className="metric-tile-label">Cupos motos</p>
                <p className="metric-tile-value tabular-nums">
                  {cupos.cupos_moto || 0}
                </p>
              </div>
              <div className="metric-tile">
                <p className="metric-tile-label">Capacidad total</p>
                <p className="metric-tile-value tabular-nums">{totalCupos}</p>
              </div>
            </div>

            <form className="stack-form" onSubmit={submit}>
              <Field label="Sede" htmlFor="capacity-site">
                <select
                  id="capacity-site"
                  onChange={(event) => {
                    setSedeId(event.target.value);
                    setSuccess("");
                  }}
                  value={sedeId}
                >
                  {sedes.map((site) => (
                    <option key={site.id} value={site.id}>
                      {site.nombre}
                    </option>
                  ))}
                </select>
              </Field>

              <div className="form-grid">
                <Field label="Cupos para carros" htmlFor="capacity-cars">
                  <input
                    id="capacity-cars"
                    min="0"
                    name="cupos_carro"
                    onChange={updateValue}
                    required
                    step="1"
                    type="number"
                    value={cupos.cupos_carro}
                  />
                </Field>
                <Field label="Cupos para motos" htmlFor="capacity-motos">
                  <input
                    id="capacity-motos"
                    min="0"
                    name="cupos_moto"
                    onChange={updateValue}
                    required
                    step="1"
                    type="number"
                    value={cupos.cupos_moto}
                  />
                </Field>
              </div>

              <div className="form-actions">
                <button
                  className="button button-primary"
                  disabled={loading || !selectedSite}
                  type="submit"
                >
                  {loading ? "Guardando..." : "Guardar cupos"}
                </button>
              </div>
            </form>
          </section>

          <aside className="rules-card">
            <p className="eyebrow">Control de aforo</p>
            <h3>Comportamiento en carril</h3>
            <ul className="rules-list">
              <li>
                <span className="rules-bullet" aria-hidden="true" />
                <span>
                  Los ingresos de cada categoría se validan en tiempo real
                  contra el límite configurado.
                </span>
              </li>
              <li>
                <span className="rules-bullet" aria-hidden="true" />
                <span>
                  Cuando una sede alcanza su capacidad máxima, el panel de
                  operación activa el estado LLENO y bloquea nuevos ingresos.
                </span>
              </li>
            </ul>
          </aside>
        </div>
      )}
    </div>
  );
}
