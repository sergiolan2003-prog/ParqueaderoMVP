const statusClass = {
  PENDIENTE: "badge-warning",
  PAGADO: "badge-success",
  ANULADO: "badge-neutral",
  VENCIDO: "badge-danger",
};

export default function StatusBadge({ status }) {
  return (
    <span className={`status-badge ${statusClass[status] ?? "badge-neutral"}`}>
      {status}
    </span>
  );
}
