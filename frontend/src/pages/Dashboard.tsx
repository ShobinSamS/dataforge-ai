import {
  Activity,
  CheckCircle2,
  ArrowRight,
  ArrowUpRight,
  Cpu,
  Database,
  Files,
  FlaskConical,
  LockKeyhole,
  ScanLine,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  Workflow,
  ArrowDownToLine,
} from "lucide-react";
import { Badge, Empty, Stat } from "../components/ui";
import type { Template, Job, System, Page } from "../types";
interface Props {
  templates: Template[];
  jobs: Job[];
  system?: System;
  busy: string;
  demo: () => void;
  go: (page: Page) => void;
  setJobId: (id: string) => void;
}
export default function Dashboard({
  templates,
  jobs,
  system,
  busy,
  demo,
  go,
  setJobId,
}: Props) {
  const allCompleted = jobs.reduce((n, j) => n + j.completed, 0),
    active = jobs.filter((j) =>
      ["queued", "running", "cancelling"].includes(j.status),
    );
  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <Badge status="hero-badge">
            <Sparkles size={12} /> FROM TEMPLATE TO TRAINING DATA
          </Badge>
          <h2>
            Realistic data.
            <br />
            <span>Entirely fictional.</span>
          </h2>
          <p>
            Turn one document into a reproducible dataset.
            <br />
            Review your fields, generate variations, export precise labels.
          </p>
          <div className="hero-buttons">
            <button
              className="btn primary"
              disabled={!!busy}
              onClick={() => demo()}
            >
              Try a fictional template
              <ArrowRight size={16} />
            </button>
            <button
              className="text-button"
              onClick={() => go("Generation studio")}
            >
              Open studio <ArrowUpRight size={15} />
            </button>
          </div>
          <div className="hero-note">
            <LockKeyhole size={13} /> 100% local processing <span>·</span>{" "}
            CPU-first engine <span>·</span> No API keys
          </div>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <div className="visual-grid" />
          <div className="paper paper-back" />
          <div className="paper paper-mid" />
          <div className="paper paper-front">
            <div className="paper-brand">
              NORTHSTAR INSTITUTE <span>✦</span>
            </div>
            <div className="paper-rule" />
            <div className="paper-title">
              Certificate of
              <br />
              completion
            </div>
            <div className="paper-tiny">THIS CERTIFICATE IS PRESENTED TO</div>
            <div className="paper-field">
              Alex Example <span>NAME</span>
            </div>
            <div className="paper-lines">
              <i />
              <i />
            </div>
            <div className="paper-footer">
              <span className="paper-sign">Fictional</span>
              <span className="paper-stamp">
                SAMPLE
                <br />
                ONLY
              </span>
              <div className="paper-qr" />
            </div>
            <div className="paper-bottom">
              SYNTHETIC · FICTIONAL · REPRODUCIBLE
            </div>
          </div>
          <div className="visual-tag">
            <CheckCircle2 size={17} />
            <div>
              <strong>Geometry-derived annotations</strong>
              <small>Images + labels, generated together</small>
            </div>
          </div>
          <div className="floating-tag">
            <ScanLine size={14} /> Field detection & review
          </div>
        </div>
      </section>
      <div className="stat-grid">
        <Stat
          label="Document templates"
          value={templates.length}
          detail={`${templates.filter((t) => t.privacy_confirmed).length} reviewed and ready`}
          icon={Files}
        />
        <Stat
          label="Samples generated"
          value={allCompleted.toLocaleString()}
          detail="Stored locally on disk"
          icon={Database}
        />
        <Stat
          label="Generation jobs"
          value={jobs.length}
          detail={`${active.length} active in the queue`}
          icon={Workflow}
        />
        <Stat
          label="Local CPU worker"
          value="1"
          detail={
            system
              ? `${system.process_rss_mb} MB current API memory`
              : "Waiting for backend connection"
          }
          icon={Cpu}
        />
      </div>
      <div className="dashboard-columns">
        <section className="panel">
          <div className="panel-title">
            <div>
              <h2>Your generation pipeline</h2>
              <p>Four steps from source to synthetic.</p>
            </div>
            <Badge>PROOF OF CONCEPT</Badge>
          </div>
          <div className="pipeline">
            {[
              {
                n: "01",
                title: "Upload a template",
                body: "A certificate, form or document",
                icon: UploadCloud,
                target: "Template library",
              },
              {
                n: "02",
                title: "Review sensitive fields",
                body: "Confirm what gets replaced",
                icon: ScanLine,
                target: "Template editor",
              },
              {
                n: "03",
                title: "Generate variations",
                body: "Seeded values and visual assets",
                icon: Sparkles,
                target: "Generation studio",
              },
              {
                n: "04",
                title: "Validate & export",
                body: "YOLO, COCO or OCR annotations",
                icon: ArrowDownToLine,
                target: "Export & history",
              },
            ].map((s) => (
              <button
                className="pipeline-step"
                key={s.n}
                onClick={() => go(s.target as Page)}
              >
                <span className="step-icon">
                  <s.icon size={19} />
                </span>
                <span className="step-number">{s.n}</span>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
                <ArrowRight size={16} />
              </button>
            ))}
          </div>
          <div className="info-strip">
            <ShieldCheck size={16} /> Human review is required before generation
            and export.
          </div>
        </section>
        <section className="panel recent-panel">
          <div className="panel-title">
            <div>
              <h2>Recent activity</h2>
              <p>Your latest generation runs.</p>
            </div>
            <button className="text-button" onClick={() => go("Job monitor")}>
              View all
              <ArrowUpRight size={14} />
            </button>
          </div>
          {jobs.length ? (
            jobs.slice(0, 3).map((j) => (
              <button
                key={j.id}
                className="activity-row"
                onClick={() => {
                  setJobId(j.id);
                  go("Job monitor");
                }}
              >
                <span className="file-icon">
                  <Database size={19} />
                </span>
                <span>
                  <strong>{j.name}</strong>
                  <small>
                    {j.completed} / {j.total} samples · seed {j.config.seed}
                  </small>
                </span>
                <Badge status={j.status} />
              </button>
            ))
          ) : (
            <Empty
              icon={Activity}
              title="Your first run starts here"
              body="Use the fictional certificate to explore the complete pipeline."
            />
          )}
        </section>
      </div>
      <section className="bottom-banner">
        <div className="banner-icon">
          <FlaskConical size={24} />
        </div>
        <div>
          <h3>Engineered for your machine</h3>
          <p>
            Bounded jobs, deterministic seeds and disk-based outputs. Optional
            AI models remain unloaded.
          </p>
        </div>
        <button className="text-button" onClick={() => go("Settings")}>
          View system status
          <ArrowRight size={16} />
        </button>
      </section>
    </>
  );
}
