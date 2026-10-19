import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Box,
  Boxes,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Cpu,
  Database,
  FileImage,
  FileText,
  FilePlus2,
  Files,
  FlaskConical,
  FolderOpen,
  Gauge,
  Layers3,
  LayoutDashboard,
  Loader2,
  LockKeyhole,
  Play,
  Plus,
  ScanLine,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Square,
  Trash2,
  UploadCloud,
  Workflow,
  X,
} from "lucide-react";
import { api, post } from "./api";
import type {
  Template,
  Job,
  Region,
  Config,
  Sample,
  Quality,
  System,
  Export as ExportRecord,
} from "./types";
import { fieldTypes } from "./types";
import RegionEditor from "./RegionEditor";
import DocumentAnalysis from "./components/DocumentAnalysis";
import VisualRegions from "./components/VisualRegions";
import TemplateCard from "./components/TemplateCard";
import DeleteDataset from "./components/DeleteDataset";
import SignatureGeneration from "./components/SignatureGeneration";
import RegionRuleControls from "./components/RegionRuleControls";
import DocumentOutputControls from "./components/DocumentOutputControls";
import Dashboard from "./pages/Dashboard";
import TextStudio from "./pages/TextStudio";
import { Badge, Empty, Stat } from "./components/ui";
import type { Page } from "./types";

const navigation = [
  {
    label: "WORKSPACE",
    items: [
      ["Dashboard", LayoutDashboard],
      ["Template library", Files],
      ["Generation studio", Sparkles],
      ["Text datasets", FileText],
      ["Dataset gallery", Database],
    ],
  },
  {
    label: "OPERATIONS",
    items: [
      ["Quality dashboard", ShieldCheck],
      ["Job monitor", Activity],
      ["Export & history", ArrowDownToLine],
    ],
  },
  {
    label: "EXTENSIONS",
    items: [
      ["AI image studio", FileImage],
      ["Agent activity", Workflow],
      ["MCP tools", Boxes],
    ],
  },
] as const;
const defaults: Config = {
  template_id: "",
  name: "Certificate variations",
  count: 100,
  seed: 42,
  blur_probability: 0.2,
  rotation_probability: 0.15,
  rotation_degrees: 3,
  noise_sigma: 0,
  signatures: true,
  signature_style_override: "mixed",
  seals: true,
  qr_codes: true,
  barcodes: false,
  max_retries: 2,
  qr_padding: 0,
  qr_payload_length: 10,
  identifier_length: 10,
  qr_required: false,
};

