import type { Region, RuleOptions } from "../types";

export default function AssetStyleControls({
  field,
  options,
  onChange,
}: {
  field: Region;
  options: RuleOptions;
  onChange: (patch: Partial<Region>) => void;
}) {
  const set = (patch: Partial<RuleOptions>) =>
    onChange({
      rule_options: { ...options, ...patch },
      confirmed: false,
      rule: "",
      rule_resolved_hash: "",
    });
  return (
    <details className="font-controls">
      <summary>Rendering style and cleanup</summary>
      <label>
        Remove original content
        <select
          value={options.cleanup_mode || "full_region"}
          onChange={(e) =>
            set({ cleanup_mode: e.target.value as RuleOptions["cleanup_mode"] })
          }
        >
          <option value="full_region">Restore entire selected region</option>
          <option value="ink_only">
            Remove detected ink only (inspect for remnants)
          </option>
        </select>
      </label>
      <p className="field-hint">
        Include all original strokes in the box. Full restoration removes the
        selected pixels before replacement, including old seals. Textured
        backgrounds are reconstructed approximately.
      </p>
      {!["signature", "seal", "qr", "barcode", "portrait"].includes(
        field.kind,
      ) && (
        <label>
          Writing style
          <select
            value={options.writing_style || "printed"}
            onChange={(e) =>
              set({
                writing_style: e.target.value as RuleOptions["writing_style"],
              })
            }
          >
            <option value="printed">Printed / match source</option>
            <option value="cursive">English cursive font</option>
          </select>
        </label>
      )}
      {["qr", "barcode"].includes(field.kind) && (
        <>
          <label>
            Code background
            <select
              value={options.code_background || "transparent"}
              onChange={(e) =>
                set({
                  code_background: e.target
                    .value as RuleOptions["code_background"],
                })
              }
            >
              <option value="transparent">
                Transparent (template shows through)
              </option>
              <option value="white">White</option>
            </select>
          </label>
          <p className="field-hint">
            Transparent light modules preserve the template. Dark or textured
            backgrounds can reduce code readability; verify scans.
          </p>
        </>
      )}
      {field.kind === "signature" && (
        <>
          <label>
            Signature style
            <select
              value={options.signature_style || "flourish"}
              onChange={(e) =>
                set({
                  signature_style: e.target
                    .value as RuleOptions["signature_style"],
                })
              }
            >
              <option value="name">Fictional name in cursive</option>
              <option value="initials">Fictional initials</option>
              <option value="flourish">Name with overlaid flourishes</option>
            </select>
          </label>
          <p className="field-hint">
            Uses the generated person's name and installed script fonts; does
            not copy a source signature. A literal replacement can supply
            fictional signing text.
          </p>
        </>
      )}
      {field.kind === "seal" && (
        <>
          <label>
            Seal shape
            <select
              value={options.seal_style || "random"}
              onChange={(e) =>
                set({ seal_style: e.target.value as RuleOptions["seal_style"] })
              }
            >
              {["random", "ring", "round", "rectangle", "text"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <label>
            Seal ink
            <select
              value={options.seal_color || "random"}
              onChange={(e) =>
                set({ seal_color: e.target.value as RuleOptions["seal_color"] })
              }
            >
              {["random", "red", "blue", "green", "mixed"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <label>
            Seal main text
            <input
              maxLength={60}
              value={options.seal_text ?? "SAMPLE OFFICE"}
              onChange={(e) => set({ seal_text: e.target.value })}
            />
          </label>
          <label>
            Seal inner text
            <input
              maxLength={40}
              value={options.seal_subtext ?? "RECEIVED"}
              onChange={(e) => set({ seal_subtext: e.target.value })}
            />
          </label>
          <label>
            Ink wear
            <input
              type="number"
              min={0}
              max={0.45}
              step={0.01}
              value={options.seal_wear ?? 0.08}
              onChange={(e) => set({ seal_wear: Number(e.target.value) })}
            />
          </label>
        </>
      )}
    </details>
  );
}
