const CONFIG_ESTADOS = {
  ESPERANDO: { label: "Esperando vehículo", clase: "badge-neutral" },
  COBRO_PENDIENTE: { label: "Cobro pendiente", clase: "badge-danger" },
  PAGADO: { label: "Pagado", clase: "badge-success" },
  BARRERA_ABIERTA: { label: "Barrera abierta", clase: "badge-success" },
  LLENO: { label: "LLENO", clase: "badge-danger-solid" },
  BAJA_CONFIANZA: { label: "Lectura con baja confianza", clase: "badge-warning" },
};

export function EstadoBadge({ estado }) {
  const config = CONFIG_ESTADOS[estado] || CONFIG_ESTADOS.ESPERANDO;
  return (
    <span className={`estado-badge ${config.clase}`} data-testid="estado-badge">
      <span className="status-badge-dot" aria-hidden="true" />
      {config.label}
    </span>
  );
}
