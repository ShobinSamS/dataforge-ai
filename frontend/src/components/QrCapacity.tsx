import { useEffect, useState } from "react";
import { api } from "../api";
import type { Config, Template } from "../types";

export interface QrPreflight {
  valid: boolean;
  errors: string[];
  qr_regions: {
    region_id: string;
    label: string;
    width: number;
    height: number;
    payload_characters: number;
    payload_source: string;
    required_size: number | null;
    max_automatic_characters: number | null;
    fits: boolean;
    error: string;
  }[];
}
export default function QrCapacity({
  config,
  template,
  onEdit,
  onState,
}: {
  config: Config;
  template: Template;
  onEdit?: (id: string) => void;
  onState?: (state: "checking" | "valid" | "invalid") => void;
}) {
  const [report, setReport] = useState<QrPreflight | null>(null),
    [error, setError] = useState("");
  const request = JSON.stringify({
    template_id: template.id,
    qr_codes: config.qr_codes,
    qr_required: config.qr_required ?? false,
    qr_payload_length: config.qr_payload_length ?? 10,
    qr_padding: config.qr_padding ?? 0,
  });
  useEffect(() => {
    setReport(null);
    setError("");
    if (!config.qr_codes && !config.qr_required) {
      onState?.("valid");
      return;
    }
    onState?.("checking");
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const value = await api<QrPreflight>("/jobs/preflight", {
          method: "POST",
          body: request,
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        setReport(value);
        onState?.(value.valid ? "valid" : "invalid");
      } catch (e) {
        if (!controller.signal.aborted) {
          setError(e instanceof Error ? e.message : "QR size check failed");
          onState?.("invalid");
        }
      }
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [request, template.revision, onState]);
  if (!config.qr_codes && !config.qr_required) return null;
  return (
    <div className="qr-capacity" aria-live="polite">
      <h4>QR size check</h4>
      {!report && !error && (
        <p className="field-hint">Checking saved QR regions…</p>
      )}
      {error && (
        <p className="inline-error" role="alert">
          {error}
        </p>
      )}
      {report && (
        <>
          {report.qr_regions.length === 0 && (
            <p className="field-hint">No saved QR replacement regions.</p>
          )}
          {report.qr_regions.map((r) => (
            <div
              key={r.region_id}
              className={
                r.fits ? "qr-capacity-item" : "qr-capacity-item invalid"
              }
            >
              <strong>{r.label}</strong>
              <p>
                Effective payload: {r.payload_characters} characters ·{" "}
                {r.payload_source}.
              </p>
              <p>
                Saved region: {r.width} × {r.height} px · Required:{" "}
                {r.required_size === null
                  ? "payload too large"
                  : `${r.required_size} × ${r.required_size} px`}
                .
              </p>
              {r.payload_source === "field length override" && (
                <p>
                  The field length overrides “QR payload characters” above.
                  Change or clear it in Template editor.
                </p>
              )}
              {!r.fits && r.max_automatic_characters !== null && (
                <p>
                  This box supports at most {r.max_automatic_characters}{" "}
                  characters with the current character set and padding.
                </p>
              )}
              {onEdit && (
                <button
                  type="button"
                  className="text-button"
                  onClick={() => onEdit(r.region_id)}
                >
                  Edit this QR field
                </button>
              )}
            </div>
          ))}
          {!report.valid && (
            <p className="inline-error" role="alert">
              Fix the QR size/payload before generating.{" "}
              {report.errors.length && !report.qr_regions.length
                ? report.errors.join(" ")
                : ""}
            </p>
          )}
          <p className="field-hint">
            Size is measured in pixels; payload length is measured in
            characters. Padding also needs space. Capacity checks do not
            guarantee scanning after blur or on textured backgrounds.
          </p>
        </>
      )}
    </div>
  );
}
