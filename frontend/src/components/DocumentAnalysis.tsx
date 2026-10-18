import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post } from "../api";
import { fieldTypes, type Region, type Template } from "../types";

interface PiiResult {
  candidates: Region[];
  engine: string;
  ocr_engine: string;
  analyzed_count: number;
  warnings: string[];
}
interface Cell {
  id: string;
  table: number;
  row: number;
  column: number;
  box: Region["box"];
  text: string;
  confidence: number;
}
interface TableResult {
  cells: Cell[];
  engine: string;
  warnings: string[];
}
export const overlaps = (a: Region["box"], b: Region["box"]) =>
  Math.min(a[0] + a[2], b[0] + b[2]) > Math.max(a[0], b[0]) &&
  Math.min(a[1] + a[3], b[1] + b[3]) > Math.max(a[1], b[1]);

export function applyPii(
  regions: Region[],
  candidates: Region[],
  template: Template,
  confirmed: boolean,
) {
  const original = new Map(
    template.regions.map((r) => [r.id, JSON.stringify(r)]),
  );
  const preserved = regions.filter(
    (r) =>
      !(
        (r.origin === "ocr" || r.origin === undefined) &&
        !r.confirmed &&
        !r.rule &&
        !r.action &&
        r.text &&
        JSON.stringify(r) === original.get(r.id)
      ),
  );
  const result = [...preserved];
  let skipped = 0;
  for (const candidate of candidates) {
    if (
      result.some(
        (r) =>
          (r.action || (r.replace ? "replace" : "keep")) !== "keep" &&
          overlaps(r.box, candidate.box),
      )
    ) {
      skipped++;
      continue;
    }
    if (result.length >= 200) {
      skipped++;
      continue;
    }
    result.push({ ...candidate, confirmed, action: "erase", replace: true });
  }
  return { regions: result, skipped, added: result.length - preserved.length };
}

