import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownToLine,
  CheckCircle2,
  FileText,
  Loader2,
  Play,
  Square,
} from "lucide-react";
import { api, post } from "../api";
import { Badge, Empty, Stat } from "../components/ui";
import type {
  Language,
  TextConfig,
  TextTask,
  TextJob,
  TextRecord,
  TextQuality,
  TextCapabilities,
  TextExport,
} from "../textTypes";

const TASKS: Record<TextTask, string> = {
  classification: "Text classification",
  ner: "Named entity recognition",
  qa: "Q&A pairs",
  instruction: "Instruction–response",
  conversation: "Conversations",
  augmentation: "Text augmentation",
};
const LANGUAGES: Record<Language, string> = {
  en: "English",
  es: "Spanish",
  fr: "French",
  de: "German",
  hi: "Hindi",
};
const DEFAULT: TextConfig = {
  name: "Synthetic text dataset",
  task: "classification",
  backend: "procedural",
  count: 100,
  seed: 42,
  languages: ["en"],
  labels: ["positive", "negative", "neutral"],
  topic: "customer service",
  instructions: "",
  batch_size: 4,
  max_retries: 2,
  source_texts: [],
  augmentations: ["whitespace"],
  class_templates: {},
  qa_answer_bank: {},
  qa_answer_hint: "fictional score expressed in points",
};
const ACTIVE = ["queued", "running", "cancelling"];

function AnnotatedText({
  text,
  entities,
}: {
  text: string;
  entities: NonNullable<TextRecord["entities"]>;
}) {
  const chars = Array.from(text);
  let cursor = 0;
  const parts: React.ReactNode[] = [];
  for (const e of entities) {
    parts.push(chars.slice(cursor, e.start).join(""));
    parts.push(
      <mark key={e.start} title={`${e.label} [${e.start}, ${e.end})`}>
        {chars.slice(e.start, e.end).join("")}
        <small>{e.label}</small>
      </mark>,
    );
    cursor = e.end;
  }
  parts.push(chars.slice(cursor).join(""));
  return <p className="ner-text">{parts}</p>;
}

