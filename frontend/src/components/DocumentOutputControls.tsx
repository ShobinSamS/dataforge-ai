import type { Config, Template } from "../types";
import QrCapacity from "./QrCapacity";

export default function DocumentOutputControls({
  config,
  onChange,
  template,
  onEditQr,
  onPreflight,
}: {
  config: Config;
  onChange: (patch: Partial<Config>) => void;
  template?: Template;
  onEditQr?: (id: string) => void;
  onPreflight?: (state: "checking" | "valid" | "invalid") => void;
}) {
  return (
    <div className="document-output-controls">
      <h3>Generated content</h3>
      <div className="form-columns">
        <label>
          Default identifier length
          <input
            type="number"
            min={1}
            max={128}
            value={config.identifier_length ?? 10}
            onChange={(e) =>
              onChange({ identifier_length: Number(e.target.value) })
            }
          />
          <small>Used when a field has no pattern or length override.</small>
        </label>
        <label>
          QR payload characters
          <input
            type="number"
            min={1}
            max={500}
            disabled={!config.qr_codes}
            value={config.qr_payload_length ?? 10}
            aria-label="QR payload characters"
            onChange={(e) =>
              onChange({ qr_payload_length: Number(e.target.value) })
            }
          />
          <small>
            1–500 characters generated automatically. A pattern is optional.
          </small>
        </label>
        <label>
          QR padding (modules)
          <input
            type="number"
            min={0}
            max={8}
            disabled={!config.qr_codes}
            value={config.qr_padding ?? 0}
            onChange={(e) => onChange({ qr_padding: Number(e.target.value) })}
          />
          <small>
            0 removes the visible border. Scanning depends on surrounding clear
            space.
          </small>
        </label>
      </div>
      <label className="check-label">
        <input
          type="checkbox"
          disabled={!config.qr_codes}
          checked={config.qr_required ?? false}
          onChange={(e) => onChange({ qr_required: e.target.checked })}
        />
        Require a reviewed QR replacement region
      </label>
      <p className="field-hint">
        Field patterns and character lengths override these defaults. Generated
        content has no SYN- prefix or portrait caption; provenance stays in
        dataset metadata.
      </p>
      {template && (
        <QrCapacity
          config={config}
          template={template}
          onEdit={onEditQr}
          onState={onPreflight}
        />
      )}
    </div>
  );
}
