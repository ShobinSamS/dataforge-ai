import { useEffect, useRef, useState } from "react";
import { post } from "../api";
import type { Region, Template } from "../types";

const coverage = (a: Region["box"], b: Region["box"]) =>
  (Math.max(0, Math.min(a[0] + a[2], b[0] + b[2]) - Math.max(a[0], b[0])) *
    Math.max(0, Math.min(a[1] + a[3], b[1] + b[3]) - Math.max(a[1], b[1]))) /
  Math.max(1, a[2] * a[3]);

export function applyVisualRegions(
  regions: Region[],
  candidates: Region[],
  template: Template,
) {
  const original = new Map(
    template.regions.map((r) => [r.id, JSON.stringify(r)]),
  );
  let result = [...regions],
    added = 0,
    skipped = 0;
  for (const candidate of candidates) {
    const removable = new Set(
      result
        .filter(
          (r) =>
            r.origin === "ocr" &&
            !r.confirmed &&
            JSON.stringify(r) === original.get(r.id) &&
            coverage(r.box, candidate.box) >= 0.75,
        )
        .map((r) => r.id),
    );
    const preserved = result.filter((r) => !removable.has(r.id));
    if (
      preserved.some(
        (r) => r.id === candidate.id || coverage(r.box, candidate.box) > 0,
      ) ||
      preserved.length >= 200
    ) {
      skipped++;
      continue;
    }
    result = [...preserved, { ...candidate, confirmed: false }];
    added++;
  }
  return { regions: result, added, skipped };
}

export default function VisualRegions({
  template,
  regions,
  onApply,
}: {
  template: Template;
  regions: Region[];
  onApply: (regions: Region[]) => void;
}) {
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [error, setError] = useState(""),
    [warnings, setWarnings] = useState<string[]>([]);
  const latest = useRef({ regions, template });
  latest.current = { regions, template };
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  return (
    <section className="panel">
      <h3>QR codes, barcodes and photos</h3>
      <p className="field-hint">
        Uploads automatically propose visual boxes. You can label them later:
        select a box to change its label or type, resize it, or use Delete
        region. Photo bounds are estimates around detected faces; other photos
        need a manual box. Detection scores are heuristic, not accuracy
        guarantees. Code contents are not read.
      </p>
      <button
        type="button"
        className="btn"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setError("");
          setMessage("");
          const id = template.id;
          try {
            const data = await post<{
              candidates: Region[];
              warnings: string[];
            }>(`/templates/${id}/detect-visual-regions`, {});
            if (!mounted.current || latest.current.template.id !== id) return;
            const applied = applyVisualRegions(
              latest.current.regions,
              data.candidates,
              latest.current.template,
            );
            if (applied.added) onApply(applied.regions);
            setWarnings(data.warnings);
            setMessage(
              `${applied.added} visual boxes added. ${applied.skipped} existing, overlapping or excess proposals skipped. Review boxes and save before generation.`,
            );
          } catch (e) {
            if (mounted.current)
              setError(
                e instanceof Error ? e.message : "Visual detection failed",
              );
          } finally {
            if (mounted.current) setBusy(false);
          }
        }}
      >
        {busy ? "Finding visual regions…" : "Find visual regions"}
      </button>
      {message && <p role="status">{message}</p>}
      {warnings.map((w, i) => (
        <p className="field-hint" key={i}>
          {w}
        </p>
      ))}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
