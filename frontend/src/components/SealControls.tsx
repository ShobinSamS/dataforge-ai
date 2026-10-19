import { useState, useEffect, useRef } from "react";
import { post } from "../api";
import type { Region, RuleOptions } from "../types";

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
  const optionsKey = JSON.stringify(options);
  useEffect(() => {
    previewRevision.current++;
    setPreview(null);
    setError("");
  }, [field.id, field.rule, optionsKey]);
  const change = (patch: Partial<RuleOptions>) => {
    setPreview(null);
    setError("");
    set(
      field.rule?.startsWith("literal:")
        ? { seal_text: field.rule.slice(8), seal_text_mode: "static", ...patch }
        : patch,
    );
  };
  return (
    <>
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
          <option value="random">Random wording per sample</option>
          <option value="static">Static wording · same text each sample</option>
          <option value="custom">
            Custom format · placeholders vary per sample
          </option>
        </select>
      </label>
      <p className="field-hint">
        Random mode varies fictional organizations, departments, people,
        locations, dates and references. Static mode uses your saved wording. A
        custom format controls where generated fields appear.
      </p>
      <label>
        Seal shape
        <select
          value={options.seal_style || "random"}
          onChange={(e) =>
            change({ seal_style: e.target.value as RuleOptions["seal_style"] })
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
          ].map((v) => (
            <option key={v} value={v}>
              {v.replaceAll("_", " ")}
            </option>
          ))}
        </select>
      </label>
      <label>
        Seal ink
        <select
          value={options.seal_color || "random"}
          onChange={(e) =>
            change({ seal_color: e.target.value as RuleOptions["seal_color"] })
          }
        >
          {[
            "random",
            "red",
            "blue",
            "green",
            "purple",
            "black",
            "brown",
            "mixed",
          ].map((v) => (
            <option key={v}>{v}</option>
          ))}
        </select>
      </label>
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
          {["random", "solid", "double", "dotted", "dashed", "serrated"].map(
            (v) => (
              <option key={v}>{v}</option>
            ),
          )}
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
          <label>
            Top format
            <input
              maxLength={200}
              value={options.seal_top_format ?? "{organization}"}
              onChange={(e) => change({ seal_top_format: e.target.value })}
            />
          </label>
          <label>
            Body format
            <textarea
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
            Bottom format
            <input
              maxLength={200}
              value={options.seal_bottom_format ?? "{city} · {state}"}
              onChange={(e) => change({ seal_bottom_format: e.target.value })}
            />
          </label>
          <p className="field-hint">
            Placeholders:{" "}
            {
              "{organization}, {department}, {name}, {title}, {city}, {state}, {year}, {date}, {reference}, {number}"
            }
            . One body line per row, up to six. Reusing a placeholder repeats
            its value inside the seal.
          </p>
        </>
      )}
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
        Off: repeated words are rejected. Enable for matching top/bottom wording
        or intentional repetition. Static mode controls whether the entire
        wording repeats across samples.
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
