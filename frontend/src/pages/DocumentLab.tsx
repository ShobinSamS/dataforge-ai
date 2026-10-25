import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, post } from "../api";
import SampleAnnotationEditor from "../components/SampleAnnotationEditor";
type LabConfig = {
  name: string;
  kind: string;
  count: number;
  pages: number;
  seed: number;
  layout_families: number;
  capture: string;
  capture_strength: number;
  capture_percent: number;
  handwritten_percent: number;
  faint_percent: number;
  signature_percent: number;
  seal_percent: number;
  negative_percent: number;
  train_percent: number;
  validation_percent: number;
};
type LabPage = {
  document: number;
  page: number;
  split: string;
  family: number;
  revision: number;
  image_url: string;
  rejected: boolean;
  annotation_count: number;
};
type LabJob = {
  id: string;
  config: LabConfig;
  status: string;
  completed: number;
  total: number;
  error: string;
  pages: LabPage[];
  download_url: string;
};
const initial: LabConfig = {
  name: "Fictional document packs",
  kind: "mixed",
  count: 10,
  pages: 2,
  seed: 42,
  layout_families: 5,
  capture: "mixed",
  capture_strength: 0.5,
  capture_percent: 50,
  handwritten_percent: 30,
  faint_percent: 30,
  signature_percent: 80,
  seal_percent: 60,
  negative_percent: 10,
  train_percent: 80,
  validation_percent: 10,
};
const classes = [
  "text",
  "name",
  "identifier",
  "address",
  "date",
  "qr",
  "signature",
  "seal",
  "portrait",
  "checkbox",
  "table_header",
  "table_cell",
];
export default function DocumentLab() {
  const client = useQueryClient(),
    [config, setConfig] = useState(initial),
    [selected, setSelected] = useState(""),
    [pageKey, setPageKey] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const jobs = useQuery({
    queryKey: ["document-lab"],
    queryFn: () => api<LabJob[]>("/document-lab/jobs"),
    refetchInterval: (q) =>
      q.state.data?.some((j) =>
        ["queued", "running", "cancelling"].includes(j.status),
      )
        ? 2000
        : false,
  });
  const job = jobs.data?.find((j) => j.id === selected) || jobs.data?.[0],
    page =
      job?.pages.find((p) => `${p.document}-${p.page}` === pageKey) ||
      job?.pages[0];
  const stopped =
      job && !["queued", "running", "cancelling"].includes(job.status),
    refresh = () => {
      void client.invalidateQueries({ queryKey: ["document-lab"] });
    };
  async function action(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const set = (patch: Partial<LabConfig>) =>
    setConfig((c) => ({ ...c, ...patch }));
  return (
    <div className="document-lab">
      <p className="muted">
        Create fictional A4 invoices and application packs. Pages share one
        record. Layout families and signer identities stay in one split.
      </p>
      {(error || jobs.error) && (
        <p role="alert" className="inline-error">
          {error || jobs.error?.message}
        </p>
      )}
      <div className="studio-grid">
        <section className="panel">
          <h2>Document pack settings</h2>
          <label>
            Dataset name
            <input
              value={config.name}
              onChange={(e) => set({ name: e.target.value })}
            />
          </label>
          <label>
            Document kind
            <select
              value={config.kind}
              onChange={(e) => set({ kind: e.target.value })}
            >
              <option value="mixed">Invoices and applications</option>
              <option value="invoice">
                Invoices · variable tables and totals
              </option>
              <option value="application">
                Applications · fields and checkboxes
              </option>
            </select>
          </label>
          <div className="form-grid">
            {(
              [
                ["count", "Document packs", 1, 100],
                ["pages", "Pages per pack", 1, 5],
                ["seed", "Seed", 0, 2147483647],
                ["layout_families", "Layout families", 1, 30],
              ] as const
            ).map(([key, label, min, max]) => (
              <label key={key}>
                {label}
                <input
                  type="number"
                  min={min}
                  max={max}
                  value={config[key]}
                  onChange={(e) => set({ [key]: Number(e.target.value) })}
                />
              </label>
            ))}
          </div>
          <p className="field-hint">
            A4 · 150 DPI · 1240 × 1754 pixels · maximum 300 pages per run.
          </p>
          <h3>Capture effects</h3>
          <label>
            Preset
            <select
              value={config.capture}
              onChange={(e) => set({ capture: e.target.value })}
            >
              {[
                ["mixed", "Random phone / scanner / photocopy"],
                ["phone", "Phone · perspective and uneven light"],
                ["scanner", "Scanner"],
                ["photocopy", "Photocopy"],
                ["cropped_scan", "Cropped scan · narrow page margins"],
                ["none", "Clean document"],
              ].map(([v, n]) => (
                <option key={v} value={v}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label>
            Capture strength
            <input
              type="range"
              min="0"
              max="1"
              step=".05"
              value={config.capture_strength}
              onChange={(e) =>
                set({ capture_strength: Number(e.target.value) })
              }
            />
          </label>
          <h3>Composition of the dataset</h3>
          <p className="field-hint">
            Rates are rounded to whole packs. Negative packs have neither
            signatures nor seals; mark counts are capped by eligible packs.
            Faint and handwritten packs can overlap.
          </p>
          {(
            [
              ["capture_percent", "Captured / degraded packs"],
              ["handwritten_percent", "Handwritten fields"],
              ["faint_percent", "Faint signature / seal ink"],
              ["signature_percent", "With signature"],
              ["seal_percent", "With seal"],
              ["negative_percent", "Without signatures and seals"],
            ] as const
          ).map(([key, label]) => (
            <label key={key}>
              {label} · {config[key]}%
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={config[key]}
                onChange={(e) => set({ [key]: Number(e.target.value) })}
              />
            </label>
          ))}
          <h3>Dataset splits</h3>
          <div className="form-grid">
            <label>
              Train %
              <input
                type="number"
                min="1"
                max="100"
                value={config.train_percent}
                onChange={(e) => set({ train_percent: Number(e.target.value) })}
              />
            </label>
            <label>
              Validation %
              <input
                type="number"
                min="0"
                max="99"
                value={config.validation_percent}
                onChange={(e) =>
                  set({ validation_percent: Number(e.target.value) })
                }
              />
            </label>
          </div>
          <p className="field-hint">
            Test: {100 - config.train_percent - config.validation_percent}%.
            Families stay together, so actual proportions may differ. Use at
            least three families for three non-empty splits.
          </p>
          <button
            className="btn primary full-width"
            disabled={
              busy ||
              config.train_percent + config.validation_percent > 100 ||
              config.count * config.pages > 300
            }
            onClick={() =>
              void action(async () => {
                const j = await post<LabJob>("/document-lab/jobs", config);
                setSelected(j.id);
                setPageKey("");
              })
            }
          >
            Generate {config.count} packs · {config.count * config.pages} pages
          </button>
        </section>
        <section className="panel">
          <h2>Runs and page review</h2>
          <select
            aria-label="Document lab run"
            value={job?.id || ""}
            onChange={(e) => {
              setSelected(e.target.value);
              setPageKey("");
            }}
          >
            {jobs.data?.map((j) => (
              <option key={j.id} value={j.id}>
                {j.config.name} · {j.completed}/{j.total} · {j.status}
              </option>
            ))}
          </select>
          {job && (
            <>
              <p role="status">
                {job.status} · {job.completed} / {job.total} pages
              </p>
              {job.error && <p role="alert">{job.error}</p>}
              <div className="button-row">
                {["running", "queued"].includes(job.status) && (
                  <button
                    className="btn"
                    disabled={busy}
                    onClick={() =>
                      void action(() =>
                        post(`/document-lab/jobs/${job.id}/cancel`),
                      )
                    }
                  >
                    Cancel run
                  </button>
                )}
                {["paused", "failed", "cancelled"].includes(job.status) && (
                  <button
                    className="btn"
                    disabled={busy}
                    onClick={() =>
                      void action(() =>
                        post(`/document-lab/jobs/${job.id}/resume`),
                      )
                    }
                  >
                    Resume remaining pages
                  </button>
                )}
                {stopped && job.completed > 0 && (
                  <a className="btn primary" href={job.download_url}>
                    Download images, PDFs and labels
                  </a>
                )}
              </div>
              <p className="field-hint">
                ZIP: YOLO, COCO boxes, OCR JSON, table structure, relationships,
                clean/captured pairs and multi-page PDFs. Review before
                training.
              </p>
              <div className="lab-page-grid">
                {job.pages.map((p) => (
                  <button
                    type="button"
                    className={`lab-page ${page?.document === p.document && page?.page === p.page ? "selected" : ""}`}
                    key={`${p.document}-${p.page}`}
                    onClick={() => setPageKey(`${p.document}-${p.page}`)}
                  >
                    <img
                      loading="lazy"
                      src={`${p.image_url}?r=${p.revision}`}
                      alt={`Pack ${p.document + 1}, page ${p.page + 1}`}
                    />
                    <span>
                      Pack {p.document + 1} · page {p.page + 1}
                      <br />
                      {p.split} · family {p.family + 1}
                      {p.rejected ? " · excluded" : ""}
                    </span>
                  </button>
                ))}
              </div>
              {page && stopped && (
                <SampleAnnotationEditor
                  key={`${job.id}-${page.document}-${page.page}`}
                  endpoint={`/document-lab/jobs/${job.id}/pages/${page.document}/${page.page}`}
                  imageUrl={page.image_url}
                  regenerateEndpoint={`/document-lab/jobs/${job.id}/documents/${page.document}/regenerate`}
                  classes={classes}
                  onSaved={refresh}
                />
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
