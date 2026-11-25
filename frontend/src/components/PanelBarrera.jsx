export function PanelBarrera({ abierta, motivo }) {
  return (
    <section
      className={`panel-barrera ${abierta ? "barrera-abierta" : "barrera-cerrada"}`}
      aria-label="Control de barrera"
    >
      <span className="eyebrow">CONTROL DE BARRERA</span>
      <h2 className="barrera-titulo">
        {abierta ? "✓ ABIERTA" : "✕ BARRERA CERRADA"}
      </h2>
      <p className="barrera-motivo">{motivo}</p>
    </section>
  );
}