export default function TextStudio() {
  const qc = useQueryClient();
  const [config, setConfig] = useState<TextConfig>(DEFAULT),
    [selectedId, setSelectedId] = useState(""),
    [offset, setOffset] = useState(0),
    [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [review, setReview] = useState(false),
    [format, setFormat] = useState("jsonl");
  const [sourceJson, setSourceJson] = useState(
    '[\n  {"text": "The helpful team resolved my fictional service request.", "language": "en", "label": "positive"}\n]',
  );
  const [templatesJson, setTemplatesJson] = useState("{}");
  const [answersJson, setAnswersJson] = useState("{}");
  const { data: capabilities } = useQuery({
    queryKey: ["text_capabilities"],
    queryFn: () => api<TextCapabilities>("/text/capabilities"),
    refetchInterval: 15000,
  });
  const { data: jobs = [], error: jobsError } = useQuery({
    queryKey: ["text_jobs"],
    queryFn: () => api<TextJob[]>("/text/jobs"),
    refetchInterval: 2000,
  });
  const job = jobs.find((j) => j.id === selectedId) || jobs[0];
  useEffect(()=>{setReview(false);setOffset(0)},[job?.id]);
  const { data: records } = useQuery({
    queryKey: ["text_records", job?.id, offset],
    queryFn: () =>
      api<{ items: TextRecord[]; total: number }>(
        `/text/jobs/${job!.id}/records?offset=${offset}&limit=10`,
      ),
    enabled: !!job,
    refetchInterval: 2000,
  });
  const { data: quality } = useQuery({
    queryKey: ["text_quality", job?.id],
    queryFn: () => api<TextQuality>(`/text/jobs/${job!.id}/quality`),
    enabled: !!job,
    refetchInterval: 2000,
  });
  const { data: exports = [] } = useQuery({
    queryKey: ["text_exports"],
    queryFn: () => api<TextExport[]>("/text/exports"),
  });
  const update = (patch: Partial<TextConfig>) =>
    setConfig((c) => ({ ...c, ...patch }));
  const act = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  };
  const generate = () =>
    act("Queueing text dataset", async () => {
      const payload = {
        ...config,
        instructions: config.backend === "ollama" ? config.instructions : "",
        source_texts:
          config.task === "augmentation" ? JSON.parse(sourceJson) : [],
        class_templates: JSON.parse(templatesJson),
        qa_answer_bank: config.task === "qa" ? JSON.parse(answersJson) : {},
      };
      const result = await post<TextJob>("/text/jobs", payload);
      setSelectedId(result.id);
      setOffset(0);
      setReview(false);
      await qc.invalidateQueries({ queryKey: ["text_jobs"] });
      setNotice("Text job queued on the shared local CPU worker.");
    });
  const action = (name: "cancel" | "resume") =>
    act(name, async () => {
      await post(`/text/jobs/${job!.id}/${name}`);
      await qc.invalidateQueries({ queryKey: ["text_jobs"] });
    });
  const validate = () =>
    act("Validating saved text", async () => {
      await post(`/text/jobs/${job!.id}/validate`);
      await Promise.all(
        ["text_jobs", "text_quality", "text_records"].map((key) =>
          qc.invalidateQueries({ queryKey: [key] }),
        ),
      );
      setNotice(
        "Saved records were revalidated. Semantic accuracy and privacy still require human review.",
      );
    });
  const download = () =>
    act("Exporting reviewed text", async () => {
      const result = await post<{ download_url: string }>(
        `/text/jobs/${job!.id}/exports`,
        { format, review_confirmed: review },
      );
      const a = document.createElement("a");
      a.href = result.download_url;
      a.download = "";
      a.click();
      await qc.invalidateQueries({ queryKey: ["text_exports"] });
      setNotice(
        "Accepted records exported. Download the manifest alongside the dataset for configuration and validation details.",
      );
    });
  return (
    <div className="text-studio">
      {(error || jobsError) && (
        <div role="alert" className="alert error">
          {error || (jobsError as Error).message}
        </div>
      )}
      {notice && (
        <div role="status" className="alert success">
          <CheckCircle2 size={16} />
          {notice}
        </div>
      )}
      {busy && (
        <div role="status" className="alert">
          <Loader2 className="spin" size={16} />
          {busy}…
        </div>
      )}
      <div className="text-layout">
        <section className="panel form-panel">
          <div className="panel-title">
            <div>
              <h2>Text dataset configuration</h2>
              <p>Task-specific records, labels and Unicode exports.</p>
            </div>
            <FileText size={20} />
          </div>
          <label>
            Dataset name
            <input
              value={config.name}
              onChange={(e) => update({ name: e.target.value })}
              maxLength={100}
            />
          </label>
          <label>
            Dataset task
            <select
              value={config.task}
              onChange={(e) => update({ task: e.target.value as TextTask })}
            >
              {Object.entries(TASKS).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Generation engine
            <select
              value={config.backend}
              onChange={(e) =>
                update({ backend: e.target.value as TextConfig["backend"] })
              }
            >
              <option value="procedural">
                Procedural · authored templates, no model
              </option>
              <option value="ollama">Local Qwen · Ollama</option>
            </select>
          </label>
          <div className="engine-note">
            <div>
              <h3>
                {config.backend === "ollama"
                  ? capabilities?.llm.installed
                    ? `${capabilities.llm.model} available locally`
                    : "Local Qwen unavailable"
                  : "Deterministic offline baseline"}
              </h3>
              <p>
                {config.backend === "ollama"
                  ? "Structured, bounded batches through loopback Ollama. No cloud fallback or model downloads. Inference can be slow on CPU."
                  : "Procedural generation uses a limited authored corpus. Sentiment examples, exact entity spans, extractive Q&A, code-copy instructions and scripted conversations are supported. Use Qwen for contextual variety."}
              </p>
            </div>
          </div>
          <div className="form-columns">
            <label>
              Sample count
              <input
                type="number"
                min={1}
                max={capabilities?.max_samples || 2000}
                value={config.count}
                onChange={(e) => update({ count: Number(e.target.value) })}
              />
              <small>1–{capabilities?.max_samples || 2000} records</small>
            </label>
            <label>
              Random seed
              <input
                type="number"
                min={0}
                max={2147483647}
                value={config.seed}
                onChange={(e) => update({ seed: Number(e.target.value) })}
              />
            </label>
          </div>
          <fieldset className="text-languages">
            <legend>Output languages</legend>
            {Object.entries(LANGUAGES).map(([language, label]) => (
              <label className="check-label" key={language}>
                <input
                  type="checkbox"
                  checked={config.languages.includes(language as Language)}
                  onChange={(e) =>
                    update({
                      languages: e.target.checked
                        ? [...config.languages, language as Language]
                        : config.languages.filter((l) => l !== language),
                    })
                  }
                />
                {label}
              </label>
            ))}
          </fieldset>
          {config.task === "classification" && (
            <>
              <label>
                Classification labels
                <input
                  value={config.labels.join(", ")}
                  onChange={(e) =>
                    update({
                      labels: e.target.value.split(",").map((s) => s.trim()),
                    })
                  }
                />
                <small>
                  Comma-separated. Default procedural labels: positive,
                  negative, neutral.
                </small>
              </label>
              <details className="text-details">
                <summary>Custom procedural class templates</summary>
                <p>
                  JSON: label → language → text. Required for custom procedural
                  classes in every selected language. Optional {"{record}"}{" "}
                  inserts a fictional reference.
                </p>
                <textarea
                  aria-label="Class templates JSON"
                  rows={5}
                  value={templatesJson}
                  onChange={(e) => setTemplatesJson(e.target.value)}
                />
              </details>
            </>
          )}
          {config.backend === "ollama" && (
            <>
              <label>
                Topic / domain
                <input
                  value={config.topic}
                  onChange={(e) => update({ topic: e.target.value })}
                  maxLength={120}
                />
              </label>
              <label>
                Content instructions
                <textarea
                  value={config.instructions}
                  onChange={(e) => update({ instructions: e.target.value })}
                  maxLength={2000}
                  rows={3}
                  placeholder="Describe fictional content, tone or domain. Do not paste private information."
                />
              </label>
            </>
          )}
          {config.task === "qa" && (
            <>
              <label>
                Q&A answer description
                <input
                  value={config.qa_answer_hint || DEFAULT.qa_answer_hint}
                  maxLength={200}
                  onChange={(e) => update({ qa_answer_hint: e.target.value })}
                />
                <small>
                  Describe the fictional answer type for Qwen, such as a service
                  tier or reference code.
                </small>
              </label>
              <label>
                Q&A answer bank JSON
                <textarea
                  rows={4}
                  value={answersJson}
                  onChange={(e) => setAnswersJson(e.target.value)}
                />
                <small>
                  Optional language → answer list, for example{" "}
                  {'{"en":["Fictional Gold Plan"]}'}. Supply all selected
                  languages. Empty uses fictional point scores. Exact values are
                  inserted after generation.
                </small>
              </label>
            </>
          )}
          {config.task === "augmentation" && (
            <>
              <label>
                Source texts JSON
                <textarea
                  aria-label="Source texts JSON"
                  rows={7}
                  value={sourceJson}
                  onChange={(e) => setSourceJson(e.target.value)}
                />
                <small>
                  Each item: text, language and optional label. Supply a source
                  in each selected language; no automatic translation.
                </small>
              </label>
              {config.backend === "procedural" && (
                <fieldset className="text-languages">
                  <legend>Augmentation operations</legend>
                  {(["whitespace", "punctuation", "typos"] as const).map(
                    (op) => (
                      <label className="check-label" key={op}>
                        <input
                          type="checkbox"
                          checked={config.augmentations.includes(op)}
                          onChange={(e) =>
                            update({
                              augmentations: e.target.checked
                                ? [...config.augmentations, op]
                                : config.augmentations.filter((o) => o !== op),
                            })
                          }
                        />
                        {op}
                      </label>
                    ),
                  )}
                </fieldset>
              )}
              <p className="muted">
                Qwen mode paraphrases. Source labels are inherited and require
                semantic review; noise or paraphrasing can change meaning.
                Finite procedural variants may cause duplicate rejection.
              </p>
            </>
          )}
          <div className="form-columns">
            <label>
              Batch size
              <input
                type="number"
                min={1}
                max={8}
                value={config.batch_size}
                onChange={(e) => update({ batch_size: Number(e.target.value) })}
              />
            </label>
            <label>
              Validation retries
              <input
                type="number"
                min={0}
                max={3}
                value={config.max_retries}
                onChange={(e) =>
                  update({ max_retries: Number(e.target.value) })
                }
              />
            </label>
          </div>
          <button
            className="btn primary full-width"
            disabled={
              !!busy ||
              config.languages.length === 0 ||
              (config.backend === "ollama" && !capabilities?.llm.installed)
            }
            onClick={generate}
          >
            <Play size={15} />
            Generate text dataset
          </button>
        </section>
        <div>
          <section className="panel form-panel">
            <div className="panel-title">
              <h2>Text generation jobs</h2>
              <Badge>
                {jobs.filter((j) => ACTIVE.includes(j.status)).length} active
              </Badge>
            </div>
            {jobs.length ? (
              <>
                <label>
                  Selected text dataset
                  <select
                    value={job?.id || ""}
                    onChange={(e) => {
                      setSelectedId(e.target.value);
                      setOffset(0);
                      setReview(false);
                    }}
                  >
                    {jobs.map((j) => (
                      <option value={j.id} key={j.id}>
                        {j.name} · {j.id.slice(0, 6)}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="text-job-info">
                  <Badge status={job.status} />
                  <span>
                    {job.completed} / {job.total} records
                  </span>
                  <span>
                    {job.config.backend} · {job.config.task}
                  </span>
                </div>
                <div className="progress-track">
                  <span
                    style={{ width: `${(job.completed / job.total) * 100}%` }}
                  />
                </div>
                {job.error && <p className="inline-error">{job.error}</p>}
                <div className="text-job-actions">
                  {["queued", "running"].includes(job.status) && (
                    <button
                      className="btn small"
                      disabled={!!busy}
                      onClick={() => action("cancel")}
                    >
                      <Square size={12} />
                      Cancel job
                    </button>
                  )}
                  {["failed", "paused", "cancelled"].includes(job.status) && (
                    <button
                      className="btn small"
                      disabled={!!busy}
                      onClick={() => action("resume")}
                    >
                      <Play size={12} />
                      Resume job
                    </button>
                  )}
                  <button
                    className="btn small"
                    onClick={() => {
                      setConfig(job.config);
                      setSourceJson(
                        JSON.stringify(job.config.source_texts, null, 2),
                      );
                      setTemplatesJson(
                        JSON.stringify(job.config.class_templates, null, 2),
                      );
                      setAnswersJson(
                        JSON.stringify(
                          job.config.qa_answer_bank || {},
                          null,
                          2,
                        ),
                      );
                    }}
                  >
                    Reuse configuration
                  </button>
                </div>
                <p className="muted">
                  {job.metrics.elapsed_seconds || 0}s measured ·{" "}
                  {job.metrics.peak_process_rss_mb || 0} MB maximum observed API
                  RSS. Ollama memory is separate.
                </p>
              </>
            ) : (
              <Empty
                title="No text jobs yet"
                body="Choose a task and generate a dataset. Document generation continues to use its existing pages."
              />
            )}
          </section>
          <section className="panel form-panel text-export-panel">
            <div className="panel-title">
              <h2>Text export & review</h2>
              <ArrowDownToLine size={18} />
            </div>
            {job ? (
              <>
                <label>
                  Text export format
                  <select
                    value={format}
                    onChange={(e) => setFormat(e.target.value)}
                  >
                    <option value="jsonl">JSONL · one record per line</option>
                    <option value="json">JSON · record array</option>
                    <option value="csv">
                      CSV · JSON-encoded content columns
                    </option>
                  </select>
                </label>
                <div className="review-box compact">
                  <label className="check-label">
                    <input
                      type="checkbox"
                      checked={review}
                      onChange={(e) => setReview(e.target.checked)}
                    />
                    I reviewed generated text, labels, languages and privacy
                    limitations before export.
                  </label>
                </div>
                <button
                  className="btn primary full-width"
                  disabled={
                    !!busy ||
                    !review ||
                    !["completed", "review_required"].includes(job.status) ||
                    !quality?.accepted
                  }
                  onClick={download}
                >
                  Download text dataset
                </button>
                <a
                  className="text-manifest"
                  href={`/api/text/jobs/${job.id}/manifest`}
                  download={`text-${job.id}-manifest.json`}
                >
                  Download configuration & quality manifest
                </a>
                <p className="muted">
                  CSV content and nested columns are JSON-encoded to preserve
                  exact Unicode/offsets and avoid spreadsheet formula execution.
                  Decode using the manifest’s column list.
                </p>
              </>
            ) : (
              <p className="muted text-padding">
                Complete a text job to export.
              </p>
            )}
          </section>
          {exports.length > 0 && (
            <section className="panel text-export-panel">
              <div className="panel-title">
                <h2>Text export history</h2>
              </div>
              {exports.slice(0, 6).map((e) => (
                <a
                  className="activity-row"
                  key={e.id}
                  href={e.download_url}
                  download
                >
                  <ArrowDownToLine size={16} />
                  <span>
                    <strong>
                      {e.format.toUpperCase()} · {e.job_id.slice(0, 8)}
                    </strong>
                    <small>{new Date(e.created_at).toLocaleString()}</small>
                  </span>
                </a>
              ))}
            </section>
          )}
        </div>
      </div>
      {job && quality && (
        <>
          <div className="stat-grid text-quality">
            <Stat
              label="Requested records"
              value={quality.requested}
              detail={`${quality.total} processed`}
              icon={FileText}
            />
            <Stat
              label="Automated checks passed"
              value={quality.accepted}
              detail="Human review still required"
              icon={CheckCircle2}
            />
            <Stat
              label="Rejected records"
              value={quality.rejected}
              detail="Excluded from all exports"
              icon={FileText}
            />
            <Stat
              label="Output languages"
              value={Object.keys(quality.languages).length}
              detail={Object.entries(quality.languages)
                .map(([l, n]) => `${l}: ${n}`)
                .join(" · ")}
              icon={FileText}
            />
          </div>
          <div className="panel text-quality-summary">
            <h3>Validation report</h3>
            <p>
              Class distribution:{" "}
              {Object.entries(quality.labels)
                .map(([l, n]) => `${l}: ${n}`)
                .join(" · ") || "Not a classification dataset"}
            </p>
            {Object.entries(quality.errors).map(([e, n]) => (
              <p key={e} className="inline-error">
                {e}: {n}
              </p>
            ))}
            {quality.warnings.map((w) => (
              <p className="muted" key={w}>
                {w}
              </p>
            ))}
          </div>
        </>
      )}
      <section className="panel text-records">
        <div className="panel-title">
          <div>
            <h2>Generated text & automatic labels</h2>
            <p>
              NER and answer offsets use Unicode code points with an exclusive
              end.
            </p>
          </div>
          {job && ["completed", "review_required"].includes(job.status) ? (
            <button className="btn small" disabled={!!busy} onClick={validate}>
              Revalidate records
            </button>
          ) : (
            <Badge>{records?.total || 0} records</Badge>
          )}
        </div>
        {records?.items.length ? (
          records.items.map((row) => (
            <article className="text-record" key={row.id}>
              <div className="row-between">
                <h3>
                  Record {row.index + 1} · {LANGUAGES[row.language]}
                </h3>
                <div className="text-record-badges">
                  {row.label && <Badge>{row.label}</Badge>}
                  <Badge
                    status={row.validation.passed ? "completed" : "failed"}
                  >
                    {row.validation.passed ? "Checks passed" : "Rejected"}
                  </Badge>
                </div>
              </div>
              {row.entities && row.text ? (
                <AnnotatedText text={row.text} entities={row.entities} />
              ) : row.text ? (
                <p className="generated-text">{row.text}</p>
              ) : null}
              {row.question && (
                <>
                  <p className="generated-text">{row.context}</p>
                  <p>
                    <b>Q:</b> {row.question}
                  </p>
                  <p>
                    <b>A:</b> {row.answer}{" "}
                    <small>start: {row.answer_start}</small>
                  </p>
                </>
              )}
              {row.instruction && (
                <>
                  <p>
                    <b>Instruction:</b> {row.instruction}
                  </p>
                  <p>
                    <b>Response:</b> {row.response}
                  </p>
                </>
              )}
              {row.messages?.map((m, i) => (
                <p className="conversation-message" key={i}>
                  <Badge>{m.role}</Badge>
                  {m.content}
                </p>
              ))}
              <small className="muted">
                {row.provenance.engine} · {row.provenance.labels}
              </small>
              {row.validation.errors.map((e) => (
                <p className="inline-error" key={e}>
                  {e}
                </p>
              ))}
              <details className="text-details">
                <summary>Full record, labels & validation</summary>
                <pre>{JSON.stringify(row, null, 2)}</pre>
              </details>
            </article>
          ))
        ) : (
          <Empty
            title="Generated text will appear here"
            body="Records are saved incrementally and previewed in pages of ten."
          />
        )}
        {job && (
          <div className="pagination">
            <button
              className="btn small"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - 10))}
            >
              Previous records
            </button>
            <span>
              {records?.total ? offset + 1 : 0}–
              {offset + (records?.items.length || 0)} of {records?.total || 0}
            </span>
            <button
              className="btn small"
              disabled={offset + 10 >= (records?.total || 0)}
              onClick={() => setOffset(offset + 10)}
            >
              Next records
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
