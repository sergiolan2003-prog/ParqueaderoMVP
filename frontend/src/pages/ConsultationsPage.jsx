import { useState } from "react";

import {
  listAccessEvents,
  listCharges,
} from "../api/consultationService.js";
import Alert from "../components/Alert.jsx";
import DataTable from "../components/DataTable.jsx";
import Field from "../components/Field.jsx";
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
          { key: "placa", label: "Placa" },
          { key: "carril_id", label: "Carril" },
          {
            key: "ocurrido_en",
            label: "Fecha y hora",
            render: (event) => formatInstant(event.ocurrido_en),
          },
          {
            key: "confianza_lpr",
            label: "Confianza",
            render: (event) => `${(event.confianza_lpr * 100).toFixed(1)}%`,
          },
          {
            key: "lectura_manual",
            label: "Lectura",
            render: (event) => (event.lectura_manual ? "Manual" : "Automática"),
          },
        ]
      : [
          { key: "placa", label: "Placa" },
          { key: "sede_id", label: "Sede" },
          { key: "dia_operativo", label: "Día operativo" },
          {
            key: "valor",
            label: "Valor",
            render: (charge) => formatCurrency(charge.valor),
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
          <p className="eyebrow">Actividad del parqueadero</p>
          <h2>Consultas</h2>
          <p className="muted">
            Busca eventos de acceso y cobros por placa, fechas y estado.
          </p>
        </div>
      </div>

      {error && <Alert variant="error">{error}</Alert>}

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

      <form
        className="filter-grid consultation-filters"
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
          <button className="button button-primary" disabled={loading} type="submit">
            {loading ? "Buscando..." : "Buscar"}
          </button>
        </div>
      </form>

      <DataTable
        columns={columns}
        emptyMessage={
          result ? "No se encontraron resultados." : "Aplica filtros para consultar."
        }
        rows={result?.items ?? []}
      />
      {result && (
        <div className="pagination">
          <span className="muted">
            {result.total} resultados · Página {page} de{" "}
            {Math.max(result.total_pages, 1)}
          </span>
          <div className="pagination-actions">
            <button
              className="button button-quiet"
              disabled={loading || page <= 1}
              onClick={() => search(page - 1)}
              type="button"
            >
              Anterior
            </button>
            <button
              className="button button-quiet"
              disabled={loading || page >= result.total_pages}
              onClick={() => search(page + 1)}
              type="button"
            >
              Siguiente
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
