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

  return (
    <div className="page-content">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Capacidad operativa</p>
          <h2>Cupos por sede</h2>
          <p className="muted">
            Consulta y actualiza la capacidad disponible para cada tipo de vehículo.
          </p>
        </div>
      </div>

      {error && <Alert variant="error">{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      {sedes.length === 0 ? (
        <Alert>No hay sedes disponibles para administrar.</Alert>
      ) : (
        <section className="subsection">
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

          <form className="form-grid capacity-form" onSubmit={submit}>
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
      )}
    </div>
  );
}
