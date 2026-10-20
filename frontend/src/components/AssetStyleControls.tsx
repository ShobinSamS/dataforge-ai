import type { Region, RuleOptions } from "../types";
import SealControls from "./SealControls";
import InkOpacityControls from "./InkOpacityControls";
import StampControls from "./StampControls";
import ColorControls from "./ColorControls";

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
      rule_options: {
        ...options,
        ...(["signature", "stamp", "rubber_stamp"].includes(field.kind) &&
        field.rule?.startsWith("literal:")
          ? { literal_text: field.rule.slice(8) }
          : {}),
        ...patch,
      },
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
      {[
        "signature",
        "seal",
        "portrait",
        "stamp",
        "rubber_stamp",
        "drawing",
      ].includes(field.kind) && (
        <>
          <label>
            Element background
            <select
              value={options.background_mode || "auto"}
              onChange={(e) =>
                set({
                  background_mode: e.target
                    .value as RuleOptions["background_mode"],
                })
              }
            >
              <option value="auto">Use canvas / original background</option>
              <option value="solid">Solid color behind element</option>
            </select>
          </label>
          {options.background_mode === "solid" && (
            <label>
              Element background color
              <input
                type="color"
                value={options.background_color || "#ffffff"}
                onChange={(e) => set({ background_color: e.target.value })}
              />
            </label>
          )}
        </>
      )}
      {field.kind === "drawing" && (
        <>
          <label>
            Pen width
            <input
              type="range"
              min={0.5}
              max={80}
              step={0.5}
              value={options.drawing_width || 3}
              onChange={(e) => set({ drawing_width: Number(e.target.value) })}
            />
          </label>
          <ColorControls options={options} set={set} label="Pen color" />
        </>
      )}
      {![
        "signature",
        "seal",
        "stamp",
        "rubber_stamp",
        "qr",
        "barcode",
        "portrait",
        "drawing",
      ].includes(field.kind) && (
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
            Signature content
            <select
              value={options.signature_content || "current"}
              onChange={(e) =>
                set({
                  signature_content: e.target
                    .value as RuleOptions["signature_content"],
                })
              }
            >
              <option value="current">
                Current · style chooses names or abbreviations
              </option>
              <option value="name">Name only · all name words</option>
              <option value="alphabet">
                Alphabet only · 1–3 initials / letters
              </option>
              <option value="mixed">
                Mixed · names, current and alphabet designs
              </option>
            </select>
          </label>
          <label>
            Signature style
            <select
              value={options.signature_style || "mixed"}
              onChange={(e) =>
                set({
                  signature_style: e.target
                    .value as RuleOptions["signature_style"],
                })
              }
            >
              <option value="mixed">Mixed signature styles per sample</option>
              <option value="enclosed">
                Pen strokes · broad enclosing return
              </option>
              <option value="interwoven">
                Pen strokes · overlapping capitals and compact letters
              </option>
              <option value="gestural">
                Pen strokes · abbreviated fast signing
              </option>
              <option value="stacked">
                Pen strokes · two-line composition
              </option>
              <option value="initial_bridge">
                Pen strokes · initials with a bridge and letter
              </option>
              <option value="terminal_loop">
                Pen strokes · terminal oval or spiral
              </option>
              <option value="crossed">
                Pen strokes · interlocked initials and crossbar
              </option>
              <option value="minimal">
                Pen strokes · simple letter, initials or first name
              </option>
              <option value="surname">
                Pen strokes · initial and compressed surname
              </option>
              <option value="split">
                Pen strokes · initials with a small letter cluster
              </option>
              <option value="tall_initial">
                Tall initials · small connected letters
              </option>
              <option value="compact">
                Compact cursive · tight connected letters
              </option>
              <option value="angular">
                Angular · initial and compressed surname
              </option>
              <option value="looped">
                Large oval initials · connected return
              </option>
              <option value="sweeping">Sweeping crossbar and underline</option>
              <option value="name">Full name · no flourish</option>
              <option value="first_name">First name · no flourish</option>
              <option value="single_letter">One letter · no flourish</option>
              <option value="two_letters">Two letters · no flourish</option>
              <option value="initials">Dotted initials · no flourish</option>
              <option value="letter_wave">Letters → small wave → letter</option>
              <option value="monogram">
                Overlapping letters with a connected finish
              </option>
              <option value="flourish">
                Name with a connected pen flourish
              </option>
            </select>
          </label>
          <p className="field-hint">
            Mixed mode varies letter count, large initials, compressed cursive,
            slant, loops and connected decoration. Some samples contain only
            lettering. Waves and finishing curves join the letters instead of
            adding independent scribbles. A literal rule supplies fictional
            signing text; the selected style may abbreviate it.
          </p>
          <label>
            Signature boldness
            <input
              type="range"
              min={1}
              max={5}
              step={0.1}
              value={options.signature_thickness ?? 1}
              onChange={(e) =>
                set({ signature_thickness: Number(e.target.value) })
              }
            />
          </label>
          <p className="field-hint">
            {(options.signature_thickness ?? 1).toFixed(1)}× · 1× is the current
            default, including random pen weights. Increase for thicker strokes;
            lettering and layout stay the same for the same seed.
          </p>
          <ColorControls options={options} set={set} label="Signature color" />
          <button
            className="btn small"
            type="button"
            onClick={() => set({ signature_thickness: 1 })}
          >
            Use default boldness
          </button>
          <InkOpacityControls options={options} set={set} />
        </>
      )}
      {field.kind === "seal" && (
        <SealControls field={field} options={options} set={set} />
      )}
      {["stamp", "rubber_stamp"].includes(field.kind) && (
        <StampControls field={field} options={options} set={set} />
      )}
    </details>
  );
}
