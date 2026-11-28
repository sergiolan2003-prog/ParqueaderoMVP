import { IconCheckCircle, IconXCircle } from "./Icons.jsx";

export function PanelBarrera({ abierta, motivo }) {
  return (
    <section
      className={`panel-barrera ${abierta ? "barrera-abierta" : "barrera-cerrada"}`}
      aria-label="Control de barrera"
    >
      <span className="eyebrow">CONTROL DE BARRERA</span>
      <h2 className="barrera-titulo">
        {abierta ? <IconCheckCircle size={22} /> : <IconXCircle size={22} />}
        <span>{abierta ? "✓ ABIERTA" : "✕ BARRERA CERRADA"}</span>
      </h2>
      <p className="barrera-motivo">{motivo}</p>
    </section>
  );
}
