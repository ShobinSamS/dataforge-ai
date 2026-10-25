import { useState, useEffect, useRef } from "react";
import { post } from "../api";
import type { Region, RuleOptions } from "../types";
import InkOpacityControls from "./InkOpacityControls";
import ColorControls from "./ColorControls";
import { sealPresets, sealPreset } from "./sealPresets";

export default function SealControls({
  field,
  options,
  set,
}: {
  field: Region;
  options: RuleOptions;
  set: (patch: Partial<RuleOptions>) => void;
}) {
  const mode =
    options.literal_text != null || field.rule?.startsWith("literal:")
      ? "static"
      : options.seal_text_mode || "random";
  const [preview, setPreview] = useState<{
      image: string;
      metadata: { text: string; shape: string };
    } | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [seed, setSeed] = useState(42);
  const previewRevision = useRef(0);
  const [recipe, setRecipe] = useState("");
  const optionsKey = JSON.stringify(options);
  useEffect(() => {
    previewRevision.current++;
    setPreview(null);
    setError("");
  }, [field.id, field.rule, optionsKey]);
  const change = (patch: Partial<RuleOptions>) => {
    setRecipe("");
    setPreview(null);
    setError("");
    set(
      field.rule?.startsWith("literal:")
        ? { seal_text: field.rule.slice(8), seal_text_mode: "static", ...patch }
        : patch,
    );
  };
  const legacyColors = {
    red: "#a12030",
    blue: "#1b3d91",
    green: "#196e44",
    purple: "#633085",
    brown: "#8b4c29",
    black: "#000000",
  };
  const legacy = options.seal_color;
  const colorOptions =
    (options.color_mode === "auto" ||
      options.color_mode === "black" ||
      !options.color_mode) &&
    legacy &&
    legacy !== "black"
      ? {
          ...options,
          color_mode: (legacy === "random"
            ? "random"
            : legacy === "mixed"
              ? "mixed"
              : "manual") as RuleOptions["color_mode"],
          text_color:
            legacyColors[legacy as keyof typeof legacyColors] ||
            options.text_color,
          color_palette:
            legacy === "random" || legacy === "mixed"
              ? Object.values(legacyColors)
              : options.color_palette,
        }
      : options;
  return (
    <>
      <p className="field-hint">
        Start with a complete design, then edit its words and ink. Each seal
        includes its border and lettering; no AI image generation is needed.
      </p>
      <label>
        Seal reference layout
        <select
          value={recipe}
          onChange={(e) => {
            if (e.target.value) {
              change(sealPreset(e.target.value));
              setRecipe(e.target.value);
            }
          }}
        >
          <option value="">Keep current design / choose a preset…</option>
          {Object.entries(sealPresets).map(([key, recipe]) => (
            <option key={key} value={key}>
              {recipe.label}
            </option>
          ))}
        </select>
      </label>
      <p className="field-hint">
        Presets replace layout and wording settings. Your ink color and opacity
        stay as selected.
      </p>
      <label>
        Seal wording
        <select
          value={mode}
          onChange={(e) =>
            change({
              seal_text_mode: e.target.value as RuleOptions["seal_text_mode"],
              literal_text: null,
            })
          }
        >
          <option value="random">Generate all words for me</option>
          <option value="static">Use my exact words in every image</option>
          <option value="custom">
            Edit wording · mix my words with generated details
          </option>
        </select>
      </label>
      <p className="field-hint">
        {mode === "random"
          ? "Creates a different fictional organization and office details for each image."
          : mode === "static"
            ? "These exact words will appear in every image."
            : "Edit the text below. Keep generated details where you want new words in each image."}
      </p>
      <details className="option-section">
        <summary>Layout details · shape, border and decoration</summary>
        <label>
          Seal shape
          <select
            value={options.seal_style || "random"}
            onChange={(e) =>
              change({
                seal_style: e.target.value as RuleOptions["seal_style"],
              })
            }
          >
            {[
              "random",
              "ring",
              "round",
              "double_ring",
              "oval",
              "badge",
              "square",
              "rectangle",
              "professional",
              "form",
              "dated",
              "text",
              "attestation",
              "corporate",
              "form_block",
              "nameplate",
            ].map((v) => (
              <option
                key={v}
                value={v}
                disabled={
                  (!!options.seal_artwork_id ||
                    !!options.seal_artwork_ids?.length) &&
                  ![
                    "random",
                    "ring",
                    "round",
                    "double_ring",
                    "oval",
                    "badge",
                    "corporate",
                  ].includes(v)
                }
              >
                {v.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        </label>
        {(options.seal_artwork_id || !!options.seal_artwork_ids?.length) && (
          <p className="field-hint">
            Center artwork uses circular or oval layouts. Remove the selected
            center artwork to use a block seal.
          </p>
        )}
        <label>
          Seal border
          <select
            value={options.seal_border || "random"}
            onChange={(e) =>
              change({
                seal_border: e.target.value as RuleOptions["seal_border"],
              })
            }
          >
            {[
              "random",
              "solid",
              "double",
              "dotted",
              "dashed",
              "serrated",
              "rosettes",
            ].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          Seal ornament
          <select
            value={options.seal_symbol || "random"}
            onChange={(e) =>
              change({
                seal_symbol: e.target.value as RuleOptions["seal_symbol"],
              })
            }
          >
            {["random", "none", "star", "diamond", "rosette", "monogram"].map(
              (v) => (
                <option key={v}>{v}</option>
              ),
            )}
          </select>
        </label>
        {options.seal_style === "corporate" && (
          <>
            <label>
              Inner top arc
              <input
                maxLength={160}
                value={options.seal_inner_top_text || ""}
                onChange={(e) =>
                  change({ seal_inner_top_text: e.target.value })
                }
              />
            </label>
            <label>
              Inner bottom arc
              <input
                maxLength={160}
                value={options.seal_inner_bottom_text || ""}
                onChange={(e) =>
                  change({ seal_inner_bottom_text: e.target.value })
                }
              />
            </label>
            <label>
              Center motif
              <select
                value={options.seal_center_motif || "none"}
                onChange={(e) =>
                  change({
                    seal_center_motif: e.target
                      .value as RuleOptions["seal_center_motif"],
                  })
                }
              >
                {["none", "shield", "rosette", "rays"].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            <p className="field-hint">
              Inner arcs support the same placeholders in Random and Custom
              modes. Static uses the exact wording. Motifs are generated
              geometric designs.
            </p>
          </>
        )}
        {["attestation", "form_block"].includes(options.seal_style || "") && (
          <>
            <p className="field-hint">
              Put each form row in the body as Label: value. Leave the value
              empty for a blank dotted line. A REG NO: row appears beneath the
              heading. Bottom text can also be a field.
            </p>
            <label>
              Field value writing
              <select
                value={options.seal_field_writing || "printed"}
                onChange={(e) =>
                  change({
                    seal_field_writing: e.target.value as "printed" | "cursive",
                  })
                }
              >
                <option value="printed">Printed</option>
                <option value="cursive">English cursive</option>
              </select>
            </label>
          </>
        )}
        {options.seal_style === "attestation" && (
          <>
            <label className="check-row">
              <input
                type="checkbox"
                checked={options.seal_embedded_signature || false}
                onChange={(e) =>
                  change({ seal_embedded_signature: e.target.checked })
                }
              />
              Add a generated signature inside the stamp
            </label>
            {options.seal_embedded_signature && (
              <label>
                Signing name (blank generates a name)
                <input
                  maxLength={100}
                  value={options.seal_signer_name || ""}
                  onChange={(e) => change({ seal_signer_name: e.target.value })}
                />
              </label>
            )}
            <p className="field-hint">
              The stamp and embedded signature share one seal mask. Use separate
              regions when you need separate seal and signature labels.
            </p>
          </>
        )}
      </details>
      {mode === "static" && (
        <>
          <label>
            Seal main text
            <input
              maxLength={100}
              value={
                options.literal_text ??
                (field.rule?.startsWith("literal:")
                  ? field.rule.slice(8)
                  : (options.seal_text ?? "SAMPLE OFFICE"))
              }
              onChange={(e) =>
                change({ seal_text: e.target.value, literal_text: null })
              }
            />
          </label>
          <label>
            Seal inner text
            <textarea
              rows={4}
              maxLength={360}
              value={options.seal_subtext ?? "RECEIVED"}
              onChange={(e) => change({ seal_subtext: e.target.value })}
            />
          </label>
          <label>
            Seal bottom text
            <input
              maxLength={100}
              value={options.seal_bottom_text || ""}
              onChange={(e) => change({ seal_bottom_text: e.target.value })}
            />
          </label>
        </>
      )}
      {mode === "custom" && (
        <>
          <p className="field-hint">
            Type your own words below. A token such as {"{organization}"}{" "}
            changes for each image; plain words stay the same. Clear a field to
            leave that part empty.
          </p>
          <label>
            Company / top text
            <input
              aria-label="Top format"
              maxLength={200}
              value={options.seal_top_format ?? "{organization}"}
              onChange={(e) => change({ seal_top_format: e.target.value })}
            />
          </label>
          <label>
            Center text / form rows
            <textarea
              aria-label="Body format"
              rows={4}
              maxLength={480}
              value={
                options.seal_body_format ??
                "{department}\n{name}\nREF {reference}"
              }
              onChange={(e) => change({ seal_body_format: e.target.value })}
            />
          </label>
          <label>
            Location / bottom text
            <input
              aria-label="Bottom format"
              maxLength={200}
              value={options.seal_bottom_format ?? "{city} · {state}"}
              onChange={(e) => change({ seal_bottom_format: e.target.value })}
            />
          </label>
          <details>
            <summary>Available generated details</summary>
            <p className="field-hint">
              Placeholders:{" "}
              {
                "{organization}, {department}, {name}, {title}, {city}, {state}, {year}, {date}, {reference}, {number}"
              }
              . One body line per row, up to six. Reusing a placeholder repeats
              its value inside the seal.
            </p>
          </details>
        </>
      )}
      <ColorControls
        options={colorOptions}
        set={change}
        label="Seal ink"
        seal
      />
      <details className="option-section">
        <summary>Ink finish and repeated words</summary>
        <label className="check-row">
          <input
            type="checkbox"
            checked={options.seal_allow_repeated_words || false}
            onChange={(e) =>
              change({ seal_allow_repeated_words: e.target.checked })
            }
          />
          Allow repeated words
        </label>
        <p className="field-hint">
          Off: repeated words are rejected. Enable for matching top/bottom
          wording or intentional repetition. Static mode controls whether the
          entire wording repeats across samples.
        </p>
        <label>
          Ink wear
          <input
            type="number"
            min={0}
            max={0.45}
            step={0.01}
            value={options.seal_wear ?? 0.08}
            onChange={(e) => change({ seal_wear: Number(e.target.value) })}
          />
        </label>
        <InkOpacityControls options={options} set={change} />
      </details>
      <button
        type="button"
        className="btn small"
        disabled={busy}
        onClick={async () => {
          const revision = previewRevision.current;
          setBusy(true);
          setError("");
          try {
            const result = await post<{
              image: string;
              metadata: { text: string; shape: string };
            }>("/seals/preview", {
              options,
              region_id: field.id,
              seed,
              width: field.box[2],
              height: field.box[3],
              literal: field.rule?.startsWith("literal:")
                ? field.rule.slice(8)
                : null,
            });
            if (revision === previewRevision.current) {
              setPreview(result);
              setSeed((n) => n + 1);
            }
          } catch (e) {
            if (revision === previewRevision.current) {
              setPreview(null);
              setError(e instanceof Error ? e.message : "Seal preview failed");
            }
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Rendering seal…" : "Preview seal variation"}
      </button>
      {error && (
        <p className="inline-error" role="alert">
          {error}
        </p>
      )}
      {preview && (
        <figure className="seal-preview">
          <img
            src={preview.image}
            alt={`Fictional ${preview.metadata.shape} seal preview`}
          />
          <figcaption>{preview.metadata.shape} · actual wording</figcaption>
          <pre>{preview.metadata.text}</pre>
        </figure>
      )}
    </>
  );
}
