import { useState } from "react";

import {
  listAccessEvents,
  listCharges,
} from "../api/consultationService.js";
import Alert from "../components/Alert.jsx";
import DataTable from "../components/DataTable.jsx";
import Field from "../components/Field.jsx";
import { IconSearch } from "../components/Icons.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

const pageSize = 10;

function formatInstant(value) {
  return new Intl.DateTimeFormat("es-CO", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatCurrency(value) {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(Number(value));
}

export default function ConsultationsPage() {
  const [kind, setKind] = useState("eventos");
  const [filters, setFilters] = useState({
    placa: "",
    desde: "",
    hasta: "",
    estado: "",
  });
  const [result, setResult] = useState(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function updateFilter(event) {
    const value =
      event.target.name === "placa"
        ? event.target.value.toUpperCase()
        : event.target.value;
    setFilters((current) => ({ ...current, [event.target.name]: value }));
  }

  function resetFilters() {
    setFilters({ placa: "", desde: "", hasta: "", estado: "" });
    setResult(null);
    setPage(1);
    setError("");
  }

  async function search(targetPage = 1) {
    setLoading(true);
    setError("");
    try {
      const query = {
        ...filters,
        page: targetPage,
        page_size: pageSize,
      };
      delete query.estado;
      const response =
        kind === "eventos"
          ? await listAccessEvents(query)
          : await listCharges({ ...query, estado: filters.estado });
      setResult(response);
      setPage(targetPage);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  const columns =
    kind === "eventos"
      ? [
          {
            key: "placa",
            label: "Placa",
            render: (event) => (
              <strong className="tabular-nums">{event.placa}</strong>
            ),
          },
          { key: "carril_id", label: "Carril" },
          {
            key: "ocurrido_en",
            label: "Fecha y hora",
            render: (event) => (
              <span className="tabular-nums">
                {formatInstant(event.ocurrido_en)}
              </span>
            ),
          },
          {
            key: "confianza_lpr",
            label: "Confianza",
            render: (event) => (
              <span className="tabular-nums">
                {(event.confianza_lpr * 100).toFixed(1)}%
              </span>
            ),
          },
          {
            key: "lectura_manual",
            label: "Lectura",
            render: (event) => (
              <span
                className={`status-badge ${
                  event.lectura_manual ? "badge-warning" : "badge-success"
                }`}
              >
                <span className="status-badge-dot" aria-hidden="true" />
                {event.lectura_manual ? "Manual" : "Automática"}
              </span>
            ),
          },
        ]
      : [
          {
            key: "placa",
            label: "Placa",
            render: (charge) => (
              <strong className="tabular-nums">{charge.placa}</strong>
            ),
          },
          { key: "sede_id", label: "Sede" },
          {
            key: "dia_operativo",
            label: "Día operativo",
            render: (charge) => (
              <span className="tabular-nums">{charge.dia_operativo}</span>
            ),
          },
          {
            key: "valor",
            label: "Valor",
            render: (charge) => (
              <strong className="tabular-nums">
                {formatCurrency(charge.valor)}
              </strong>
            ),
          },
          {
            key: "estado",
            label: "Estado",
            render: (charge) => <StatusBadge status={charge.estado} />,
          },
        ];

  return (
    <div className="page-content">
      <div className="section-heading">
        <div>
          <p className="eyebrow eyebrow-accent">Actividad del parqueadero</p>
          <h2>Consultas</h2>
          <p className="muted">
            Busca eventos de acceso y cobros por placa, fechas y estado.
          </p>
        </div>

        <div className="query-switch" aria-label="Tipo de consulta">
          <button
            aria-pressed={kind === "eventos"}
            className="button button-secondary"
            onClick={() => {
              setKind("eventos");
              setResult(null);
              setPage(1);
            }}
            type="button"
          >
            Eventos de acceso
          </button>
          <button
            aria-pressed={kind === "cobros"}
            className="button button-secondary"
            onClick={() => {
              setKind("cobros");
              setResult(null);
              setPage(1);
            }}
            type="button"
          >
            Cobros
          </button>
        </div>
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      <section className="surface-card">
        <form
          className="filter-grid filter-grid-consultations"
          onSubmit={(event) => {
            event.preventDefault();
            search(1);
          }}
        >
          <Field label="Placa" htmlFor="query-plate">
            <input
              id="query-plate"
              name="placa"
              onChange={updateFilter}
              placeholder="ABC123"
              value={filters.placa}
            />
          </Field>
          <Field label="Desde" htmlFor="query-from">
            <input
              id="query-from"
              name="desde"
              onChange={updateFilter}
              type="date"
              value={filters.desde}
            />
          </Field>
          <Field label="Hasta" htmlFor="query-to">
            <input
              id="query-to"
              name="hasta"
              onChange={updateFilter}
              type="date"
              value={filters.hasta}
            />
          </Field>
          {kind === "cobros" && (
            <Field label="Estado" htmlFor="query-state">
              <select
                id="query-state"
                name="estado"
                onChange={updateFilter}
                value={filters.estado}
              >
                <option value="">Todos</option>
                <option value="PENDIENTE">Pendiente</option>
                <option value="PAGADO">Pagado</option>
                <option value="ANULADO">Anulado</option>
                <option value="VENCIDO">Vencido</option>
              </select>
            </Field>
          )}
          <div className="form-actions">
            <button
              className="button button-primary"
              disabled={loading}
              type="submit"
            >
              <IconSearch />
              {loading ? "Buscando..." : "Buscar"}
            </button>
            <button
              className="button button-quiet"
              disabled={loading}
              onClick={resetFilters}
              type="button"
            >
              Limpiar
            </button>
          </div>
        </form>
      </section>

      <section className="surface-card">
        <div className="surface-card-header">
          <div>
            <h3>
              {kind === "eventos"
                ? "Registro de eventos de acceso"
                : "Detalle de cobros"}
            </h3>
            <p className="muted">
              {result
                ? `Mostrando ${result.items?.length ?? 0} registros en esta página`
                : "Aplica los filtros superiores para consultar los registros."}
            </p>
          </div>
          {result && (
            <span className="status-badge badge-neutral tabular-nums">
              Total: {result.total}
            </span>
          )}
        </div>

        <DataTable
          columns={columns}
          emptyMessage={
            result
              ? "No se encontraron resultados."
              : "Aplica filtros para consultar."
          }
          rows={result?.items ?? []}
        />

        {result && (
          <div className="pagination">
            <span className="muted tabular-nums">
              {result.total} resultados · Página {page} de{" "}
              {Math.max(result.total_pages, 1)}
            </span>
            <div className="pagination-actions">
              <button
                className="button button-secondary button-small"
                disabled={loading || page <= 1}
                onClick={() => search(page - 1)}
                type="button"
              >
                Anterior
              </button>
              <span className="page-pill-active tabular-nums">{page}</span>
              <button
                className="button button-secondary button-small"
                disabled={loading || page >= result.total_pages}
                onClick={() => search(page + 1)}
                type="button"
              >
                Siguiente
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