function download(name: string, type: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function tableCsv(cells: Cell[]) {
  const lines: string[] = [];
  for (const table of [...new Set(cells.map((c) => c.table))].sort(
    (a, b) => a - b,
  )) {
    const subset = cells.filter((c) => c.table === table);
    const rows = Math.max(...subset.map((c) => c.row)) + 1,
      cols = Math.max(...subset.map((c) => c.column)) + 1;
    for (let row = 0; row < rows; row++)
      lines.push(
        Array.from({ length: cols }, (_, column) => {
          let value =
            subset.find((c) => c.row === row && c.column === column)?.text ||
            "";
          if (/^[\s]*[=+@-]/.test(value)) value = "'" + value;
          return '"' + value.replaceAll('"', '""') + '"';
        }).join(","),
      );
    lines.push("");
  }
  return lines.join("\r\n");
}

export default function DocumentAnalysis({
  template,
  regions,
  onApply,
  onPreview,
}: {
  template: Template;
  regions: Region[];
  onApply: (r: Region[]) => void;
  onPreview: (r: Region[]) => void;
}) {
  const [mode, setMode] = useState("existing"),
    [engine, setEngine] = useState("local_qwen"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const [pii, setPii] = useState<PiiResult | null>(null),
    [selected, setSelected] = useState<Set<string>>(new Set()),
    [verified, setVerified] = useState(false),
    [table, setTable] = useState<TableResult | null>(null);
  const current = useRef(regions);
  current.current = regions;
  const source = useRef("");
  const caps = useQuery({
    queryKey: ["document-analysis-capabilities"],
    queryFn: () =>
      api<{ models: Record<string, boolean>; language: string }>(
        "/document-analysis/capabilities",
      ),
    staleTime: 30000,
  });
  // Geometry/text edits invalidate old model results, including requests still in flight.
  const fingerprint = JSON.stringify(regions);
  useEffect(() => {
    setPii(null);
    setSelected(new Set());
    setTable(null);
    setVerified(false);
    onPreview([]);
  }, [fingerprint]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    onPreview(
      pii
        ? pii.candidates.filter((c) => selected.has(c.id))
        : table
          ? table.cells.map((c) => ({
              id: c.id,
              label: `Table ${c.table + 1} R${c.row + 1} C${c.column + 1}`,
              kind: "text",
              box: c.box,
              text: c.text,
              confidence: c.confidence,
              sensitive: false,
              replace: false,
              confirmed: false,
              page: 0,
              rule: "",
            }))
          : [],
    );
  }, [pii, selected, table, onPreview]);
  const run = async (task: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setMessage("");
    source.current = JSON.stringify(current.current);
    try {
      await task();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setBusy(false);
    }
  };
  const assertCurrent = () => {
    if (source.current !== JSON.stringify(current.current))
      throw new Error("Regions changed during analysis. Run analysis again.");
  };
  const payload = () => ({ regions: current.current, ocr_mode: mode, engine });
  return (
    <section className="panel document-analysis" aria-busy={busy}>
      <div className="panel-title">
        <h2>Find PII and extract tables</h2>
      </div>
      <div className="analysis-toolbar">
        <label>
          Text recognition
          <select
            disabled={busy}
            value={mode}
            onChange={(e) => {
              setMode(e.target.value);
              setPii(null);
              setTable(null);
              setVerified(false);
            }}
          >
            <option value="existing">Existing text / configured OCR</option>
            <option value="printed" disabled={!caps.data?.models.printed}>
              English printed · TrOCR{" "}
              {caps.data?.models.printed ? "" : "(not installed)"}
            </option>
            <option
              value="handwritten"
              disabled={!caps.data?.models.handwritten}
            >
              English handwriting · TrOCR{" "}
              {caps.data?.models.handwritten ? "" : "(not installed)"}
            </option>
          </select>
        </label>
        <label>
          PII classifier
          <select
            disabled={busy}
            value={engine}
            onChange={(e) => setEngine(e.target.value)}
          >
            <option value="local_qwen">Local Qwen + rules</option>
            <option value="regex">Rules only (limited)</option>
          </select>
        </label>
        <button
          type="button"
          className="btn primary"
          disabled={busy}
          onClick={() =>
            run(async () => {
              const result = await post<PiiResult>(
                `/templates/${template.id}/analyze-pii`,
                payload(),
              );
              assertCurrent();
              setPii(result);
              setTable(null);
              setSelected(new Set(result.candidates.map((c) => c.id)));
              setVerified(false);
            })
          }
        >
          {busy ? "Analyzing…" : "Find PII and auto-label"}
        </button>
        <button
          type="button"
          className="btn"
          disabled={busy}
          onClick={() =>
            run(async () => {
              const result = await post<TableResult>(
                `/templates/${template.id}/extract-table`,
                payload(),
              );
              assertCurrent();
              setTable(result);
              setPii(null);
            })
          }
        >
          Extract ruled table
        </button>
      </div>
      <p className="field-hint">
        For TrOCR, existing boxes are treated as single-line crops; delete
        unsuitable proposals to detect page lines. Handwriting recognition is
        experimental English only. No online inference. OCR can miss PII;
        inspect the full page.
      </p>
      {pii && (
        <>
          <p>
            {pii.candidates.length} suggestions from {pii.analyzed_count} text
            groups · {pii.ocr_engine} · {pii.engine}
          </p>
          <div className="analysis-results">
            {pii.candidates.map((c) => (
              <div key={c.id} className="analysis-candidate">
                <label className="check-label">
                  <input
                    type="checkbox"
                    checked={selected.has(c.id)}
                    onChange={(e) => {
                      setSelected((old) => {
                        const next = new Set(old);
                        if (e.target.checked) next.add(c.id);
                        else next.delete(c.id);
                        return next;
                      });
                      setVerified(false);
                    }}
                  />
                  Select
                </label>
                <label>
                  PII label
                  <input
                    value={c.label}
                    onChange={(e) => {
                      setPii({
                        ...pii,
                        candidates: pii.candidates.map((r) =>
                          r.id === c.id ? { ...r, label: e.target.value } : r,
                        ),
                      });
                      setVerified(false);
                    }}
                    maxLength={100}
                  />
                </label>
                <label>
                  Detected type
                  <select
                    value={c.kind}
                    onChange={(e) => {
                      setPii({
                        ...pii,
                        candidates: pii.candidates.map((r) =>
                          r.id === c.id
                            ? { ...r, kind: e.target.value as Region["kind"] }
                            : r,
                        ),
                      });
                      setVerified(false);
                    }}
                  >
                    {fieldTypes.map((t) => (
                      <option key={t}>{t}</option>
                    ))}
                  </select>
                </label>
                <small>
                  {c.text} · [{c.box.join(", ")}]
                </small>
              </div>
            ))}
          </div>
          <label className="check-label">
            <input
              type="checkbox"
              checked={verified}
              onChange={(e) => setVerified(e.target.checked)}
            />
            I checked the selected PII boxes and labels
          </label>
          <button
            className="btn"
            disabled={busy || !selected.size}
            onClick={() => {
              const result = applyPii(
                regions,
                pii.candidates.filter((c) => selected.has(c.id)),
                template,
                verified,
              );
              if (result.added) {
                onApply(result.regions);
                setPii(null);
                onPreview([]);
              }
              setMessage(
                `${result.added} regions marked for erase. ${result.skipped} overlapping or excess suggestions skipped; adjust them manually. Untouched upload OCR proposals were replaced; edited/manual regions were preserved. Save the review before generation. Source image is unchanged.`,
              );
            }}
          >
            Apply selected as erase regions
          </button>
          {pii.warnings.map((w, i) => (
            <p className="field-hint" key={i}>
              {w}
            </p>
          ))}
        </>
      )}
      {table && (
        <>
          <p>
            Cell transcription · {table.engine}. Edit errors before export or
            Qwen structuring.
          </p>
          <div className="analysis-results">
            <table>
              <thead>
                <tr>
                  <th>Table</th>
                  <th>Row</th>
                  <th>Column</th>
                  <th>Extracted text</th>
                  <th>Score</th>
                </tr>
              </thead>
              <tbody>
                {table.cells.map((c) => (
                  <tr key={c.id}>
                    <td>{c.table + 1}</td>
                    <td>
                      <input
                        aria-label={`Row ${c.id}`}
                        disabled={busy}
                        type="number"
                        min={1}
                        max={201}
                        value={c.row + 1}
                        onChange={(e) =>
                          setTable({
                            ...table,
                            cells: table.cells.map((v) =>
                              v.id === c.id
                                ? {
                                    ...v,
                                    row: Math.max(
                                      0,
                                      Math.min(200, Number(e.target.value) - 1),
                                    ),
                                  }
                                : v,
                            ),
                          })
                        }
                      />
                    </td>
                    <td>
                      <input
                        aria-label={`Column ${c.id}`}
                        disabled={busy}
                        type="number"
                        min={1}
                        max={201}
                        value={c.column + 1}
                        onChange={(e) =>
                          setTable({
                            ...table,
                            cells: table.cells.map((v) =>
                              v.id === c.id
                                ? {
                                    ...v,
                                    column: Math.max(
                                      0,
                                      Math.min(200, Number(e.target.value) - 1),
                                    ),
                                  }
                                : v,
                            ),
                          })
                        }
                      />
                    </td>
                    <td>
                      <input
                        aria-label={`Text ${c.id}`}
                        disabled={busy}
                        maxLength={400}
                        value={c.text}
                        onChange={(e) =>
                          setTable({
                            ...table,
                            cells: table.cells.map((v) =>
                              v.id === c.id
                                ? { ...v, text: e.target.value }
                                : v,
                            ),
                          })
                        }
                      />
                    </td>
                    <td>{Math.round(c.confidence * 100)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="analysis-toolbar">
            <button
              className="btn"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  const updates = new Map<
                    string,
                    { row: number; column: number }
                  >();
                  for (const tableId of new Set(
                    table.cells.map((c) => c.table),
                  )) {
                    const result = await post<{
                      cells: { id: string; row: number; column: number }[];
                    }>("/document-analysis/structure-table", {
                      cells: table.cells
                        .filter((c) => c.table === tableId)
                        .map((c) => ({
                          id: c.id,
                          text: c.text,
                          row: c.row,
                          column: c.column,
                        })),
                    });
                    result.cells.forEach((c) => updates.set(c.id, c));
                  }
                  assertCurrent();
                  setTable({
                    ...table,
                    cells: table.cells.map((c) => ({
                      ...c,
                      ...updates.get(c.id),
                    })),
                    warnings: [
                      ...table.warnings,
                      "Qwen rearranged source IDs only. Review assignments; it did not complete or rewrite text.",
                    ],
                  });
                })
              }
            >
              Structure cells with local Qwen
            </button>
            <button
              className="btn"
              disabled={busy}
              onClick={() =>
                download(
                  "extracted-table.json",
                  "application/json",
                  JSON.stringify(table, null, 2),
                )
              }
            >
              Export table JSON
            </button>
            <button
              className="btn"
              disabled={busy}
              onClick={() => {
                if (
                  new Set(
                    table.cells.map((c) => `${c.table}:${c.row}:${c.column}`),
                  ).size !== table.cells.length
                ) {
                  setError(
                    "Multiple cells have the same row/column. Correct them before CSV export.",
                  );
                  return;
                }
                download(
                  "extracted-table.csv",
                  "text/csv;charset=utf-8",
                  tableCsv(table.cells),
                );
              }}
            >
              Export table CSV
            </button>
          </div>
          {table.warnings.map((w, i) => (
            <p className="field-hint" key={i}>
              {w}
            </p>
          ))}
        </>
      )}
      {message && <p role="status">{message}</p>}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
