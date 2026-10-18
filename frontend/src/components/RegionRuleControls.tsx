import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post } from "../api";
import type { Region, RuleOptions } from "../types";
import FontControls from "./FontControls";
import AssetStyleControls from "./AssetStyleControls";

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
  color_mode: "auto",
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
  const addPortrait = (record: Portrait) => {
    if (options.portrait_asset_ids.length >= 20)
      throw new Error("A pool supports up to 20 portraits.");
    setOptions({
      portrait_source: "asset_pool",
      portrait_asset_ids: [...options.portrait_asset_ids, record.id],
    });
    setMessage(
      "Portrait added. Different samples choose from this pool using the dataset seed.",
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
            <p className="field-hint">
              Leave the pattern empty to generate random values automatically.
              Length and character set control the value. If a pattern is
              provided, its output must match any explicit length. Total output:
              1–{field.kind === "qr" ? 500 : 128} characters.
            </p>
          </>
        )}
      {action === "replace" &&
        !["portrait", "signature", "seal", "qr", "barcode"].includes(
          field.kind,
        ) && (
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
      {action === "replace" && field.kind === "portrait" && (
        <>
          <label>
            Portrait source
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
          <p className="field-hint">
            Offline portraits are drawings. For photographic output, add
            approved photos or externally generated fictional faces. Images are
            cropped to fill the selected rectangle; its annotation covers the
            whole photo.
          </p>
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
            Add portrait to pool (up to 20)
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              disabled={!rights || options.portrait_asset_ids.length >= 20}
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (file)
                  run(async () => {
                    const form = new FormData();
                    form.append("file", file);
                    form.append("rights_confirmed", "true");
                    form.append(
                      "license_note",
                      license || "User confirmed permission for dataset use",
                    );
                    addPortrait(
                      await api<Portrait>("/portraits", {
                        method: "POST",
                        body: form,
                      }),
                    );
                  });
              }}
            />
          </label>
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
                options.portrait_asset_ids.length >= 20
              }
              onClick={() =>
                run(async () =>
                  addPortrait(
                    await post<Portrait>("/portraits/fetch", {
                      confirm_online: true,
                      rights_confirmed: true,
                      license_note:
                        license ||
                        "User confirmed provider image permission for dataset use",
                    }),
                  ),
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
