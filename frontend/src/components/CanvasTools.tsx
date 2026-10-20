import { useEffect, useRef, useState } from "react";
import { post } from "../api";
import { fieldTypes } from "../types";
import type { FieldType, Region, Template } from "../types";

export default function CanvasTools({
  template,
  regions,
  selected,
  onChange,
  onSelect,
  onPreview,
}: {
  template: Template;
  regions: Region[];
  selected: string;
  onChange: (regions: Region[]) => void;
  onSelect: (id: string) => void;
  onPreview: (url: string) => void;
}) {
  const [kind, setKind] = useState<FieldType>("text"),
    [seed, setSeed] = useState(42),
    [image, setImage] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const revision = useRef(0);
  useEffect(() => {
    revision.current++;
    setImage("");
    setError("");
    onPreview("");
  }, [template.id, regions, seed]);
  const index = regions.findIndex((r) => r.id === selected);
  const move = (direction: number) => {
    const next = [...regions],
      target = index + direction;
    if (index < 0 || target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  };
  return (
    <section className="panel canvas-tools">
      <div className="panel-title">
        <h2>Build your canvas</h2>
        <span className="muted">
          {template.width} × {template.height} px · {template.canvas?.dpi} DPI ·{" "}
          {template.canvas?.background} background
        </span>
      </div>
      <div className="canvas-actions">
        <label>
          New element
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as FieldType)}
          >
            {fieldTypes
              .filter((k) => k !== "drawing")
              .map((k) => (
                <option key={k} value={k}>
                  {k === "portrait" ? "Photo / image" : k.replaceAll("_", " ")}
                </option>
              ))}
          </select>
        </label>
        <button
          className="btn"
          disabled={regions.length >= 200}
          onClick={() => {
            const id = crypto.randomUUID().replaceAll("-", "");
            let w = Math.round(template.width * 0.5),
              h = Math.round(template.height * 0.16);
            if (["seal", "qr", "stamp", "portrait"].includes(kind)) {
              h = Math.round(template.height * 0.4);
              w = Math.min(
                w,
                kind === "portrait" || kind === "stamp"
                  ? Math.round(h * 0.75)
                  : h,
              );
            }
            const x = Math.min(
                template.width - w - 8,
                Math.round(template.width * 0.1) + regions.length * 12,
              ),
              y = Math.min(
                template.height - h - 8,
                Math.round(template.height * 0.1) + regions.length * 12,
              );
            onChange([
              ...regions,
              {
                id,
                kind,
                label: kind === "portrait" ? "Photo / image" : kind,
                box: [
                  Math.max(4, x),
                  Math.max(4, y),
                  Math.max(16, w),
                  Math.max(16, h),
                ],
                text: "",
                confidence: 1,
                sensitive: false,
                replace: true,
                confirmed: false,
                page: 0,
                rule: "",
                ...(kind === "text"
                  ? {
                      rule_options: {
                        literal_text: "Your text",
                      } as Region["rule_options"],
                    }
                  : {}),
              },
            ]);
            onSelect(id);
          }}
        >
          Add element
        </button>
        <button className="btn" disabled={index <= 0} onClick={() => move(-1)}>
          Send backward
        </button>
        <button
          className="btn"
          disabled={index < 0 || index === regions.length - 1}
          onClick={() => move(1)}
        >
          Bring forward
        </button>
        <label>
          Preview seed
          <input
            type="number"
            min={0}
            max={2147483647}
            value={seed}
            onChange={(e) => setSeed(Number(e.target.value))}
          />
        </label>
        <button
          className="btn primary"
          disabled={busy}
          onClick={async () => {
            const current = revision.current;
            setBusy(true);
            setError("");
            try {
              const result = await post<{ image: string; errors: string[] }>(
                `/templates/${template.id}/preview`,
                { regions, seed },
              );
              if (current === revision.current) {
                setImage(result.image);
                onPreview(result.image);
                if (result.errors.length) setError(result.errors.join(", "));
              }
            } catch (e) {
              if (current === revision.current)
                setError(e instanceof Error ? e.message : "Preview failed");
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Rendering…" : "Preview canvas"}
        </button>
        {image && (
          <a
            className="btn"
            href={image}
            download={`${template.name.replace(/[^a-zA-Z0-9_-]/g, "_")}.png`}
          >
            Download PNG
          </a>
        )}
      </div>
      <p className="field-hint">
        Add elements or draw their boxes with +. Use the pen for freehand
        strokes. Drag and resize on the canvas; select an element to edit its
        text, font, colors or image pool. Later elements appear on top. Preview
        refreshes the canvas and enables PNG download. Save the final review to
        generate batches.
      </p>
      {error && (
        <p role="alert" className="rule-error">
          {error}
        </p>
      )}
    </section>
  );
}
