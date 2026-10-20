import { useEffect, useRef, useState } from "react";
import { post } from "../api";
import type { Region, RuleOptions } from "../types";
import InkOpacityControls from "./InkOpacityControls";

export default function StampControls({
  field,
  options,
  set,
}: {
  field: Region;
  options: RuleOptions;
  set: (patch: Partial<RuleOptions>) => void;
}) {
  const paper = field.kind === "stamp";
  const inkMode =
    options.stamp_ink_mode ||
    (options.stamp_palette && options.stamp_palette !== "black"
      ? "custom"
      : "default");
  const [preview, setPreview] = useState<{
    image: string;
    metadata: { value: string };
  } | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [seed, setSeed] = useState(42);
  const revision = useRef(0);
  const key = JSON.stringify([
    field.id,
    field.kind,
    field.box,
    field.rule,
    options,
  ]);
  useEffect(() => {
    revision.current++;
    setPreview(null);
    setError("");
    return () => {
      revision.current++;
    };
  }, [key]);
  const change = (patch: Partial<RuleOptions>) => set(patch);
  return (
    <>
      <h3>
        {paper ? "Postage / revenue stamp" : "Rubber stamp / approval mark"}
      </h3>
      {paper ? (
        <>
          <p className="field-hint">
            Printed paper stamps with engraved artwork, denominations and
            optional cancellation marks. The perforated paper is opaque; outside
            the paper is transparent. Ink opacity changes the print, not the
            paper.
          </p>
          <label>
            Stamp artwork style
            <select
              value={options.stamp_style || "random"}
              onChange={(e) =>
                change({
                  stamp_style: e.target.value as RuleOptions["stamp_style"],
                })
              }
            >
              {[
                "random",
                "portrait",
                "architecture",
                "botanical",
                "commemorative",
                "revenue",
              ].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <label>
            Stamp print
            <select
              value={inkMode}
              onChange={(e) =>
                change(
                  e.target.value === "default"
                    ? { stamp_ink_mode: "default", stamp_palette: "black" }
                    : { stamp_ink_mode: "custom" },
                )
              }
            >
              <option value="default">Default · dark black</option>
              <option value="custom">Custom color, opacity and finish</option>
            </select>
          </label>
          <label>
            Stamp palette
            <select
              value={options.stamp_palette || "black"}
              onChange={(e) =>
                change({
                  stamp_palette: e.target.value as RuleOptions["stamp_palette"],
                  stamp_ink_mode: "custom",
                })
              }
            >
              {[
                "black",
                "custom",
                "random",
                "sepia",
                "red",
                "blue",
                "green",
                "purple",
                "monochrome",
                "multicolor",
              ].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          {options.stamp_palette === "custom" && (
            <label>
              Custom stamp color
              <input
                type="color"
                value={options.stamp_color || "#000000"}
                onChange={(e) =>
                  change({
                    stamp_color: e.target.value,
                    stamp_ink_mode: "custom",
                  })
                }
              />
            </label>
          )}
          <p className="field-hint">
            Default print uses dark black at full opacity. Custom print uses the
            chosen palette/color and the ink controls below.
          </p>
          <label>
            Issuer (empty = random fictional post)
            <input
              maxLength={80}
              value={options.stamp_issuer || ""}
              placeholder="NORTHSTAR POST"
              onChange={(e) => change({ stamp_issuer: e.target.value })}
            />
          </label>
          <label>
            Stamp caption (empty = vary with artwork)
            <input
              maxLength={100}
              value={options.stamp_caption || ""}
              placeholder="HERITAGE HALL"
              onChange={(e) =>
                change({ stamp_caption: e.target.value, literal_text: null })
              }
            />
          </label>
          <label>
            Denomination (empty = random)
            <input
              maxLength={16}
              value={options.stamp_denomination || ""}
              placeholder="0.15"
              onChange={(e) => change({ stamp_denomination: e.target.value })}
            />
          </label>
          <label className="check-label">
            <input
              type="checkbox"
              checked={options.stamp_perforated ?? true}
              onChange={(e) => change({ stamp_perforated: e.target.checked })}
            />
            Perforated paper edges
          </label>
          <label>
            Paper age · {Math.round((options.stamp_age ?? 0.35) * 100)}%
            <input
              aria-label="Paper age"
              type="range"
              min={0}
              max={100}
              value={Math.round((options.stamp_age ?? 0.35) * 100)}
              onChange={(e) =>
                change({ stamp_age: Number(e.target.value) / 100 })
              }
            />
          </label>
          <label>
            Cancellation mark
            <select
              value={options.stamp_cancellation || "none"}
              onChange={(e) =>
                change({
                  stamp_cancellation: e.target
                    .value as RuleOptions["stamp_cancellation"],
                })
              }
            >
              {["random", "none", "postmark", "waves", "pen"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <p className="field-hint">
            Portrait and revenue artwork can use the approved image pool below.
            Other artwork is generated locally. Use a separate rubber stamp
            region for a separately labeled postmark. Cancellation is off by
            default. Pen and wave cancellations are separate marks on the stamp;
            your signature stays in its own region.
          </p>
        </>
      ) : (
        <>
          <label>
            Rubber stamp preset
            <select
              value=""
              onChange={(e) => {
                if (e.target.value)
                  change({
                    literal_text: null,
                    rubber_stamp_mode: "static",
                    rubber_stamp_text: e.target.value,
                  });
              }}
            >
              <option value="">Choose a preset or edit wording below</option>
              {[
                "RECEIVED",
                "PAID",
                "APPROVED",
                "REJECTED",
                "COPY",
                "CONFIDENTIAL",
                "CANCELLED",
                "DISPATCHED",
              ].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <label>
            Rubber stamp layout
            <select
              value={options.rubber_stamp_style || "boxed"}
              onChange={(e) =>
                change({
                  rubber_stamp_style: e.target
                    .value as RuleOptions["rubber_stamp_style"],
                })
              }
            >
              {[
                "random",
                "boxed",
                "text",
                "round",
                "dated",
                "postmark",
                "waves",
              ].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <label>
            Rubber stamp wording
            <select
              value={options.rubber_stamp_mode || "random"}
              onChange={(e) =>
                change({
                  literal_text: null,
                  rubber_stamp_mode: e.target
                    .value as RuleOptions["rubber_stamp_mode"],
                })
              }
            >
              <option value="random">Random status per sample</option>
              <option value="static">Static wording</option>
              <option value="custom">Custom format</option>
            </select>
          </label>
          {options.rubber_stamp_mode === "static" && (
            <label>
              Rubber stamp text
              <input
                maxLength={100}
                value={options.rubber_stamp_text ?? "RECEIVED"}
                onChange={(e) =>
                  change({
                    rubber_stamp_text: e.target.value,
                    literal_text: null,
                  })
                }
              />
            </label>
          )}
          {options.rubber_stamp_mode === "custom" && (
            <label>
              Rubber stamp format
              <textarea
                maxLength={480}
                value={
                  options.rubber_stamp_format ||
                  "{department}\n{date}\nREF {reference}"
                }
                onChange={(e) =>
                  change({
                    rubber_stamp_format: e.target.value,
                    literal_text: null,
                  })
                }
              />
            </label>
          )}
          <label>
            Rubber stamp ink
            <select
              value={options.rubber_stamp_color || "random"}
              onChange={(e) =>
                change({
                  rubber_stamp_color: e.target
                    .value as RuleOptions["rubber_stamp_color"],
                })
              }
            >
              {[
                "random",
                "red",
                "blue",
                "green",
                "purple",
                "black",
                "brown",
              ].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <p className="field-hint">
            Ink-only marks have no paper background and their own rubber_stamp
            annotation. Postmark draws a postal circle and date; waves draws
            cancellation lines. These layouts supply their own wording.
          </p>
        </>
      )}
      {(!paper || inkMode === "custom") && (
        <InkOpacityControls options={options} set={change} />
      )}
      <button
        type="button"
        className="btn small"
        disabled={busy}
        onClick={async () => {
          const current = revision.current;
          setBusy(true);
          setError("");
          try {
            const result = await post<{
              image: string;
              metadata: { value: string };
            }>("/assets/generate", {
              kind: field.kind,
              options,
              width: field.box[2],
              height: field.box[3],
              seed,
              value: field.rule?.startsWith("literal:")
                ? field.rule.slice(8)
                : null,
            });
            if (current === revision.current) {
              setPreview(result);
              setSeed((n) => n + 1);
            }
          } catch (e) {
            if (current === revision.current)
              setError(e instanceof Error ? e.message : "Stamp preview failed");
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy
          ? "Rendering…"
          : paper
            ? "Preview paper stamp"
            : "Preview rubber stamp"}
      </button>
      {error && (
        <p role="alert" className="inline-error">
          {error}
        </p>
      )}
      {preview && (
        <figure className="seal-preview">
          <img
            src={preview.image}
            alt={
              paper
                ? "Postage or revenue stamp preview"
                : "Rubber stamp preview"
            }
          />
          <pre>{preview.metadata.value}</pre>
        </figure>
      )}
    </>
  );
}
