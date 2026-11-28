import { useEffect, useState } from "react";

import {
  getOperationalConfiguration,
  updateOperationalConfiguration,
} from "../api/configurationService.js";
import Alert from "../components/Alert.jsx";
import Field from "../components/Field.jsx";

function formatTime(value) {
  return value?.slice(0, 5) ?? "";
}

function formatConfiguration(configuration) {
  return {
    daytime_start: formatTime(configuration.daytime_start),
    daytime_end: formatTime(configuration.daytime_end),
    nighttime_start: formatTime(configuration.nighttime_start),
    nighttime_end: formatTime(configuration.nighttime_end),
    lpr_confidence_threshold: String(
      configuration.lpr_confidence_threshold,
    ),
  };
}

export default function ConfigurationPage() {
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    let active = true;
    getOperationalConfiguration()
      .then((configuration) => {
        if (active) {
          setForm(formatConfiguration(configuration));
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
  }, []);

  function updateField(event) {
    setForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
    setError("");
    setSuccess("");
  }

  async function saveConfiguration(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const saved = await updateOperationalConfiguration({
        ...form,
        lpr_confidence_threshold: Number(form.lpr_confidence_threshold),
      });
      setForm(formatConfiguration(saved));
      setSuccess("Configuración operativa actualizada correctamente.");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="surface-card">
        <p role="status" className="muted" style={{ margin: 0 }}>
          Cargando configuración operativa...
        </p>
      </div>
    );
  }

  return (
    <div className="page-content">
      <div className="section-heading">
        <div>
          <p className="eyebrow eyebrow-accent">Parámetros globales</p>
          <h2 id="configuration-heading">Configuración operativa</h2>
          <p className="muted">
            Define los horarios de las franjas y la confianza mínima para
            lecturas automáticas de placas.
          </p>
        </div>
        <span className="status-badge badge-warning">Parámetros del sistema</span>
      </div>

      {error && <Alert variant="error">{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      {form && (
        <form className="page-content" onSubmit={saveConfiguration}>
          <div className="two-col-asymmetric">
            <section className="surface-card">
              <div className="surface-card-header">
                <div>
                  <h3>Franjas horarias</h3>
                  <p className="muted">
                    Las franjas deben cubrir el día completo, sin cruces ni
                    espacios.
                  </p>
                </div>
              </div>

              <div className="form-grid" style={{ marginBottom: "1.5rem" }}>
                <Field htmlFor="daytime-start" label="Inicio de franja diurna">
                  <input
                    id="daytime-start"
                    name="daytime_start"
                    onChange={updateField}
                    required
                    type="time"
                    value={form.daytime_start}
                  />
                </Field>
                <Field htmlFor="daytime-end" label="Fin de franja diurna">
                  <input
                    id="daytime-end"
                    name="daytime_end"
                    onChange={updateField}
                    required
                    type="time"
                    value={form.daytime_end}
                  />
                </Field>
                <Field
                  htmlFor="nighttime-start"
                  label="Inicio de franja nocturna"
                >
                  <input
                    id="nighttime-start"
                    name="nighttime_start"
                    onChange={updateField}
                    required
                    type="time"
                    value={form.nighttime_start}
                  />
                </Field>
                <Field htmlFor="nighttime-end" label="Fin de franja nocturna">
                  <input
                    id="nighttime-end"
                    name="nighttime_end"
                    onChange={updateField}
                    required
                    type="time"
                    value={form.nighttime_end}
                  />
                </Field>
              </div>

              <div
                style={{
                  paddingTop: "1.25rem",
                  borderTop: "1px solid var(--color-border)",
                }}
              >
                <div className="surface-card-header">
                  <div>
                    <h3>Reconocimiento de placas (LPR)</h3>
                    <p className="muted">
                      Controla el umbral mínimo para autorizar la lectura
                      automática sin intervención manual.
                    </p>
                  </div>
                </div>
                <div className="form-grid">
                  <Field
                    hint="Valor entre 0 y 1; por ejemplo, 0.8 equivale al 80%."
                    htmlFor="lpr-confidence-threshold"
                    label="Umbral de confianza LPR"
                  >
                    <input
                      id="lpr-confidence-threshold"
                      max="1"
                      min="0"
                      name="lpr_confidence_threshold"
                      onChange={updateField}
                      required
                      step="0.01"
                      type="number"
                      value={form.lpr_confidence_threshold}
                    />
                  </Field>
                </div>
              </div>
            </section>

            <aside className="side-stack">
              <div className="rules-card">
                <p className="eyebrow">Criterios de validación</p>
                <h3>Reglas operativas</h3>
                <ul className="rules-list">
                  <li>
                    <span className="rules-bullet" aria-hidden="true" />
                    <span>
                      El fin de la franja diurna debe coincidir con el inicio de
                      la franja nocturna.
                    </span>
                  </li>
                  <li>
                    <span className="rules-bullet" aria-hidden="true" />
                    <span>
                      Lecturas con confianza inferior al umbral LPR solicitan
                      confirmación manual en el carril.
                    </span>
                  </li>
                  <li>
                    <span className="rules-bullet" aria-hidden="true" />
                    <span>
                      Los cambios aplican inmediatamente a los nuevos eventos
                      registrados.
                    </span>
                  </li>
                </ul>
              </div>
            </aside>
          </div>

          <div className="action-footer-card">
            <p className="action-footer-note">
              Verifica que las franjas cubran las 24 horas antes de guardar los
              cambios.
            </p>
            <button
              className="button button-primary"
              disabled={saving}
              type="submit"
            >
              {saving ? "Guardando..." : "Guardar configuración"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
