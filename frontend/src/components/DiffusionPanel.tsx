import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, post } from "../api";

type Kind = "portrait" | "seal_artwork" | "stamp_artwork";
type Asset = { id: string; preview_url: string };
type Job = {
  id: string;
  kind: Kind;
  status: string;
  prompt: string;
  seed: number;
  steps: number;
  step: number;
  error?: string;
  image_url?: string;
  raw_image_url?: string;
  asset?: Asset;
  count?: number;
  completed?: number;
  saved_count?: number;
  batch_index?: number;
  items?: Job[];
  download_url?: string;
  prompt_mode?: "manual" | "qwen";
  generated_prompt?: string;
  prompt_seed?: number;
  prompt_model?: string;
  stage?: string;
  metrics?: {
    elapsed_seconds: number;
    peak_worker_rss_mb: number | null;
    prompt_truncated?: boolean;
    worker_wall_seconds?: number;
    image_wall_seconds?: number;
    prompt_planning_seconds?: number;
  };
};
type Caps = {
  ready: boolean;
  runtime: boolean;
  model_installed: boolean;
  available_ram_mb: number;
  setup_commands: string[];
  prompt_llm?: { installed: boolean; model: string };
};
type PromptExample = {
  generated_prompt: string;
  prompt_seed: number;
  prompt_model: string;
};
const prompts: Record<Kind, string> = {
  portrait:
    "An adult South Asian woman, short dark hair, business casual clothing, neutral expression, realistic portrait",
  seal_artwork:
    "A cedar tree above two small leaves, symmetrical botanical emblem",
  stamp_artwork:
    "A fictional coastal lighthouse with waves and seabirds, fine engraved illustration",
};
const titles: Record<Kind, string> = {
  portrait: "Fictional person",
  seal_artwork: "Seal center artwork",
  stamp_artwork: "Stamp illustration",
};
const randomBriefs: Record<Kind, string> = {
  portrait:
    "One anonymous fictional adult in a realistic portrait. Choose a gender, adult age, skin tone, facial features, hairstyle and business-casual outfit; vary these between images.",
  seal_artwork:
    "Invent varied botanical, geometric or animal emblems for fictional company seals. Simple isolated monochrome artwork without lettering.",
  stamp_artwork:
    "Invent varied scenery, plants, wildlife, architecture or transport illustrations for fictional stamps. Vintage engraving without lettering.",
};
const terminal = (status: string) =>
  ["completed", "failed", "cancelled"].includes(status);

