import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post } from "../api";
import type { Region, RuleOptions } from "../types";
import FontControls from "./FontControls";
import AssetStyleControls from "./AssetStyleControls";
import ColorControls from "./ColorControls";
import AddressControls from "./AddressControls";
import DiffusionPanel from "./DiffusionPanel";

export const defaultRuleOptions: RuleOptions = {
  date_format: "yyyy-mm-dd",
  date_start: "2015-01-01",
  date_end: "2025-12-31",
  identifier_pattern: "",
  literal_text: null,
  portrait_source: "illustration",
  portrait_asset_ids: [],
  character_length: null,
  character_set: "alnum",
  font_id: "auto",
  font_size: null,
  text_color: "#000000",
  color_mode: "black",
  font_weight: "auto",
  background_mode: "auto",
  background_color: "#ffffff",
};
interface Portrait {
  id: string;
  preview_url: string;
}
interface Plan {
  region: Region;
  explanation: string;
  engine: string;
  warnings?: string[];
  references?: {
    title: string;
    url: string;
    verified_at: string;
    pattern: string;
  }[];
}

export default function RegionRuleControls({
  field,
  templateId,
  onChange,
}: {
  field: Region;
  templateId?: string;
  onChange: (patch: Partial<Region>) => void;
}) {
  const options = { ...defaultRuleOptions, ...field.rule_options };
  const action = field.action || (field.replace ? "replace" : "keep");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [resolution, setResolution] = useState<Plan | null>(null);
  const [rights, setRights] = useState(false);
  const [online, setOnline] = useState(false);
  const [license, setLicense] = useState("");
  const capabilities = useQuery({
    queryKey: ["portrait-capabilities"],
    queryFn: () =>
      api<{ online_configured: boolean }>("/portraits/capabilities"),
    staleTime: 60_000,
  });
  const change = (patch: Partial<Region>) => {
    onChange({ ...patch, rule: "", rule_resolved_hash: "", confirmed: false });
    setMessage("");
    setError("");
    setResolution(null);
  };
  const setOptions = (patch: Partial<RuleOptions>) =>
    change({
      rule_options: {
        ...options,
        ...patch,
        ...("identifier_pattern" in patch ||
        "character_length" in patch ||
        "character_set" in patch
          ? { literal_text: null }
          : {}),
      },
    });
  const run = async (task: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setMessage("");
    setResolution(null);
    try {
      await task();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setBusy(false);
    }
  };
  const interpret = (engine: "auto" | "local_llm") =>
    run(async () => {
      const result = await post<Plan>("/document-rules/interpret", {
        region: field,
        engine,
      });
      onChange(result.region);
      setResolution(result);
      setMessage(
        `${result.explanation} Review the action, field type and options below, then verify this region.`,
      );
    });
  const addPortraits = (records: Portrait[]) => {
    const unique = records.filter(
      (record) => !options.portrait_asset_ids.includes(record.id),
    );
    if (options.portrait_asset_ids.length + unique.length > 100)
      throw new Error(
        "A pool supports up to 100 images. Remove some images before adding this batch.",
      );
    setOptions({
      portrait_source: "asset_pool",
      portrait_asset_ids: [
        ...options.portrait_asset_ids,
        ...unique.map((record) => record.id),
      ],
    });
    setMessage(
      `${records.length} image${records.length === 1 ? "" : "s"} added. Different samples choose from this pool using the dataset seed.`,
    );
  };

  return (
    <fieldset className="region-rule-controls" disabled={busy} aria-busy={busy}>
      <AssetStyleControls field={field} options={options} onChange={onChange} />
      <label>
        Action
        <select
          value={action}
          onChange={(e) =>
            change({
              action: e.target.value as Region["action"],
              replace: e.target.value !== "keep",
            })
          }
        >
          <option value="replace">Replace with generated content</option>
          <option value="erase">Erase only — no replacement</option>
          <option value="keep">Keep original pixels</option>
        </select>
      </label>
      <label>
        Rule prompt
        <textarea
          rows={3}
          maxLength={2000}
          value={field.rule}
          placeholder="3 uppercase letters and 6 digits; invoice code INV- plus 8 digits; dd/mm/yyyy; remove this completely"
          onChange={(e) => {
            onChange({
              rule: e.target.value,
              rule_resolved_hash: "",
              confirmed: false,
            });
            setMessage("");
            setError("");
            setResolution(null);
          }}
        />
      </label>
      <div className="rule-buttons">
        <button
          type="button"
          className="btn"
          disabled={!field.rule.trim()}
          onClick={() => interpret("auto")}
        >
          Apply rule
        </button>
        <button
          type="button"
          className="btn"
          disabled={!field.rule.trim()}
          onClick={() => interpret("local_llm")}
        >
          Interpret with local Qwen
        </button>
      </div>
      <p className="field-hint">
        Apply a prompt and review the plan. Common rules work immediately; other
        prompts use local Qwen. Changing controls clears the prompt.
      </p>
      {busy && (
        <p role="status" className="field-hint">
          Processing…
        </p>
      )}
      {error && (
        <p role="alert" className="rule-error">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="field-hint">
          {message}
        </p>
      )}
      {resolution && (
        <div className="field-hint" role="status">
          <strong>
            {resolution.engine === "local_qwen"
              ? "Interpreted by local Qwen"
              : resolution.engine === "known_rule_fallback"
                ? "Applied recognized rule fallback"
                : "Applied recognized rule"}
          </strong>
          {resolution.engine === "known_rule_fallback" && (
            <p>{resolution.warnings?.[0]}</p>
          )}
          {resolution.region.rule_options?.identifier_pattern && (
            <p>
              Resolved pattern:{" "}
              <code>{resolution.region.rule_options.identifier_pattern}</code>{" "}
              (no added prefix)
            </p>
          )}
          {resolution.references?.map((reference) => (
            <p key={reference.url}>
              Format reference:{" "}
              <a href={reference.url} target="_blank" rel="noreferrer">
                {reference.title}
              </a>{" "}
              · cached {reference.verified_at}
            </p>
          ))}
        </div>
      )}
      {action === "erase" && (
        <p className="field-hint">
          The selected rectangle is cleared using nearby background color. It
          receives no replacement or object annotation. Complex backgrounds may
          need smaller regions or a cleaned template.
        </p>
      )}
      {action === "keep" && (
        <p className="field-hint">
          Original pixels remain. A region marked sensitive must be replaced or
          erased.
        </p>
      )}
      {action === "replace" && field.kind === "date" && (
        <>
          <label>
            Date format
            <select
              value={options.date_format}
              onChange={(e) =>
                setOptions({
                  date_format: e.target.value as RuleOptions["date_format"],
                })
              }
            >
              {[
                "yyyy-mm-dd",
                "dd/mm/yyyy",
                "mm/dd/yyyy",
                "dd-mm-yyyy",
                "yyyy/mm/dd",
              ].map((format) => (
                <option key={format}>{format}</option>
              ))}
            </select>
          </label>
          <label>
            Earliest date
            <input
              type="date"
              min="1900-01-01"
              max={options.date_end}
              value={options.date_start}
              onChange={(e) => setOptions({ date_start: e.target.value })}
            />
          </label>
          <label>
            Latest date
            <input
              type="date"
              min={options.date_start}
              max="2100-12-31"
              value={options.date_end}
              onChange={(e) => setOptions({ date_end: e.target.value })}
            />
          </label>
        </>
      )}
      {action === "replace" && field.kind === "address" && (
        <AddressControls options={options} set={setOptions} />
      )}
      {action === "replace" &&
        ["identifier", "text", "qr", "barcode"].includes(field.kind) && (
          <>
            <details>
              <summary>Optional custom pattern</summary>
              <label>
                Character pattern
                <input
                  maxLength={256}
                  value={options.identifier_pattern}
                  placeholder="INV-{upper:2}-{digits:6}"
                  onChange={(e) =>
                    setOptions({ identifier_pattern: e.target.value })
                  }
                />
              </label>
              <p className="field-hint">
                Ask Qwen for any custom code format. Templates support literal
                text and{" "}
                {
                  "{upper:N}, {lower:N}, {digits:N}, {alnum:N}, {year}, {month}, {day}"
                }
                . Legacy A/9/X tokens also work. No prefix is added.
              </p>
            </details>
            <label>
              Generated character length (empty = automatic)
              <input
                type="number"
                min={1}
                max={field.kind === "qr" ? 500 : 128}
                value={options.character_length ?? ""}
                onChange={(e) =>
                  setOptions({
                    character_length: e.target.value
                      ? Number(e.target.value)
                      : null,
                  })
                }
              />
            </label>
            <label>
              Character set
              <select
                value={options.character_set || "alnum"}
                onChange={(e) =>
                  setOptions({
                    character_set: e.target
                      .value as RuleOptions["character_set"],
                  })
                }
              >
                <option value="alnum">Uppercase letters and digits</option>
                <option value="digits">Digits</option>
                <option value="upper">Uppercase letters</option>
                <option value="lower">Lowercase letters</option>
              </select>
            </label>
            {field.kind === "qr" && (
              <p className="field-hint">
                A field length here overrides the Generation studio QR payload
                setting. Clear it to use the generation default. Pixel
                dimensions are separate; check QR size in Generation studio
                before queueing.
              </p>
            )}
            <p className="field-hint">
              Leave the pattern empty to generate random values automatically.
              Length and character set control the value. If a pattern is
              provided, its output must match any explicit length. Total output:
              1–{field.kind === "qr" ? 500 : 128} characters.
            </p>
          </>
        )}
      {action === "replace" &&
        [
          "text",
          "name",
          "address",
          "email",
          "phone",
          "date",
          "identifier",
          "signature",
          "qr",
          "barcode",
        ].includes(field.kind) && (
          <label>
            Exact content (empty = generate)
            <textarea
              rows={2}
              maxLength={
                field.kind === "signature"
                  ? 100
                  : field.kind === "qr"
                    ? 500
                    : field.kind === "barcode"
                      ? 128
                      : 1000
              }
              value={options.literal_text || ""}
              placeholder="Type the text you want to place"
              onChange={(e) =>
                setOptions({
                  literal_text: e.target.value || null,
                  identifier_pattern: "",
                  character_length: null,
                })
              }
            />
          </label>
        )}
      {action === "replace" &&
        ![
          "portrait",
          "signature",
          "seal",
          "stamp",
          "rubber_stamp",
          "qr",
          "barcode",
          "drawing",
        ].includes(field.kind) && (
          <FontControls
            field={field}
            options={options}
            templateId={templateId}
            onChange={onChange}
          />
        )}
      {action === "replace" && options.literal_text !== null && (
        <p className="field-hint">Exact text: {options.literal_text}</p>
      )}
      {action === "replace" &&
        ["portrait", "seal", "stamp"].includes(field.kind) && (
          <details>
            <summary>Generate or select Stable Diffusion artwork</summary>
            <DiffusionPanel
              key={`${field.id}:${field.kind}`}
              kind={
                field.kind === "portrait"
                  ? "portrait"
                  : field.kind === "seal"
                    ? "seal_artwork"
                    : "stamp_artwork"
              }
              onUse={(asset) => {
                if (field.kind === "seal")
                  setOptions({
                    seal_artwork_id: asset.id,
                    seal_artwork_ids: [],
                    seal_style: "corporate",
                  });
                else if (!options.portrait_asset_ids.includes(asset.id))
                  addPortraits([asset]);
              }}
              onUseMany={(assets) => {
                if (field.kind === "seal")
                  setOptions({
                    seal_artwork_id: null,
                    seal_artwork_ids: assets.map((asset) => asset.id),
                    seal_style: "corporate",
                  });
                else addPortraits(assets);
              }}
            />
          </details>
        )}
      {action === "replace" &&
        field.kind === "seal" &&
        (options.seal_artwork_id || !!options.seal_artwork_ids?.length) && (
          <div>
            <img
              src={`/api/portraits/${options.seal_artwork_id || options.seal_artwork_ids?.[0]}/image`}
              alt="Selected seal center artwork"
              style={{ width: 96 }}
            />
            <button
              type="button"
              className="btn"
              onClick={() =>
                setOptions({ seal_artwork_id: null, seal_artwork_ids: [] })
              }
            >
              Remove seal center artwork
            </button>
            {!!options.seal_artwork_ids?.length && (
              <p className="field-hint">
                {options.seal_artwork_ids.length} seal emblems in this pool.
                Dataset samples select an emblem using their seed.
              </p>
            )}
          </div>
        )}
      {action === "replace" && ["portrait", "stamp"].includes(field.kind) && (
        <>
          {field.kind === "portrait" && (
            <>
              <label>
                Photo background
                <select
                  value={options.portrait_background || "preserve"}
                  onChange={(e) =>
                    setOptions({
                      portrait_background: e.target
                        .value as RuleOptions["portrait_background"],
                    })
                  }
                >
                  <option value="preserve">
                    Keep original background / PNG transparency
                  </option>
                  <option value="transparent">
                    Remove background · transparent
                  </option>
                  <option value="solid">Replace with a color</option>
                  <option value="random">
                    Random background color per sample
                  </option>
                </select>
              </label>
              {["solid", "random"].includes(
                options.portrait_background || "",
              ) && (
                <ColorControls
                  label="Photo background color"
                  options={{
                    ...options,
                    color_mode:
                      options.portrait_background === "random"
                        ? "random"
                        : "manual",
                    text_color: options.portrait_background_color || "#ffffff",
                    color_palette: options.portrait_background_palette || [
                      "#ffffff",
                      "#d9e8ff",
                      "#ddd9ef",
                      "#ddebd9",
                    ],
                  }}
                  set={(patch) =>
                    setOptions({
                      ...(patch.color_mode
                        ? {
                            portrait_background:
                              patch.color_mode === "random"
                                ? "random"
                                : "solid",
                          }
                        : {}),
                      ...(patch.text_color
                        ? { portrait_background_color: patch.text_color }
                        : {}),
                      ...(patch.color_palette
                        ? { portrait_background_palette: patch.color_palette }
                        : {}),
                    })
                  }
                />
              )}
              {options.portrait_background &&
                options.portrait_background !== "preserve" && (
                  <p className="field-hint">
                    Background removal runs locally and is approximate,
                    especially around hair or busy scenes. Preview the cutout.
                    An existing transparent PNG keeps its supplied edges.
                  </p>
                )}
            </>
          )}
          <label>
            {field.kind === "stamp"
              ? "Stamp artwork source"
              : "Portrait source"}
            <select
              value={options.portrait_source}
              onChange={(e) =>
                setOptions({
                  portrait_source: e.target
                    .value as RuleOptions["portrait_source"],
                })
              }
            >
              <option value="illustration">
                Offline fictional illustration
              </option>
              <option value="asset_pool">Approved photo / image pool</option>
            </select>
          </label>
          {field.kind === "stamp" ? (
            <p className="field-hint">
              Approved images are converted to printed engraving inside portrait
              or revenue stamps. Choose portrait or revenue artwork style to use
              the pool.
            </p>
          ) : (
            <p className="field-hint">
              Offline portraits are drawings. For photographic output, add
              approved photos or externally generated fictional faces. Images
              are cropped to fill the selected rectangle; its annotation covers
              the whole photo.
            </p>
          )}
          <div className="portrait-pool">
            {options.portrait_asset_ids.map((id, index) => (
              <div key={id}>
                <img
                  src={`/api/portraits/${id}/image`}
                  alt={`Portrait pool image ${index + 1}`}
                />
                <button
                  type="button"
                  className="btn"
                  aria-label={`Remove portrait ${index + 1}`}
                  onClick={() =>
                    setOptions({
                      portrait_asset_ids: options.portrait_asset_ids.filter(
                        (v) => v !== id,
                      ),
                    })
                  }
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
          <label className="check-label">
            <input
              type="checkbox"
              checked={rights}
              onChange={(e) => setRights(e.target.checked)}
            />
            I have permission to use these images in this dataset.
          </label>
          <label>
            Permission / attribution note
            <input
              maxLength={1000}
              value={license}
              onChange={(e) => setLicense(e.target.value)}
              placeholder="Image owner, license or generated image source"
            />
          </label>
          <label>
            Add images or ZIP to pool (up to 20 per upload)
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp,.zip,application/zip"
              multiple
              disabled={!rights || options.portrait_asset_ids.length >= 100}
              onChange={(e) => {
                const files = Array.from(e.target.files || []);
                e.target.value = "";
                if (files.length)
                  run(async () => {
                    const form = new FormData();
                    for (const file of files) form.append("files", file);
                    form.append(
                      "max_count",
                      String(
                        Math.min(20, 100 - options.portrait_asset_ids.length),
                      ),
                    );
                    form.append("rights_confirmed", "true");
                    form.append(
                      "license_note",
                      license || "User confirmed permission for dataset use",
                    );
                    const result = await api<{ portraits: Portrait[] }>(
                      "/portraits/batch",
                      {
                        method: "POST",
                        body: form,
                      },
                    );
                    addPortraits(result.portraits);
                  });
              }}
            />
          </label>
          <p className="field-hint">
            {options.portrait_asset_ids.length}/100 selected. Select multiple
            PNG, JPEG or WebP images, or a ZIP containing images. Each image: up
            to 8 MB / 8 megapixels. Combined upload and uncompressed images: up
            to 40 MB. Imports add to the existing pool; invalid or oversized
            batches leave it unchanged.
          </p>
          <details>
            <summary>Optional online portrait import</summary>
            <p className="field-hint">
              Uses an operator-configured image provider. The template and
              prompt stay local. The LLM does not browse or scrape for photos.
            </p>
            {!capabilities.data?.online_configured && (
              <p className="field-hint">
                No online provider configured. Upload an image, or set
                DATAFORGE_ALLOW_ONLINE_PORTRAITS and
                DATAFORGE_PORTRAIT_PROVIDER_URL in .env.
              </p>
            )}
            <label className="check-label">
              <input
                type="checkbox"
                checked={online}
                onChange={(e) => setOnline(e.target.checked)}
              />
              I approve this online download.
            </label>
            <button
              type="button"
              className="btn"
              disabled={
                !capabilities.data?.online_configured ||
                !online ||
                !rights ||
                options.portrait_asset_ids.length >= 100
              }
              onClick={() =>
                run(async () =>
                  addPortraits([
                    await post<Portrait>("/portraits/fetch", {
                      confirm_online: true,
                      rights_confirmed: true,
                      license_note:
                        license ||
                        "User confirmed provider image permission for dataset use",
                    }),
                  ]),
                )
              }
            >
              Fetch from configured provider
            </button>
          </details>
        </>
      )}
    </fieldset>
  );
}
