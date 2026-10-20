import type { Config, Template } from "../types";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export default function SignatureGeneration({
  config,
  template,
  onChange,
}: {
  config: Config;
  template?: Template;
  onChange: (patch: Partial<Config>) => void;
}) {
  const fields =
    template?.regions.filter(
      (r) => r.kind === "signature" && r.replace && r.action !== "erase",
    ) || [];
  const [show, setShow] = useState(false),
    [offset, setOffset] = useState(0);
  const style =
    config.signature_style_override ||
    fields[0]?.rule_options?.signature_style ||
    "mixed";
  const seed = (config.seed + offset) % 2 ** 31;
  const options = fields[0]?.rule_options;
  const query = new URLSearchParams({
    ink_opacity_mode: options?.ink_opacity_mode || "random",
    ink_opacity: String(options?.ink_opacity ?? 1),
    ink_opacity_min: String(options?.ink_opacity_min ?? 0.45),
    ink_opacity_max: String(options?.ink_opacity_max ?? 1),
    ink_finish: options?.ink_finish || "natural",
    ink_irregularity: String(options?.ink_irregularity ?? 0.55),
    signature_thickness: String(options?.signature_thickness ?? 1),
    font_weight: options?.font_weight || "auto",
    signature_content:
      config.signature_content_override ||
      options?.signature_content ||
      "current",
    color_mode: options?.color_mode || "black",
    text_color: options?.text_color || "#000000",
  });
  for (const color of options?.color_palette || [
    "#000000",
    "#173574",
    "#a61c32",
    "#216e39",
    "#6a338e",
  ])
    query.append("color_palette", color);
  const opacityQuery = query.toString();
  const previews = useQuery({
    queryKey: ["signature_previews", style, seed, opacityQuery],
    queryFn: () =>
      api<{ style: string; url: string }[]>(
        `/signatures/previews?style=${style}&seed=${seed}&${opacityQuery}`,
      ),
    enabled: show && config.signatures && !!fields.length,
  });
  if (!config.signatures || !fields.length) return null;
  return (
    <div>
      <label>
        Signature content for this batch
        <select
          value={config.signature_content_override || "template"}
          onChange={(e) =>
            onChange({
              signature_content_override:
                e.target.value === "template"
                  ? null
                  : (e.target.value as Config["signature_content_override"]),
            })
          }
        >
          <option value="mixed">
            Mixed · names, current and alphabet designs
          </option>
          <option value="current">Current version only</option>
          <option value="name">Name only</option>
          <option value="alphabet">Alphabet / initials only</option>
          <option value="template">Use saved region content settings</option>
        </select>
      </label>
      <p className="field-hint">
        Content chooses the signing letters; style below chooses the shape and
        flourishes. New batches default to Mixed. Choose saved region settings
        to honor each region's content choice.
      </p>
      <label>
        Signature variety for this batch
        <select
          value={config.signature_style_override || "template"}
          onChange={(e) =>
            onChange({
              signature_style_override:
                e.target.value === "mixed" ? "mixed" : null,
            })
          }
        >
          <option value="template">Use saved region styles</option>
          <option value="mixed">
            Mixed · vary lettering, layout and pen designs
          </option>
        </select>
      </label>
      <p className="field-hint">
        Saved styles:{" "}
        {fields
          .map(
            (r) =>
              `${r.label || r.id}: ${(r.rule_options?.signature_style || "mixed").replaceAll("_", " ")}`,
          )
          .join("; ")}
        .{" "}
        {config.signature_style_override
          ? "This new batch uses Mixed for every signature region."
          : "Fixed styles keep producing that style. Select Mixed above to use the full range of variations."}{" "}
        Existing datasets and resumed jobs keep their saved settings.
      </p>
      <button
        className="btn small"
        type="button"
        onClick={() => {
          if (show) setOffset((n) => n + 6);
          setShow(true);
        }}
      >
        Preview signature variations
      </button>
      {show && (
        <>
          <p className="field-hint">
            Fictional style examples · first signature region · previews are
            separate from dataset samples. Ink finish and opacity use this
            region's saved settings. Change them in Template editor → Rendering
            style and cleanup.
          </p>
          {previews.isLoading && <p>Loading signature previews…</p>}
          {previews.error && <p role="alert">{previews.error.message}</p>}
          <div className="signature-preview-grid">
            {previews.data?.map((p, i) => (
              <figure key={p.url}>
                <img
                  src={p.url}
                  alt={`Fictional ${p.style.replaceAll("_", " ")} signature ${i + 1}`}
                />
                <figcaption>{p.style.replaceAll("_", " ")}</figcaption>
              </figure>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
