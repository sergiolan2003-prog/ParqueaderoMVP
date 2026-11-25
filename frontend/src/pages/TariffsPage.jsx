import { useEffect, useMemo, useState } from "react";

import { listSites } from "../api/capacityService.js";
import { createOrUpdateTariff, listTariffs } from "../api/tariffService.js";
import Alert from "../components/Alert.jsx";
import DataTable from "../components/DataTable.jsx";
import Field from "../components/Field.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

function localDate() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 10);
}

function dayAfter(value) {
  const result = new Date(`${value}T00:00:00.000Z`);
  result.setUTCDate(result.getUTCDate() + 1);
  return result.toISOString().slice(0, 10);
}

function emptyForm(sedeId = "") {
  return {
    sede_id: sedeId,
    tipo_vehiculo: "CARRO",
    franja: "DIURNA",
    valor: "",
    vigente_desde: localDate(),
    vigente_hasta: "",
  };
}

function formatCurrency(value) {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(Number(value));
}

export default function TariffsPage() {
  const [sedes, setSedes] = useState([]);
  const [tarifas, setTarifas] = useState([]);
  const [filters, setFilters] = useState({
    sede_id: "",
    tipo_vehiculo: "",
    franja: "",
  });
  const [form, setForm] = useState(() => emptyForm());
  const [isVersion, setIsVersion] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    let active = true;
    listSites()
      .then((items) => {
        if (active) {
          setSedes(items);
          setForm((current) => ({
            ...current,
            sede_id: current.sede_id || items[0]?.id || "",
          }));
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
    let active = true;
    setLoading(true);
    listTariffs(filters)
      .then((items) => {
        if (active) {
          setTarifas(items);
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
  }, [filters]);

  const sedeNames = useMemo(
    () => new Map(sedes.map((sede) => [sede.id, sede.nombre])),
    [sedes],
  );

  function updateForm(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  function updateFilter(event) {
    setFilters((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  }

  function startNewVersion(tarifa) {
    const earliestStart = dayAfter(tarifa.vigente_desde);
    const startDate = earliestStart > localDate() ? earliestStart : localDate();
    setForm({
      sede_id: tarifa.sede_id,
      tipo_vehiculo: tarifa.tipo_vehiculo,
      franja: tarifa.franja,
      valor: String(tarifa.valor),
      vigente_desde: startDate,
      vigente_hasta: "",
    });
    setIsVersion(true);
    setError("");
    setSuccess("");
  }

  async function submitTariff(event) {
    event.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);
    try {
      await createOrUpdateTariff({
        ...form,
        valor: form.valor,
        vigente_hasta: form.vigente_hasta || null,
      });
      setSuccess(
        isVersion
          ? "Nueva versión creada; el historial anterior se conservó."
          : "Tarifa creada correctamente.",
      );
      setIsVersion(false);
      setForm(emptyForm(form.sede_id));
      setTarifas(await listTariffs(filters));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  const columns = [
    {
      key: "sede_id",
      label: "Sede",
      render: (tarifa) => sedeNames.get(tarifa.sede_id) ?? tarifa.sede_id,
    },
    { key: "tipo_vehiculo", label: "Vehículo" },
    { key: "franja", label: "Franja" },
    { key: "valor", label: "Valor", render: (tarifa) => formatCurrency(tarifa.valor) },
    { key: "vigente_desde", label: "Desde" },
    {
      key: "vigente_hasta",
      label: "Vigencia",
      render: (tarifa) =>
        tarifa.vigente_hasta ? (
          tarifa.vigente_hasta
        ) : (
          <StatusBadge status="VIGENTE" />
        ),
    },
    {
      key: "action",
      label: "Acción",
      render: (tarifa) =>
        tarifa.vigente_hasta ? (
          <span className="muted">Historial</span>
        ) : (
          <button
            className="button button-small button-secondary"
            onClick={() => startNewVersion(tarifa)}
            type="button"
          >
            Nueva versión
          </button>
        ),
    },
  ];

  return (
    <div className="page-content">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Reglas de cobro</p>
          <h2>Tarifas</h2>
          <p className="muted">
            Cada cambio genera una versión nueva y conserva la vigencia anterior.
          </p>
        </div>
      </div>

      {error && <Alert variant="error">{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      <section className="subsection" aria-labelledby="tariff-form-title">
        <h3 id="tariff-form-title">
          {isVersion ? "Crear nueva versión" : "Registrar tarifa"}
        </h3>
        <form className="form-grid" onSubmit={submitTariff}>
          <Field label="Sede" htmlFor="tariff-site">
            <select
              id="tariff-site"
              name="sede_id"
              onChange={updateForm}
              required
              value={form.sede_id}
            >
              <option value="">Selecciona una sede</option>
              {sedes.map((sede) => (
                <option key={sede.id} value={sede.id}>
                  {sede.nombre}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Tipo de vehículo" htmlFor="tariff-vehicle">
            <select
              id="tariff-vehicle"
              name="tipo_vehiculo"
              onChange={updateForm}
              value={form.tipo_vehiculo}
            >
              <option value="CARRO">Carro</option>
              <option value="MOTO">Moto</option>
            </select>
          </Field>
          <Field label="Franja" htmlFor="tariff-band">
            <select
              id="tariff-band"
              name="franja"
              onChange={updateForm}
              value={form.franja}
            >
              <option value="DIURNA">Diurna</option>
              <option value="NOCTURNA">Nocturna</option>
            </select>
          </Field>
          <Field label="Valor (COP)" htmlFor="tariff-value">
            <input
              id="tariff-value"
              min="0"
              name="valor"
              onChange={updateForm}
              required
              step="0.01"
              type="number"
              value={form.valor}
            />
          </Field>
          <Field label="Vigente desde" htmlFor="tariff-start">
            <input
              id="tariff-start"
              name="vigente_desde"
              onChange={updateForm}
              required
              type="date"
              value={form.vigente_desde}
            />
          </Field>
          <Field label="Vigente hasta (opcional)" htmlFor="tariff-end">
            <input
              id="tariff-end"
              name="vigente_hasta"
              onChange={updateForm}
              type="date"
              value={form.vigente_hasta}
            />
          </Field>
          <div className="form-actions">
            <button
              className="button button-primary"
              disabled={loading || sedes.length === 0}
              type="submit"
            >
              {loading ? "Guardando..." : isVersion ? "Guardar versión" : "Crear tarifa"}
            </button>
            {isVersion && (
              <button
                className="button button-quiet"
                onClick={() => {
                  setIsVersion(false);
                  setForm(emptyForm(form.sede_id));
                }}
                type="button"
              >
                Cancelar edición
              </button>
            )}
          </div>
        </form>
      </section>

      <section className="subsection" aria-labelledby="tariff-list-title">
        <div className="section-heading">
          <div>
            <h3 id="tariff-list-title">Historial de tarifas</h3>
            <p className="muted">Filtra las tarifas por sede, vehículo o franja.</p>
          </div>
        </div>
        <div className="filter-grid">
          <Field label="Sede" htmlFor="filter-site">
            <select
              id="filter-site"
              name="sede_id"
              onChange={updateFilter}
              value={filters.sede_id}
            >
              <option value="">Todas las sedes</option>
              {sedes.map((sede) => (
                <option key={sede.id} value={sede.id}>
                  {sede.nombre}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Vehículo" htmlFor="filter-vehicle">
            <select
              id="filter-vehicle"
              name="tipo_vehiculo"
              onChange={updateFilter}
              value={filters.tipo_vehiculo}
            >
              <option value="">Todos</option>
              <option value="CARRO">Carro</option>
              <option value="MOTO">Moto</option>
            </select>
          </Field>
          <Field label="Franja" htmlFor="filter-band">
            <select
              id="filter-band"
              name="franja"
              onChange={updateFilter}
              value={filters.franja}
            >
              <option value="">Todas</option>
              <option value="DIURNA">Diurna</option>
              <option value="NOCTURNA">Nocturna</option>
            </select>
          </Field>
        </div>
        <DataTable
          columns={columns}
          emptyMessage={loading ? "Cargando tarifas..." : undefined}
          rows={tarifas}
        />
      </section>
    </div>
  );
}