export default function App() {
  const qc = useQueryClient();
  const [page, setPage] = useState<Page>("Dashboard"),
    [templateId, setTemplateId] = useState(""),
    [jobId, setJobId] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(""),
    [notice, setNotice] = useState(""),
    [search, setSearch] = useState("");
  const { data: templates = [], error: templateError } = useQuery({
    queryKey: ["templates"],
    queryFn: () => api<Template[]>("/templates"),
  });
  const { data: jobs = [] } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api<Job[]>("/jobs"),
    refetchInterval: 2000,
  });
  const { data: system } = useQuery({
    queryKey: ["system"],
    queryFn: () => api<System>("/system"),
    refetchInterval: 10000,
  });
  const { data: exports = [] } = useQuery({
    queryKey: ["exports"],
    queryFn: () => api<ExportRecord[]>("/exports"),
  });
  const selectedTemplate =
    templates.find((t) => t.id === templateId) || templates[0];
  const selectedJob = jobs.find((j) => j.id === jobId) || jobs[0];
  const [analysisPreview, setAnalysisPreview] = useState<Region[]>([]);
  const [qrPreflightState, setQrPreflightState] = useState<
    "checking" | "valid" | "invalid"
  >("checking");
  const [regions, setRegions] = useState<Region[]>([]),
    [selected, setSelected] = useState(""),
    [privacy, setPrivacy] = useState(false),
    [config, setConfig] = useState<Config>(defaults),
    [format, setFormat] = useState("yolo"),
    [exportReview, setExportReview] = useState(false),
    [sampleOffset, setSampleOffset] = useState(0),
    [sampleSelected, setSampleSelected] = useState<Sample | null>(null);
  useEffect(() => {
    if (selectedTemplate) {
      setRegions(structuredClone(selectedTemplate.regions));
      setPrivacy(selectedTemplate.privacy_confirmed);
      setSelected("");
      setConfig((c) => ({ ...c, template_id: selectedTemplate.id }));
    } else {
      setRegions([]);
      setPrivacy(false);
      setSelected("");
      setAnalysisPreview([]);
      setConfig((c) => ({ ...c, template_id: "" }));
    }
  }, [selectedTemplate?.id, selectedTemplate?.revision]);
  useEffect(() => {
    setSampleOffset(0);
    setExportReview(false);
    setSampleSelected(null);
  }, [selectedJob?.id]);
  const { data: samples = [] } = useQuery({
    queryKey: ["samples", selectedJob?.id, sampleOffset],
    queryFn: () =>
      api<Sample[]>(
        `/jobs/${selectedJob!.id}/samples?offset=${sampleOffset}&limit=12`,
      ),
    enabled: !!selectedJob,
    refetchInterval: 3000,
  });
  const { data: quality } = useQuery({
    queryKey: ["quality", selectedJob?.id],
    queryFn: () => api<Quality>(`/jobs/${selectedJob!.id}/quality`),
    enabled: !!selectedJob,
    refetchInterval: 3000,
  });
  const act = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  };
  const go = (p: Page) => {
    setPage(p);
    setError("");
    setNotice("");
    setSearch("");
  };
  const openTemplate = (t: Template) => {
    setTemplateId(t.id);
    go("Template editor");
  };
  const demo = () =>
    act("Preparing demo", async () => {
      const t = await post<Template>("/templates/demo");
      await qc.invalidateQueries({ queryKey: ["templates"] });
      openTemplate(t);
    });
  const upload = (file?: File) => {
    if (file)
      act("Analyzing template", async () => {
        const form = new FormData();
        form.append("file", file);
        const t = await api<Template>("/templates", {
          method: "POST",
          body: form,
        });
        await qc.invalidateQueries({ queryKey: ["templates"] });
        openTemplate(t);
      });
  };
  const save = () =>
    act("Saving regions", async () => {
      await api(`/templates/${selectedTemplate.id}/review`, {
        method: "PUT",
        body: JSON.stringify({
          regions,
          privacy_confirmed: privacy,
          revision: selectedTemplate.revision,
        }),
      });
      await qc.invalidateQueries({ queryKey: ["templates"] });
      setNotice(
        privacy
          ? "Review confirmed. This template is ready for generation."
          : "Draft saved. Confirm privacy review before generation.",
      );
    });
  const run = () =>
    act("Queueing generation", async () => {
      const j = await post<Job>("/jobs", config);
      setJobId(j.id);
      await qc.invalidateQueries({ queryKey: ["jobs"] });
      go("Job monitor");
    });
  const jobAction = (job: Job, action: string) =>
    act(action, async () => {
      await post(`/jobs/${job.id}/${action}`);
      await qc.invalidateQueries({ queryKey: ["jobs"] });
    });
  const datasetDeleted = async (id: string, message: string) => {
    qc.setQueryData<Job[]>(["jobs"], (rows) =>
      rows?.filter((j) => j.id !== id),
    );
    qc.setQueryData<ExportRecord[]>(["exports"], (rows) =>
      rows?.filter((e) => e.job_id !== id),
    );
    qc.removeQueries({ queryKey: ["samples", id] });
    qc.removeQueries({ queryKey: ["quality", id] });
    if (jobId === id) setJobId("");
    setSampleSelected(null);
    setNotice(message);
    await qc.invalidateQueries({ queryKey: ["jobs"] });
    await qc.invalidateQueries({ queryKey: ["exports"] });
  };
  const fixQrJob = (job: Job) => {
    if (!templates.some((t) => t.id === job.template_id)) {
      setError(
        "This job's template is no longer in the library. Select another template to create a corrected job.",
      );
      return;
    }
    setTemplateId(job.template_id);
    setConfig({ ...defaults, ...job.config });
    go("Generation studio");
  };
  const download = () =>
    act("Packaging dataset", async () => {
      const result = await post<{ download_url: string; count: number }>(
        `/jobs/${selectedJob!.id}/exports`,
        { format, review_confirmed: exportReview },
      );
      await qc.invalidateQueries({ queryKey: ["exports"] });
      const a = document.createElement("a");
      a.href = result.download_url;
      a.download = "";
      a.click();
      setNotice(`Export ready: ${result.count} accepted samples.`);
    });
  const updateRegion = (patch: Partial<Region>) => {
    setPrivacy(false);
    setRegions((rs) =>
      rs.map((r) => (r.id === selected ? { ...r, ...patch } : r)),
    );
  };
  const field = regions.find((r) => r.id === selected);
  const allCompleted = jobs.reduce((n, j) => n + j.completed, 0),
    active = jobs.filter((j) =>
      ["queued", "running", "cancelling"].includes(j.status),
    );
  const uploadButton = (
    <label className="btn primary">
      <Plus size={16} /> New template
      <input
        type="file"
        accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff"
        onChange={(e) => {
          upload(e.target.files?.[0]);
          e.target.value = "";
        }}
        hidden
        disabled={!!busy}
      />
    </label>
  );
  const jobPicker = (
    <select
      aria-label="Select dataset"
      className="select dataset-select"
      value={selectedJob?.id || ""}
      onChange={(e) => setJobId(e.target.value)}
    >
      {jobs.map((j) => (
        <option value={j.id} key={j.id}>
          {j.name} · {j.id.slice(0, 6)}
        </option>
      ))}
    </select>
  );
  const title: Partial<Record<Page, [string, string]>> = {
    Dashboard: [
      "Your data. New possibilities.",
      "Build useful training data, with privacy built in.",
    ],
    "Template library": [
      "Template library",
      "Your starting points for consistent synthetic documents.",
    ],
    "Template editor": [
      "Review your template",
      "Verify sensitive regions before generating fictional replacements.",
    ],
    "Generation studio": [
      "Generation studio",
      "Configure a reproducible dataset. Let the local engine do the rest.",
    ],
    "Text datasets": [
      "Synthetic text datasets",
      "Generate, label, validate and export multilingual text locally.",
    ],
    "Dataset gallery": [
      "Dataset gallery",
      "Explore the documents you generated and inspect their labels.",
    ],
    "Annotation preview": [
      "Annotation preview",
      "Inspect mask-derived bounding boxes and generated transcriptions.",
    ],
    "Quality dashboard": [
      "Dataset quality",
      "Measured validation, with clear limits. Every sample matters.",
    ],
    "Job monitor": [
      "Generation jobs",
      "One CPU worker. Live progress. Everything on your machine.",
    ],
    "Export & history": [
      "Export & history",
      "Package reviewed samples for your training pipeline.",
    ],
    Settings: [
      "Application settings",
      "Local resource policy and installed capabilities.",
    ],
  };
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            go("Dashboard");
          }}
        >
          <span className="brand-mark">
            <Layers3 size={23} />
          </span>
          <span>
            DataForge<span className="brand-ai"> AI</span>
          </span>
        </a>
        <div className="workspace-switch">
          <span className="workspace-avatar">D</span>
          <div>
            <strong>Local workspace</strong>
            <small>Personal environment</small>
          </div>
          <ChevronDown size={14} />
        </div>
        <nav>
          {navigation.map((group) => (
            <div className="nav-group" key={group.label}>
              <p>{group.label}</p>
              {group.items.map(([label, Icon]) => (
                <button
                  key={label}
                  className={
                    "nav-link " +
                    (page === label ||
                    (page === "Template editor" &&
                      label === "Template library") ||
                    (page === "Annotation preview" &&
                      label === "Dataset gallery")
                      ? "selected"
                      : "")
                  }
                  onClick={() => go(label)}
                >
                  <Icon size={18} />
                  <span>{label}</span>
                  {label === "Job monitor" && active.length > 0 && (
                    <span className="nav-count">{active.length}</span>
                  )}
                  {group.label === "EXTENSIONS" && (
                    <span className="soon-dot" />
                  )}
                </button>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-card">
            <span className="local-icon">
              <ShieldCheck size={18} />
            </span>
            <div>
              <strong>Private by design</strong>
              <p>Your data stays on this device.</p>
            </div>
            <i className="dot teal" />
          </div>
          <button
            className={"nav-link " + (page === "Settings" ? "selected" : "")}
            onClick={() => go("Settings")}
          >
            <Settings2 size={18} />
            Settings
          </button>
          <button
            className="nav-link"
            onClick={() =>
              window.open("http://127.0.0.1:8000/docs", "_blank", "noopener")
            }
          >
            <CircleHelp size={18} />
            API documentation
            <ArrowUpRight size={14} />
          </button>
          <div className="profile">
            <div className="profile-avatar">LW</div>
            <div>
              <strong>Local user</strong>
              <small>DataForge v0.1 · Proof of concept</small>
            </div>
          </div>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <ChevronRight size={13} />
            <span>{page}</span>
          </div>
          <div className="top-actions">
            <span className="offline-label">
              <i className="dot teal" />
              Local processing
            </span>
            <span className="header-divider" />
            <Cpu size={16} />
            <span>
              {system
                ? `${(system.available_ram_mb / 1024).toFixed(1)} GB available`
                : "Connecting…"}
            </span>
            <span className="avatar">LW</span>
          </div>
        </header>
        <div className="main-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                {page === "Dashboard"
                  ? "YOUR SYNTHETIC DATA WORKSPACE"
                  : "DATAFORGE WORKSPACE"}
              </div>
              <h1>{title[page]?.[0] || page}</h1>
              <p>
                {title[page]?.[1] ||
                  "Optional local integrations for the next phase of DataForge."}
              </p>
            </div>
            <div className="heading-actions">
              {page === "Dashboard" || page === "Template library" ? (
                uploadButton
              ) : page === "Template editor" ? (
                <>
                  <button
                    className="btn"
                    onClick={() => go("Generation studio")}
                  >
                    Generation studio
                    <ArrowRight size={15} />
                  </button>
                  <button
                    className="btn primary"
                    disabled={!!busy}
                    onClick={save}
                  >
                    <Check size={16} />
                    Save review
                  </button>
                </>
              ) : [
                  "Dataset gallery",
                  "Quality dashboard",
                  "Export & history",
                  "Annotation preview",
                ].includes(page) && jobs.length > 0 ? (
                jobPicker
              ) : null}
            </div>
          </div>
          {(error || templateError) && (
            <div role="alert" className="alert error">
              <X size={18} />
              {error || (templateError as Error).message}{" "}
              <button onClick={() => setError("")} aria-label="Dismiss error">
                <X size={14} />
              </button>
            </div>
          )}
          {notice && (
            <div role="status" className="alert success">
              <CheckCircle2 size={18} />
              {notice}
            </div>
          )}
          {busy && (
            <div role="status" className="alert loading">
              <Loader2 className="spin" size={17} />
              {busy}…
            </div>
          )}

          {page === "Dashboard" && (
            <Dashboard
              templates={templates}
              jobs={jobs}
              system={system}
              busy={busy}
              demo={() => demo()}
              go={go}
              setJobId={setJobId}
            />
          )}

          {page === "Template library" && (
            <>
              <div className="section-toolbar">
                <div className="search">
                  <Search size={16} />
                  <input
                    placeholder="Search templates…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                <span className="muted">
                  {templates.length} templates · Single-page documents
                </span>
                <button
                  className="btn"
                  disabled={!!busy}
                  onClick={() => demo()}
                >
                  <FlaskConical size={15} />
                  Add fictional demo
                </button>
              </div>
              <div className="template-grid">
                {templates
                  .filter((t) =>
                    t.name.toLowerCase().includes(search.toLowerCase()),
                  )
                  .map((t) => (
                    <TemplateCard
                      key={t.id}
                      template={t}
                      busy={!!busy}
                      jobCount={
                        jobs.filter((j) => j.template_id === t.id).length
                      }
                      onOpen={openTemplate}
                      onDeleted={async (id, message) => {
                        qc.setQueryData<Template[]>(["templates"], (old) =>
                          old?.filter((item) => item.id !== id),
                        );
                        if (selectedTemplate?.id === id) {
                          setTemplateId("");
                          setRegions([]);
                          setSelected("");
                          setPrivacy(false);
                          setAnalysisPreview([]);
                        }
                        await qc.invalidateQueries({ queryKey: ["templates"] });
                        setNotice(message);
                      }}
                    />
                  ))}
                <label className="upload-tile">
                  <UploadCloud size={30} />
                  <h3>Bring your own document</h3>
                  <p>
                    PDF, PNG, JPG or TIFF
                    <br />
                    One page · up to 20 MB
                  </p>
                  <span className="btn">Choose file</span>
                  <input
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff"
                    hidden
                    onChange={(e) => upload(e.target.files?.[0])}
                    disabled={!!busy}
                  />
                </label>
              </div>
            </>
          )}

          {page === "Template editor" &&
            (selectedTemplate ? (
              <>
                <div className="editor-top">
                  <select
                    className="select"
                    value={selectedTemplate.id}
                    onChange={(e) => setTemplateId(e.target.value)}
                  >
                    {templates.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                  <span className="muted">
                    {selectedTemplate.engine} · v{selectedTemplate.revision}
                  </span>
                  <Badge
                    status={
                      selectedTemplate.privacy_confirmed
                        ? "completed"
                        : "paused"
                    }
                  >
                    {selectedTemplate.privacy_confirmed
                      ? "Review saved"
                      : "Review needed"}
                  </Badge>
                </div>
                <VisualRegions
                  key={`visual-${selectedTemplate.id}`}
                  template={selectedTemplate}
                  regions={regions}
                  onApply={(rs) => {
                    setRegions(rs);
                    setPrivacy(false);
                    setSelected("");
                  }}
                />
                <DocumentAnalysis
                  key={selectedTemplate.id}
                  template={selectedTemplate}
                  regions={regions}
                  onPreview={setAnalysisPreview}
                  onApply={(rs) => {
                    setRegions(rs);
                    setPrivacy(false);
                    setSelected("");
                  }}
                />
                <div className="editor-grid">
                  <RegionEditor
                    template={selectedTemplate}
                    regions={regions}
                    suggestions={analysisPreview}
                    selected={selected}
                    onSelect={setSelected}
                    onChange={(rs) => {
                      setRegions(rs);
                      setPrivacy(false);
                    }}
                  />
                  <aside className="panel field-panel">
                    <div className="panel-title">
                      <h2>Document fields</h2>
                      <Badge>
                        {regions.filter((r) => r.replace).length} selected
                      </Badge>
                    </div>
                    <div className="field-list">
                      {regions.map((r) => (
                        <button
                          key={r.id}
                          onClick={() => setSelected(r.id)}
                          className={
                            "field-row " + (selected === r.id ? "active" : "")
                          }
                        >
                          <span
                            className={
                              "field-dot " + (r.replace ? "teal" : "gray")
                            }
                          />
                          <span>
                            <strong>{r.label}</strong>
                            <small>
                              {r.kind} · {Math.round(r.confidence * 100)}%
                              confidence
                            </small>
                          </span>
                          {r.confirmed && <Check size={14} />}
                        </button>
                      ))}
                    </div>
                    {field ? (
                      <div className="field-properties">
                        <div className="row-between">
                          <h3>Region properties</h3>
                          <button
                            className="icon-button danger"
                            title="Delete region"
                            onClick={() => {
                              setRegions((rs) =>
                                rs.filter((r) => r.id !== selected),
                              );
                              setSelected("");
                              setPrivacy(false);
                            }}
                          >
                            <Trash2 size={15} />
                          </button>
                        </div>
                        <label>
                          Label
                          <input
                            value={field.label}
                            onChange={(e) =>
                              updateRegion({ label: e.target.value })
                            }
                          />
                        </label>
                        <label>
                          Field type
                          <select
                            value={field.kind}
                            onChange={(e) =>
                              updateRegion({
                                kind: e.target.value as Region["kind"],
                                rule: "",
                                rule_resolved_hash: "",
                                rule_options: field.rule_options
                                  ? {
                                      ...field.rule_options,
                                      literal_text: null,
                                      identifier_pattern: [
                                        "text",
                                        "identifier",
                                        "qr",
                                        "barcode",
                                      ].includes(e.target.value)
                                        ? field.rule_options.identifier_pattern
                                        : "",
                                      character_length: [
                                        "text",
                                        "identifier",
                                        "qr",
                                        "barcode",
                                      ].includes(e.target.value)
                                        ? field.rule_options.character_length
                                        : null,
                                    }
                                  : undefined,
                                confirmed: false,
                              })
                            }
                          >
                            {fieldTypes.map((t) => (
                              <option key={t} value={t}>
                                {t === "seal"
                                  ? "seal / stamp"
                                  : t === "portrait"
                                    ? "portrait / photo"
                                    : t}
                              </option>
                            ))}
                          </select>
                        </label>
                        <div className="coordinate-grid">
                          {["X", "Y", "W", "H"].map((v, i) => (
                            <label key={v}>
                              {v}
                              <input
                                type="number"
                                min={i < 2 ? 0 : 4}
                                value={field.box[i]}
                                onChange={(e) => {
                                  const box = [...field.box] as Region["box"];
                                  box[i] = Number(e.target.value);
                                  updateRegion({ box, confirmed: false });
                                }}
                              />
                            </label>
                          ))}
                        </div>
                        <RegionRuleControls
                          key={`${selectedTemplate.id}:${field.id}`}
                          field={field}
                          templateId={selectedTemplate.id}
                          onChange={updateRegion}
                        />
                        {field.pii_value && (
                          <div className="pii-evidence">
                            <strong>
                              Extracted sensitive value:{" "}
                              <code>{field.pii_value}</code>
                            </strong>
                            <p>{field.pii_reason}</p>
                          </div>
                        )}
                        <label className="check-label">
                          <input
                            type="checkbox"
                            checked={field.sensitive}
                            onChange={(e) =>
                              updateRegion({
                                sensitive: e.target.checked,
                                confirmed: false,
                              })
                            }
                          />
                          Contains sensitive content
                        </label>
                        <label className="check-label">
                          <input
                            type="checkbox"
                            checked={field.confirmed}
                            onChange={(e) =>
                              updateRegion({ confirmed: e.target.checked })
                            }
                          />
                          I verified this region
                        </label>
                      </div>
                    ) : (
                      <p className="field-hint">
                        Select a field to edit its type, boundaries and
                        replacement rule. Use + on the canvas to draw a region.
                      </p>
                    )}
                  </aside>
                </div>
                <div className="review-box">
                  <ShieldCheck size={23} />
                  <div>
                    <h3>Confirm your privacy review</h3>
                    <p>
                      OCR can miss text and visual identifiers. Inspect the
                      entire page, including signatures, stamps and codes.
                      Preserved content will remain in generated images.
                    </p>
                    <label className="check-label">
                      <input
                        type="checkbox"
                        checked={privacy}
                        onChange={(e) => setPrivacy(e.target.checked)}
                      />
                      I reviewed all sensitive regions and verified that each is
                      selected, confirmed and replaced or erased.
                    </label>
                  </div>
                </div>
                <details className="warnings">
                  <summary>
                    Analysis notes ({selectedTemplate.warnings.length})
                  </summary>
                  {selectedTemplate.warnings.map((w, i) => (
                    <p key={i}>{w}</p>
                  ))}
                </details>
              </>
            ) : (
              <Empty
                title="Select a template first"
                body="Upload a document or use the fictional certificate."
                action={
                  <button className="btn primary" onClick={() => demo()}>
                    Load fictional demo
                  </button>
                }
              />
            ))}

          {page === "Generation studio" && (
            <div className="studio-grid">
              <section className="panel form-panel">
                <div className="panel-title">
                  <div>
                    <h2>Dataset configuration</h2>
                    <p>One configuration. Reproducible results.</p>
                  </div>
                  <span className="step-pill">01 / CONFIGURE</span>
                </div>
                <label>
                  Source template
                  <select
                    value={config.template_id}
                    onChange={(e) => {
                      setTemplateId(e.target.value);
                      setConfig((c) => ({ ...c, template_id: e.target.value }));
                    }}
                  >
                    <option value="">Select a reviewed template</option>
                    {templates.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                        {t.privacy_confirmed
                          ? " · Reviewed"
                          : " · Needs review"}
                      </option>
                    ))}
                  </select>
                </label>
                {selectedTemplate && !selectedTemplate.privacy_confirmed && (
                  <div className="alert warning">
                    This template needs a confirmed privacy review.
                    <button
                      className="text-button"
                      onClick={() => go("Template editor")}
                    >
                      Review fields
                      <ArrowRight size={14} />
                    </button>
                  </div>
                )}
                <label>
                  Dataset name
                  <input
                    value={config.name}
                    onChange={(e) =>
                      setConfig((c) => ({ ...c, name: e.target.value }))
                    }
                  />
                </label>
                <div className="form-columns">
                  <label>
                    Number of samples
                    <input
                      type="number"
                      min={1}
                      max={2000}
                      value={config.count}
                      onChange={(e) =>
                        setConfig((c) => ({
                          ...c,
                          count: Number(e.target.value),
                        }))
                      }
                    />
                    <small>1–2,000 per job</small>
                  </label>
                  <label>
                    Random seed
                    <input
                      type="number"
                      min={0}
                      value={config.seed}
                      onChange={(e) =>
                        setConfig((c) => ({
                          ...c,
                          seed: Number(e.target.value),
                        }))
                      }
                    />
                    <small>Same seed + config = same output</small>
                  </label>
                </div>
                <div className="section-divider" />
                <h3>Procedural assets</h3>
                <p className="muted">
                  Add assets only within matching, reviewed template regions.
                </p>
                <div className="asset-options">
                  {(
                    [
                      [
                        "signatures",
                        "Fictional signatures",
                        "Lettering and connected pen designs",
                      ],
                      [
                        "seals",
                        "Synthetic seals / stamps",
                        "Varied wording, layouts and ink",
                      ],
                      ["qr_codes", "QR codes", "Synthetic record payload"],
                      ["barcodes", "Barcodes", "Code 128 synthetic IDs"],
                    ] as const
                  ).map(([key, label, detail]) => (
                    <label className="asset-option" key={key}>
                      <input
                        type="checkbox"
                        checked={config[key]}
                        onChange={(e) =>
                          setConfig((c) => ({
                            ...c,
                            [key]: e.target.checked,
                            ...(key === "qr_codes" && !e.target.checked
                              ? { qr_required: false }
                              : {}),
                          }))
                        }
                      />
                      <span>
                        <strong>{label}</strong>
                        <small>{detail}</small>
                      </span>
                    </label>
                  ))}
                </div>
                <div className="section-divider" />
                <DocumentOutputControls
                  config={config}
                  template={selectedTemplate}
                  onPreflight={setQrPreflightState}
                  onEditQr={(id) => {
                    go("Template editor");
                    setSelected(id);
                  }}
                  onChange={(patch) => setConfig((c) => ({ ...c, ...patch }))}
                />
                <SignatureGeneration
                  config={config}
                  template={selectedTemplate}
                  onChange={(patch) => setConfig((c) => ({ ...c, ...patch }))}
                />
                <div className="section-divider" />
                <h3>Image variation</h3>
                <p className="muted">
                  Geometry transforms apply to images and masks together.
                </p>
                {(
                  [
                    ["blur_probability", "Blurry samples", 100, "%"],
                    ["rotation_probability", "Rotated samples", 100, "%"],
                    ["rotation_degrees", "Maximum rotation", 1, "°"],
                    ["noise_sigma", "Noise standard deviation", 1, ""],
                  ] as const
                ).map(([key, label, mult, unit]) => (
                  <label className="range-label" key={key}>
                    <span>
                      {label}
                      <b>
                        {Math.round(config[key] * mult)}
                        {unit}
                      </b>
                    </span>
                    <input
                      type="range"
                      min={0}
                      max={
                        key.includes("probability")
                          ? 1
                          : key === "rotation_degrees"
                            ? 8
                            : 12
                      }
                      step={key.includes("probability") ? 0.05 : 1}
                      value={config[key]}
                      onChange={(e) =>
                        setConfig((c) => ({
                          ...c,
                          [key]: Number(e.target.value),
                        }))
                      }
                    />
                  </label>
                ))}
                <button
                  className="btn primary full-width"
                  disabled={
                    !!busy ||
                    !selectedTemplate?.privacy_confirmed ||
                    !config.template_id ||
                    (config.qr_codes && qrPreflightState !== "valid")
                  }
                  onClick={run}
                >
                  <Play size={16} />
                  Generate {config.count.toLocaleString()} samples
                  <ArrowRight size={16} />
                </button>
              </section>
              <div>
                <section className="panel studio-preview">
                  <div className="panel-title">
                    <h2>Source preview</h2>
                    <Badge>LOCAL</Badge>
                  </div>
                  {selectedTemplate ? (
                    <img
                      src={`/api/templates/${selectedTemplate.id}/image`}
                      alt="Selected source template"
                    />
                  ) : (
                    <Empty
                      title="No template selected"
                      body="Choose a source to get started."
                    />
                  )}
                  <button
                    className="text-button"
                    onClick={() => go("Template editor")}
                  >
                    Edit replacement regions
                    <ArrowUpRight size={15} />
                  </button>
                </section>
                <div className="engine-note">
                  <Cpu size={21} />
                  <div>
                    <h3>CPU-friendly by default</h3>
                    <p>
                      A single worker streams images to disk. No diffusion or
                      language model is loaded for this workflow. Jobs can be
                      cancelled and resumed.
                    </p>
                  </div>
                </div>
                <section className="panel small-panel">
                  <h3>What this run produces</h3>
                  <ul className="check-list">
                    <li>
                      <Check size={15} />
                      Synthetic document images
                    </li>
                    <li>
                      <Check size={15} />
                      Instance masks and bounding boxes
                    </li>
                    <li>
                      <Check size={15} />
                      Generated field transcriptions
                    </li>
                    <li>
                      <Check size={15} />
                      Per-sample validation results
                    </li>
                    <li>
                      <Check size={15} />
                      Config, seed and version metadata
                    </li>
                  </ul>
                </section>
              </div>
            </div>
          )}

          {page === "Job monitor" && (
            <section className="panel">
              <div className="panel-title">
                <div>
                  <h2>Generation queue</h2>
                  <p>Progress is saved after each sample.</p>
                </div>
                <Badge>{active.length} active · 1 worker</Badge>
              </div>
              {jobs.length ? (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Dataset / version</th>
                        <th>Status</th>
                        <th>Progress</th>
                        <th>Elapsed</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {jobs.map((j) => (
                        <tr key={j.id}>
                          <td>
                            <strong>{j.name}</strong>
                            <small>
                              {j.id.slice(0, 12)} · seed {j.config.seed}
                            </small>
                            {j.error && (
                              <p className="inline-error">{j.error}</p>
                            )}
                          </td>
                          <td>
                            <Badge status={j.status} />
                          </td>
                          <td className="progress-cell">
                            <div className="row-between">
                              <span>
                                {j.completed} / {j.total}
                              </span>
                              <span>
                                {Math.round((j.completed / j.total) * 100)}%
                              </span>
                            </div>
                            <div className="progress-track">
                              <span
                                style={{
                                  width: `${(j.completed / j.total) * 100}%`,
                                }}
                              />
                            </div>
                          </td>
                          <td>
                            {j.metrics.elapsed_seconds || 0}s
                            <small>
                              {j.metrics.peak_process_rss_mb || "—"} MB peak RSS
                            </small>
                          </td>
                          <td>
                            <div className="table-actions">
                              {["queued", "running"].includes(j.status) && (
                                <button
                                  className="btn small"
                                  onClick={() => jobAction(j, "cancel")}
                                >
                                  <Square size={12} />
                                  Cancel
                                </button>
                              )}
                              {["cancelled", "paused", "failed"].includes(
                                j.status,
                              ) && (
                                <button
                                  className="btn small"
                                  onClick={() =>
                                    /QR region|QR encoding capacity/.test(
                                      j.error,
                                    )
                                      ? fixQrJob(j)
                                      : jobAction(j, "resume")
                                  }
                                >
                                  <Play size={12} />
                                  {/QR region|QR encoding capacity/.test(
                                    j.error,
                                  )
                                    ? "Fix QR settings"
                                    : "Resume"}
                                </button>
                              )}
                              <button
                                className="btn small"
                                onClick={() => {
                                  setJobId(j.id);
                                  go("Dataset gallery");
                                }}
                              >
                                View
                                <ArrowUpRight size={13} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty
                  title="No generation jobs yet"
                  body="Configure your first dataset in the generation studio."
                  action={
                    <button
                      className="btn primary"
                      onClick={() => go("Generation studio")}
                    >
                      Open generation studio
                    </button>
                  }
                />
              )}
            </section>
          )}

          {(page === "Dataset gallery" || page === "Annotation preview") &&
            (selectedJob ? (
              <>
                <div className="section-toolbar">
                  <Badge status={selectedJob.status} />
                  <span className="muted">
                    {selectedJob.completed} samples · {selectedJob.name}
                  </span>
                  <DeleteDataset
                    job={selectedJob}
                    busy={!!busy}
                    onDeleted={datasetDeleted}
                  />
                  <button
                    className="btn"
                    onClick={() => go("Quality dashboard")}
                  >
                    <ShieldCheck size={15} />
                    View quality
                  </button>
                  <button
                    className="btn primary"
                    onClick={() => go("Export & history")}
                  >
                    <ArrowDownToLine size={15} />
                    Export dataset
                  </button>
                </div>
                <div className="gallery-grid">
                  {samples.map((s) => (
                    <button
                      className="sample-card"
                      key={s.id}
                      onClick={() => setSampleSelected(s)}
                    >
                      <div className="sample-thumb">
                        <img
                          src={`/api/samples/${s.id}/image`}
                          alt={`Synthetic sample ${s.index}`}
                        />
                      </div>
                      <div className="row-between">
                        <strong>
                          Sample {String(s.index + 1).padStart(4, "0")}
                        </strong>
                        <Badge
                          status={s.validation.passed ? "completed" : "failed"}
                        >
                          {s.validation.passed ? "Checks passed" : "Rejected"}
                        </Badge>
                      </div>
                      <p>
                        {s.annotations.length} annotated objects
                        <ScanLine size={14} />
                      </p>
                      {s.annotations.some((a) => a.signature) && (
                        <p>
                          Signature:{" "}
                          {s.annotations
                            .filter((a) => a.signature)
                            .map((a) => a.signature!.style.replaceAll("_", " "))
                            .join(", ")}
                        </p>
                      )}
                      {s.annotations.some((a) => a.seal) && (
                        <p>
                          Seal:{" "}
                          {s.annotations
                            .filter((a) => a.seal)
                            .map(
                              (a) =>
                                `${a.seal!.shape} · ${a.seal!.content_mode}`,
                            )
                            .join(", ")}
                        </p>
                      )}
                    </button>
                  ))}
                </div>
                {samples.length === 0 && (
                  <Empty
                    title="No samples available yet"
                    body="Generated images will appear as the worker saves them."
                  />
                )}
                <div className="pagination">
                  <button
                    className="btn small"
                    disabled={sampleOffset === 0}
                    onClick={() => setSampleOffset((n) => Math.max(0, n - 12))}
                  >
                    Previous
                  </button>
                  <span>
                    {sampleOffset + 1}–{sampleOffset + samples.length} of{" "}
                    {selectedJob.completed}
                  </span>
                  <button
                    className="btn small"
                    disabled={sampleOffset + 12 >= selectedJob.completed}
                    onClick={() => setSampleOffset((n) => n + 12)}
                  >
                    Next
                  </button>
                </div>
              </>
            ) : (
              <Empty
                title="Your datasets will appear here"
                body="Start a generation run to build your first collection."
              />
            ))}

          {page === "Quality dashboard" &&
            (selectedJob && quality ? (
              <>
                <div className="stat-grid">
                  <Stat
                    label="Samples validated"
                    value={quality.total}
                    detail="Per-sample validation recorded"
                    icon={ScanLine}
                  />
                  <Stat
                    label="Automated checks passed"
                    value={quality.accepted}
                    detail="Human review is still required"
                    icon={CheckCircle2}
                  />
                  <Stat
                    label="Rejected samples"
                    value={quality.rejected}
                    detail="Excluded from dataset exports"
                    icon={ShieldCheck}
                  />
                  <Stat
                    label="Peak process memory"
                    value={`${quality.metrics.peak_process_rss_mb || 0} MB`}
                    detail={`${quality.metrics.elapsed_seconds || 0}s total measured elapsed`}
                    icon={Cpu}
                  />
                </div>
                <div className="dashboard-columns">
                  <section className="panel chart-panel">
                    <div className="panel-title">
                      <div>
                        <h2>Class distribution</h2>
                        <p>Rendered objects across generated samples.</p>
                      </div>
                    </div>
                    <ResponsiveContainer width="100%" height={270}>
                      <BarChart
                        data={Object.entries(quality.classes).map(
                          ([name, count]) => ({ name, count }),
                        )}
                        margin={{ top: 10, left: -25, right: 15, bottom: 5 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          vertical={false}
                          stroke="#e9edef"
                        />
                        <XAxis
                          dataKey="name"
                          tick={{ fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          tick={{ fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip />
                        <Bar
                          dataKey="count"
                          fill="#159488"
                          radius={[4, 4, 0, 0]}
                          maxBarSize={40}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </section>
                  <section className="panel small-panel">
                    <h2>Validation coverage</h2>
                    <ul className="check-list">
                      {[
                        "Normalized coordinate bounds",
                        "Image / mask alignment",
                        "Rendered field coverage",
                        "Image integrity",
                        "QR decode when present",
                        "Duplicate image hashes",
                      ].map((c) => (
                        <li key={c}>
                          <CheckCircle2 size={16} />
                          {c}
                        </li>
                      ))}
                    </ul>
                    <div className="info-strip">
                      Checks passing does not establish that data is
                      training-ready.
                    </div>
                  </section>
                </div>
                <div className="review-box">
                  <ShieldCheck size={24} />
                  <div>
                    <h3>Additional review required</h3>
                    <p>
                      These checks are not implemented:{" "}
                      {quality.not_checked.join(", ")}. Inspect backgrounds and
                      replacements before exporting. Dataset utility must be
                      evaluated for your task.
                    </p>
                  </div>
                </div>
                {Object.keys(quality.errors).length > 0 && (
                  <section className="panel small-panel">
                    <h3>Rejection reasons</h3>
                    {Object.entries(quality.errors).map(([e, n]) => (
                      <p key={e}>
                        {e} · {n}
                      </p>
                    ))}
                  </section>
                )}
              </>
            ) : (
              <Empty
                title="No quality report yet"
                body="Generate a dataset to inspect validation results."
              />
            ))}

          {page === "Export & history" && (
            <div className="studio-grid">
              <section className="panel form-panel">
                <div className="panel-title">
                  <div>
                    <h2>Prepare dataset export</h2>
                    <p>
                      Only samples that passed automated checks are included.
                    </p>
                  </div>
                  <ArrowDownToLine size={20} />
                </div>
                {selectedJob ? (
                  <>
                    <div className="export-summary">
                      <Database size={24} />
                      <div>
                        <h3>{selectedJob.name}</h3>
                        <p>
                          {quality?.accepted || 0} accepted /{" "}
                          {selectedJob.completed} generated · seed{" "}
                          {selectedJob.config.seed}
                        </p>
                      </div>
                    </div>
                    <label>
                      Annotation format
                      <select
                        value={format}
                        onChange={(e) => setFormat(e.target.value)}
                      >
                        <option value="yolo">YOLO bounding boxes</option>
                        <option value="coco">COCO + segmentation RLE</option>
                        <option value="ocr">OCR / field extraction JSON</option>
                      </select>
                    </label>
                    <div className="export-includes">
                      <h3>Included in every ZIP</h3>
                      <p>
                        Images, instance masks, per-sample metadata, class
                        mappings, generation configuration, random seeds and
                        validation results.
                      </p>
                    </div>
                    <div className="review-box compact">
                      <label className="check-label">
                        <input
                          type="checkbox"
                          checked={exportReview}
                          onChange={(e) => setExportReview(e.target.checked)}
                        />
                        I inspected generated samples for remaining sensitive
                        content and reviewed the validation limitations.
                      </label>
                    </div>
                    <button
                      className="btn primary full-width"
                      disabled={
                        !exportReview ||
                        !!busy ||
                        !["completed", "review_required"].includes(
                          selectedJob.status,
                        )
                      }
                      onClick={download}
                    >
                      <ArrowDownToLine size={16} />
                      Build & download ZIP
                    </button>
                  </>
                ) : (
                  <Empty
                    title="No dataset to export"
                    body="Finish a generation job first."
                  />
                )}
              </section>
              <section className="panel">
                <div className="panel-title">
                  <h2>Export history</h2>
                  <Badge>{exports.length}</Badge>
                </div>
                {exports.length ? (
                  exports.map((e) => (
                    <a
                      className="activity-row"
                      href={e.download_url}
                      key={e.id}
                      download
                    >
                      <span className="file-icon">
                        <Box size={18} />
                      </span>
                      <span>
                        <strong>{e.format.toUpperCase()} dataset</strong>
                        <small>
                          {e.job_id.slice(0, 10)} ·{" "}
                          {new Date(e.created_at).toLocaleDateString()}
                        </small>
                      </span>
                      <ArrowDownToLine size={17} />
                    </a>
                  ))
                ) : (
                  <Empty
                    icon={ArrowDownToLine}
                    title="No exports yet"
                    body="Your local export archives will appear here."
                  />
                )}
              </section>
            </div>
          )}

          {page === "Settings" && (
            <div className="studio-grid">
              <section className="panel form-panel">
                <div className="panel-title">
                  <h2>Local runtime</h2>
                  <Badge status="completed">CPU MODE</Badge>
                </div>
                {[
                  ["API binding", "127.0.0.1:8000"],
                  ["Worker concurrency", "1"],
                  ["Queue capacity", "8 active jobs"],
                  ["RAM safety threshold", "1,500 MB available by default"],
                  ["Storage", "Local disk + SQL metadata"],
                  [
                    "Printed OCR",
                    system?.ocr.paddle_local_models
                      ? "PaddleOCR local models configured"
                      : system?.ocr.tesseract
                        ? "Tesseract available"
                        : "Not installed; native PDF text / manual regions",
                  ],
                  ["Remote inference", "Disabled; local Ollama supported"],
                  ["Authentication", "Loopback-only proof of concept"],
                ].map(([k, v]) => (
                  <div className="setting-row" key={k}>
                    <span>{k}</span>
                    <strong>{v}</strong>
                  </div>
                ))}
                <p className="muted">
                  Configure paths, database and memory policy in .env, then
                  restart the backend. Model files must be provisioned locally.
                </p>
              </section>
              <section className="panel form-panel">
                <div className="panel-title">
                  <h2>Capability status</h2>
                  <Badge>PHASE 1</Badge>
                </div>
                {system &&
                  Object.entries(system.capabilities).map(([k, v]) => (
                    <div className="setting-row" key={k}>
                      <span>{k.replaceAll("_", " ")}</span>
                      <Badge status={v ? "completed" : "neutral"}>
                        {v ? "Available" : "Not implemented"}
                      </Badge>
                    </div>
                  ))}
              </section>
            </div>
          )}

          {["AI image studio", "Agent activity", "MCP tools"].includes(
            page,
          ) && (
            <section className="panel extension-panel">
              <span className="extension-icon">
                {page === "AI image studio" ? (
                  <FileImage size={36} />
                ) : page === "MCP tools" ? (
                  <Boxes size={36} />
                ) : (
                  <Workflow size={36} />
                )}
              </span>
              <Badge>PLANNED EXTENSION</Badge>
              <h2>
                {page === "AI image studio"
                  ? "Local diffusion requires a benchmark first"
                  : page === "Agent activity"
                    ? "Shared local reasoning comes after the core pipeline"
                    : "MCP interoperability is planned"}
              </h2>
              <p>
                {page === "AI image studio"
                  ? "Stable Diffusion 1.5 + LCM is not installed or enabled. The target laptop needs measured 256×256 and 512×512 latency, memory and quality results before enabling image inference."
                  : page === "Agent activity"
                    ? "Qwen text generation is available in Text datasets through local Ollama. LangGraph agents and local RAG are not implemented. The architecture defines future planning nodes sharing one local model."
                    : "No MCP server runs in this proof of concept. The architecture documents typed tool contracts for the existing FastAPI services. This page does not simulate tool calls."}
              </p>
              <button
                className="btn primary"
                onClick={() => go("Generation studio")}
              >
                Use the procedural engine
                <ArrowRight size={16} />
              </button>
            </section>
          )}
          {page === "Text datasets" && <TextStudio />}
          <footer className="footer">
            <span>
              <Layers3 size={13} />
              DataForge AI <b>LOCAL WORKSPACE</b>
            </span>
            <span>
              <i className="dot teal" />
              All processing stays on this device
            </span>
          </footer>
        </div>
      </main>
      <Dialog.Root
        open={!!sampleSelected}
        onOpenChange={(v) => {
          if (!v) setSampleSelected(null);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="modal-overlay" />
          <Dialog.Content className="modal">
            <div className="row-between">
              <Dialog.Title>
                Sample{" "}
                {sampleSelected
                  ? String(sampleSelected.index + 1).padStart(4, "0")
                  : ""}{" "}
                · annotation preview
              </Dialog.Title>
              <Dialog.Close className="icon-button" aria-label="Close preview">
                <X size={20} />
              </Dialog.Close>
            </div>
            <Dialog.Description className="muted">
              Generated values and geometry-derived bounding boxes. Sample
              annotation editing is planned; adjust source regions and
              regenerate for corrections.
            </Dialog.Description>
            {sampleSelected && (
              <div className="preview-grid">
                <div className="annotated-preview">
                  <img
                    src={`/api/samples/${sampleSelected.id}/image`}
                    alt="Generated document"
                  />
                  {sampleSelected.annotations.map((a) => (
                    <div
                      key={a.region_id}
                      title={`${a.class}: ${a.text}`}
                      style={{
                        left: `${(a.bbox[0] / (templates.find((t) => t.id === selectedJob?.template_id)?.width || 1350)) * 100}%`,
                        top: `${(a.bbox[1] / (templates.find((t) => t.id === selectedJob?.template_id)?.height || 960)) * 100}%`,
                        width: `${(a.bbox[2] / (templates.find((t) => t.id === selectedJob?.template_id)?.width || 1350)) * 100}%`,
                        height: `${(a.bbox[3] / (templates.find((t) => t.id === selectedJob?.template_id)?.height || 960)) * 100}%`,
                      }}
                    />
                  ))}
                </div>
                <div className="preview-fields">
                  {sampleSelected.annotations.map((a) => (
                    <div key={a.region_id}>
                      <Badge>{a.class}</Badge>
                      <strong>{a.text}</strong>
                      <small>[{a.bbox.join(", ")}]</small>
                    </div>
                  ))}
                  <Badge
                    status={
                      sampleSelected.validation.passed ? "completed" : "failed"
                    }
                  >
                    {sampleSelected.validation.passed
                      ? "Automated checks passed"
                      : "Rejected"}
                  </Badge>
                  {sampleSelected.validation.errors.map((e) => (
                    <p key={e} className="inline-error">
                      {e}
                    </p>
                  ))}
                </div>
              </div>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
