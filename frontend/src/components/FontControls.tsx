import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post } from "../api";
import type { Region, RuleOptions } from "../types";

export default function FontControls({
  field,
  options,
  templateId,
  onChange,
}: {
  field: Region;
  options: RuleOptions;
  templateId?: string;
  onChange: (patch: Partial<Region>) => void;
}) {
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const { data } = useQuery({
    queryKey: ["fonts"],
    queryFn: () => api<{ id: string; label: string }[]>("/fonts"),
    staleTime: Infinity,
  });
  const fonts = Array.isArray(data) ? data : [];
  const setOptions = (patch: Partial<RuleOptions>) =>
    onChange({ rule_options: { ...options, ...patch }, confirmed: false });
  return (
    <details className="font-controls">
      <summary>Font and appearance</summary>
      {field.source_font && (
        <p className="field-hint">
          PDF source: {field.source_font} ·{" "}
          {Math.round(field.source_font_size || 0)} px. Automatic font uses the
          nearest installed family.
        </p>
      )}
      <label>
        Font family
        <select
          value={options.font_id || "auto"}
          onChange={(e) => setOptions({ font_id: e.target.value })}
        >
          <option value="auto">Automatic / source font</option>
          {fonts.map((font) => (
            <option value={font.id} key={font.id}>
              {font.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Font weight
        <select
          value={options.font_weight || "auto"}
          onChange={(e) =>
            setOptions({
              font_weight: e.target.value as RuleOptions["font_weight"],
            })
          }
        >
          <option value="auto">Match source / selected face</option>
          <option value="normal">Regular</option>
          <option value="bold">Bold</option>
        </select>
      </label>
      <label>
        Font size (pixels; empty = fit)
        <input
          type="number"
          min={6}
          max={200}
          value={options.font_size ?? ""}
          onChange={(e) =>
            setOptions({
              font_size: e.target.value ? Number(e.target.value) : null,
            })
          }
        />
      </label>
      <label>
        Text color mode
        <select
          value={options.color_mode || "auto"}
          onChange={(e) =>
            setOptions({
              color_mode: e.target.value as RuleOptions["color_mode"],
            })
          }
        >
          <option value="auto">Match original lettering</option>
          <option value="manual">Custom text color</option>
        </select>
      </label>
      <label>
        Text color
        <input
          type="color"
          value={options.text_color || "#000000"}
          onChange={(e) =>
            setOptions({ text_color: e.target.value, color_mode: "manual" })
          }
        />
      </label>
      <label>
        Text background cleanup
        <select
          value={options.background_mode || "auto"}
          onChange={(e) =>
            setOptions({
              background_mode: e.target.value as RuleOptions["background_mode"],
            })
          }
        >
          <option value="auto">Restore original background</option>
          <option value="solid">Solid background color</option>
        </select>
      </label>
      {options.background_mode === "solid" && (
        <label>
          Background color
          <input
            type="color"
            value={options.background_color || "#ffffff"}
            onChange={(e) => setOptions({ background_color: e.target.value })}
          />
        </label>
      )}
      <label>
        Source text for font matching
        <input
          maxLength={200}
          value={field.text}
          placeholder="Text visible in the selected source region"
          onChange={(e) => onChange({ text: e.target.value, confirmed: false })}
        />
      </label>
      <button
        type="button"
        className="btn"
        disabled={busy || !templateId}
        onClick={async () => {
          setBusy(true);
          setMessage("");
          try {
            const result = await post<{
              region: Region;
              match: { label: string; similarity: number; warning: string };
            }>(`/templates/${templateId}/font-match`, { region: field });
            onChange(result.region);
            setMessage(
              `${result.match.label} · shape similarity ${Math.round(result.match.similarity * 100)}%. ${result.match.warning}`,
            );
          } catch (e) {
            setMessage(e instanceof Error ? e.message : "Font matching failed");
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Matching…" : "Match source font"}
      </button>
      <p className="field-hint">
        Automatic generation matches source weight and color without adding a
        text background. Font matching compares source lettering with installed
        fonts. If source text is empty, configured local OCR is tried. Scans
        provide an estimate; choose a family manually when needed.
      </p>
      {message && (
        <p role="status" className="field-hint">
          {message}
        </p>
      )}
    </details>
  );
}
