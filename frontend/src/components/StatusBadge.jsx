const statusClass = {
  PENDIENTE: "badge-warning",
  PAGADO: "badge-success",
  VIGENTE: "badge-success",
  ANULADO: "badge-neutral",
  VENCIDO: "badge-danger",
};

export default function StatusBadge({ status }) {
  return (
    <span className={`status-badge ${statusClass[status] ?? "badge-neutral"}`}>
      <span className="status-badge-dot" aria-hidden="true" />
      {status}
    </span>
  );
}