export default function DiffusionPanel({
  kind: fixedKind,
  onUse,
  onUseMany,
}: {
  kind?: Kind;
  onUse?: (asset: Asset) => void;
  onUseMany?: (assets: Asset[]) => void;
}) {
  const client = useQueryClient();
  const [kind, setKind] = useState<Kind>(fixedKind || "portrait");
  const [promptMode, setPromptMode] = useState<"manual" | "qwen">("qwen");
  const [prompt, setPrompt] = useState(randomBriefs[fixedKind || "portrait"]);
  const [promptExample, setPromptExample] = useState<PromptExample | null>(
    null,
  );
  const [seed, setSeed] = useState(42),
    [steps, setSteps] = useState(2);
  const [count, setCount] = useState(10),
    [imageIndex, setImageIndex] = useState(0);
  const [background, setBackground] = useState("preserve"),
    [color, setColor] = useState("#ffffff");
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const mounted = useRef(true);
  const promptRevision = useRef(0);
  useEffect(() => {
    promptRevision.current++;
    setPromptExample(null);
  }, [kind, prompt, promptMode]);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const caps = useQuery({
    queryKey: ["diffusion-capabilities"],
    queryFn: () => api<Caps>("/diffusion/capabilities"),
  });
  const jobs = useQuery({
    queryKey: ["diffusion-jobs"],
    queryFn: () => api<Job[]>("/diffusion/jobs"),
    refetchInterval: (query) =>
      Array.isArray(query.state.data) &&
      query.state.data.some((j) => !terminal(j.status))
        ? 1500
        : false,
  });
  const rows = Array.isArray(jobs.data)
    ? jobs.data.filter((j) => !fixedKind || j.kind === fixedKind)
    : [];
  const job = rows.find((j) => j.id === selected);
  const completedItems =
    job?.items?.filter((item) => item.status === "completed") || [];
  const preview =
    (job?.count || 1) > 1
      ? completedItems.find((item) => item.batch_index === imageIndex) ||
        completedItems[0]
      : job;
  const elapsed = completedItems.reduce(
    (sum, item) =>
      sum +
      (item.metrics?.image_wall_seconds ||
        item.metrics?.worker_wall_seconds ||
        item.metrics?.elapsed_seconds ||
        0),
    0,
  );
  const refresh = () =>
    client.invalidateQueries({ queryKey: ["diffusion-jobs"] });
  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (e) {
      if (mounted.current) setError((e as Error).message);
    } finally {
      if (mounted.current) setBusy(false);
    }
  };
  return (
    <div className="diffusion-panel">
      <h3>Stable Diffusion · local CPU preview</h3>
      <p className="field-hint">
        Generate 1–100 images in a run, one 512 × 512 image at a time. Each
        image uses a different seed. Larger batches can take over an hour on
        CPU. Keep DataForge running; you can leave this page and return to its
        progress.
      </p>
      {(caps.error || jobs.error) && (
        <p role="alert">{(caps.error || jobs.error)?.message}</p>
      )}
      {caps.data && !caps.data.ready && (
        <div className="notice">
          <p>
            {!caps.data.runtime
              ? "Optional image runtime is not installed."
              : "SD-Turbo model is not installed."}
          </p>
          <p>
            Run these commands in the project folder, then check setup again:
          </p>
          {caps.data.setup_commands?.map((command) => (
            <pre key={command}>
              <code>{command}</code>
            </pre>
          ))}
        </div>
      )}
      <button
        type="button"
        className="btn"
        onClick={() => {
          void caps.refetch();
          void refresh();
        }}
      >
        Check setup / refresh
      </button>
      {caps.data?.ready && (
        <p className="field-hint">
          SD-Turbo ready · CPU ·{" "}
          {Math.round((caps.data.available_ram_mb / 1024) * 10) / 10} GB RAM
          available
        </p>
      )}
      {!fixedKind && (
        <label>
          Generate artwork for
          <select
            value={kind}
            onChange={(e) => {
              const value = e.target.value as Kind;
              setKind(value);
              setPrompt(
                promptMode === "qwen" ? randomBriefs[value] : prompts[value],
              );
              setPromptExample(null);
              setSelected(null);
              setMessage("");
            }}
          >
            {Object.entries(titles).map(([value, title]) => (
              <option key={value} value={value}>
                {title}
              </option>
            ))}
          </select>
        </label>
      )}
      <label>
        Prompt mode
        <select
          value={promptMode}
          onChange={(e) => {
            const mode = e.target.value as "manual" | "qwen";
            setPromptMode(mode);
            setPromptExample(null);
            setPrompt((current) =>
              current === prompts[kind] || current === randomBriefs[kind]
                ? mode === "qwen"
                  ? randomBriefs[kind]
                  : prompts[kind]
                : current,
            );
          }}
        >
          <option value="qwen">Qwen variation per image</option>
          <option value="manual">Exact/manual prompt</option>
        </select>
      </label>
      {promptMode === "qwen" && (
        <p className="field-hint">
          Local Qwen writes a fresh description for every image, keeping your
          explicit constraints and varying unspecified details. Each run
          receives a new prompt variation seed. Prompts are saved with the
          images.{" "}
          {caps.data?.prompt_llm?.installed
            ? `${caps.data.prompt_llm.model} is available.`
            : "Start local Ollama/Qwen, or choose Exact/manual prompt."}
        </p>
      )}
      <label>
        {promptMode === "qwen" ? "Image brief" : "Image description"}
        <textarea
          rows={3}
          maxLength={600}
          value={prompt}
          onChange={(e) => {
            setPrompt(e.target.value);
            setPromptExample(null);
          }}
        />
      </label>
      {promptMode === "qwen" && (
        <>
          <button
            type="button"
            className="btn"
            disabled={
              busy ||
              !caps.data?.prompt_llm?.installed ||
              prompt.trim().length < 3
            }
            onClick={() =>
              void run(async () => {
                const revision = promptRevision.current;
                const example = await post<PromptExample>(
                  "/diffusion/prompts/preview",
                  { kind, prompt, prompt_mode: "qwen", count: 1, seed, steps },
                );
                if (mounted.current && revision === promptRevision.current)
                  setPromptExample(example);
              })
            }
          >
            Preview sample Qwen prompt
          </button>
          {promptExample && (
            <div className="diffusion-result">
              <strong>Sample Qwen description</strong>
              <p>{promptExample.generated_prompt}</p>
              <p className="field-hint">
                Example only. Generation creates a fresh description for each
                image.
              </p>
            </div>
          )}
        </>
      )}
      <p className="field-hint">
        {kind === "portrait"
          ? "Describe a fictional adult's appearance, clothing and lighting."
          : "Describe the illustration only. Exact wording, denominations and borders are added by the document renderer. Generated artwork may still contain unwanted marks; inspect the preview."}
      </p>
      <div className="diffusion-inputs">
        <label>
          Number of images
          <input
            type="number"
            min={1}
            max={100}
            step={1}
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
          />
        </label>
        <label>
          Image seed
          <input
            type="number"
            min={0}
            max={2147483647}
            value={seed}
            onChange={(e) => setSeed(Number(e.target.value))}
          />
        </label>
        <label>
          Diffusion steps
          <select
            value={steps}
            onChange={(e) => setSteps(Number(e.target.value))}
          >
            {[1, 2, 3, 4].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="rule-buttons" aria-label="Image count presets">
        {[1, 10, 50, 100].map((value) => (
          <button
            type="button"
            className="btn"
            aria-pressed={count === value}
            key={value}
            onClick={() => setCount(value)}
          >
            {value} {value === 1 ? "image" : "images"}
          </button>
        ))}
      </div>
      {kind !== "seal_artwork" && (
        <>
          <label>
            Generated image background
            <select
              value={background}
              onChange={(e) => setBackground(e.target.value)}
            >
              <option value="preserve">Keep generated background</option>
              <option value="transparent">
                Remove background · approximate
              </option>
              <option value="solid">Replace with a color · approximate</option>
            </select>
          </label>
          {background === "solid" && (
            <label>
              Generated background color
              <input
                type="color"
                value={color}
                onChange={(e) => setColor(e.target.value)}
              />
            </label>
          )}
        </>
      )}
      {kind === "seal_artwork" && (
        <p className="field-hint">
          Dark artwork is converted to transparent ink. Use this with a circular
          or oval seal.
        </p>
      )}
      <button
        type="button"
        className="btn primary"
        disabled={
          busy ||
          !caps.data?.ready ||
          (promptMode === "qwen" && !caps.data?.prompt_llm?.installed) ||
          prompt.trim().length < 3 ||
          !Number.isInteger(count) ||
          count < 1 ||
          count > 100 ||
          (!!job && !terminal(job.status))
        }
        onClick={() =>
          void run(async () => {
            const result = await post<Job>("/diffusion/jobs", {
              kind,
              prompt,
              seed,
              steps,
              count,
              prompt_mode: promptMode,
              background: kind === "seal_artwork" ? "preserve" : background,
              background_color: color,
            });
            if (!mounted.current) return;
            setSelected(result.id);
            setImageIndex(0);
            await refresh();
          })
        }
      >
        {busy
          ? "Working…"
          : count === 1
            ? "Generate image preview"
            : `Generate ${count} images`}
      </button>
      {error && (
        <p role="alert" className="rule-error">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {job && (
        <div className="diffusion-result">
          <p role="status">
            {titles[job.kind]} · {job.status}
            {job.status === "running"
              ? ` · step ${job.step}/${job.steps}`
              : ""}{" "}
            · seed {job.seed}
            {(job.count || 1) > 1 &&
              ` · ${job.completed || 0} / ${job.count} images completed`}
            {job.status === "running" &&
              job.stage === "planning_prompt" &&
              " · Qwen is writing the image description"}
          </p>
          {(job.count || 1) > 1 && (
            <progress
              max={job.count}
              value={job.completed || 0}
              aria-label="Image batch progress"
              style={{ width: "100%" }}
            />
          )}
          {!terminal(job.status) &&
            completedItems.length > 0 &&
            elapsed > 0 && (
              <p className="field-hint">
                About{" "}
                {Math.max(
                  1,
                  Math.ceil(
                    ((elapsed / completedItems.length) *
                      ((job.count || 1) - completedItems.length)) /
                      60,
                  ),
                )}{" "}
                minutes remaining, estimated from completed images.
              </p>
            )}
          {job.error && <p role="alert">{job.error}</p>}
          {(job.count || 1) > 1 &&
            ["failed", "cancelled"].includes(job.status) &&
            (job.completed || 0) < (job.count || 1) && (
              <button
                type="button"
                className="btn"
                disabled={busy}
                onClick={() =>
                  void run(async () => {
                    await post(`/diffusion/jobs/${job.id}/resume`);
                    await refresh();
                  })
                }
              >
                Resume remaining images
              </button>
            )}
          {!terminal(job.status) && (
            <button
              type="button"
              className="btn"
              disabled={busy || job.status === "cancelling"}
              onClick={() =>
                void run(async () => {
                  await post(`/diffusion/jobs/${job.id}/cancel`);
                  await refresh();
                })
              }
            >
              Cancel preview
            </button>
          )}
          {(job.count || 1) > 1 && completedItems.length > 0 && (
            <>
              <div className="rule-buttons">
                <a className="btn" href={job.download_url} download>
                  Download completed images ZIP
                </a>
                <button
                  type="button"
                  className="btn primary"
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      const result = await post<{ assets: Asset[] }>(
                        `/diffusion/jobs/${job.id}/save`,
                      );
                      if (!mounted.current) return;
                      onUseMany?.(result.assets);
                      setMessage(
                        onUseMany
                          ? `${result.assets.length} completed images added to this region's pool.`
                          : `${result.assets.length} completed images saved to the asset library.`,
                      );
                      await refresh();
                    })
                  }
                >
                  {onUseMany
                    ? "Use completed images in this region"
                    : "Save all completed images"}
                </button>
              </div>
              <div className="diffusion-gallery">
                {completedItems.map((item) => (
                  <button
                    type="button"
                    className={`diffusion-thumb ${preview?.id === item.id ? "selected" : ""}`}
                    key={item.id}
                    onClick={() => setImageIndex(item.batch_index || 0)}
                  >
                    <img
                      src={item.image_url}
                      alt={`Batch image ${(item.batch_index || 0) + 1}`}
                      loading="lazy"
                    />
                    <span>
                      Image {(item.batch_index || 0) + 1} · seed {item.seed}
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}
          {preview?.image_url && (
            <>
              <img
                className="diffusion-preview"
                src={preview.image_url}
                alt={`Generated ${titles[job.kind].toLowerCase()} preview`}
              />
              <details>
                <summary>Prompt used for this image</summary>
                <p>{preview.generated_prompt || preview.prompt}</p>
                {preview.prompt_mode === "qwen" && (
                  <p className="field-hint">
                    {preview.prompt_model} · prompt variation seed{" "}
                    {preview.prompt_seed}
                  </p>
                )}
              </details>
              {preview.metrics && (
                <p className="field-hint">
                  {preview.metrics.image_wall_seconds ??
                    preview.metrics.worker_wall_seconds ??
                    preview.metrics.elapsed_seconds}
                  s generation including prompt/model load
                  {preview.metrics.peak_worker_rss_mb != null
                    ? ` · peak worker RAM ${preview.metrics.peak_worker_rss_mb} MB`
                    : " · RAM not recorded"}
                </p>
              )}
              {preview.metrics?.prompt_truncated && (
                <p role="status" className="field-hint">
                  The model shortened this prompt to its token limit. Use a
                  shorter description for better control.
                </p>
              )}
              <div className="rule-buttons">
                <a
                  className="btn"
                  href={preview.image_url}
                  download={`${job.kind}-${preview.seed}.png`}
                >
                  Download PNG
                </a>
                <a
                  className="btn"
                  href={preview.raw_image_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  View original
                </a>
                <button
                  type="button"
                  className="btn primary"
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      const asset = await post<Asset>(
                        `/diffusion/jobs/${preview.id}/save`,
                      );
                      if (!mounted.current) return;
                      onUse?.(asset);
                      setMessage(
                        onUse
                          ? "Generated artwork added to this region."
                          : "Saved to asset library. Select this saved preview from a portrait, stamp or seal region to use it.",
                      );
                      await refresh();
                    })
                  }
                >
                  {onUse
                    ? "Use in this region"
                    : preview.asset
                      ? "Saved to asset library"
                      : "Save to asset library"}
                </button>
              </div>
            </>
          )}
        </div>
      )}
      {rows.length > 0 && (
        <details open={!onUse}>
          <summary>Previous image previews ({rows.length})</summary>
          <div className="diffusion-gallery">
            {rows.map((row) => (
              <button
                type="button"
                className={`diffusion-thumb ${row.id === selected ? "selected" : ""}`}
                key={row.id}
                onClick={() => {
                  setSelected(row.id);
                  setError("");
                  setMessage("");
                }}
              >
                {row.image_url && (
                  <img src={row.image_url} alt="" loading="lazy" />
                )}
                <span>
                  {titles[row.kind]} · {row.status} · seed {row.seed}
                  {(row.count || 1) > 1 &&
                    ` · ${row.completed || 0}/${row.count} images`}
                  {row.asset ? " · saved" : ""}
                </span>
              </button>
            ))}
          </div>
        </details>
      )}
      <p className="field-hint">
        SD-Turbo generates fictional imagery and can produce facial or lettering
        artifacts. Background removal is approximate.{" "}
        <a
          href="https://huggingface.co/stabilityai/sd-turbo"
          target="_blank"
          rel="noreferrer"
        >
          Model details and license
        </a>
        .
      </p>
    </div>
  );
}
