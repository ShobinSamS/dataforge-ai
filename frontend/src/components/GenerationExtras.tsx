import type { Config, Template } from "../types";
export default function GenerationExtras({
  config,
  template,
  onChange,
}: {
  config: Config;
  template?: Template;
  onChange: (patch: Partial<Config>) => void;
}) {
  const links = config.field_links || [],
    fields = (template?.regions || []).filter(
      (r) => r.action !== "erase" && r.replace,
    );
  const update = (index: number, patch: Partial<(typeof links)[number]>) =>
    onChange({
      field_links: links.map((l, i) => (i === index ? { ...l, ...patch } : l)),
    });
  return (
    <section>
      <h3>Capture simulation</h3>
      <label>
        Camera / scanner preset
        <select
          value={config.capture_profile || "none"}
          onChange={(e) =>
            onChange({
              capture_profile: e.target.value as Config["capture_profile"],
            })
          }
        >
          {[
            ["none", "None · current output"],
            ["phone", "Phone · perspective, light, fold, JPEG"],
            ["scanner", "Scanner"],
            ["photocopy", "Photocopy"],
            ["cropped_scan", "Cropped scan · narrow page margins"],
            ["mixed", "Random capture preset"],
          ].map(([v, n]) => (
            <option value={v} key={v}>
              {n}
            </option>
          ))}
        </select>
      </label>
      {config.capture_profile && config.capture_profile !== "none" && (
        <label>
          Effect strength
          <input
            type="range"
            min="0"
            max="1"
            step=".05"
            value={config.capture_strength ?? 0.5}
            onChange={(e) =>
              onChange({ capture_strength: Number(e.target.value) })
            }
          />
        </label>
      )}
      <details>
        <summary>Relationships between fields ({links.length})</summary>
        <p className="field-hint">
          Copy values into repeated fields or QR/barcode contents. Date rules
          use the source field’s configured date format. Cycles are rejected.
        </p>
        {links.map((link, index) => (
          <div className="panel" key={index}>
            <label>
              Target field
              <select
                aria-label={`Relationship ${index + 1} target`}
                value={link.target}
                onChange={(e) => update(index, { target: e.target.value })}
              >
                <option value="">Choose field</option>
                {fields.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Rule
              <select
                value={link.rule}
                onChange={(e) =>
                  update(index, { rule: e.target.value as typeof link.rule })
                }
              >
                {[
                  ["copy", "Copy / join values"],
                  ["age", "Age from birth date"],
                  ["after_date", "Date after source"],
                  ["sum", "Sum numbers"],
                ].map(([v, n]) => (
                  <option key={v} value={v}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Source fields
              <select
                multiple
                aria-label={`Relationship ${index + 1} sources`}
                value={link.sources}
                onChange={(e) =>
                  update(index, {
                    sources: Array.from(
                      e.target.selectedOptions,
                      (o) => o.value,
                    ),
                  })
                }
              >
                {fields
                  .filter((r) => r.id !== link.target)
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.label}
                    </option>
                  ))}
              </select>
            </label>
            {link.rule === "copy" && (
              <label>
                Join separator
                <input
                  value={link.separator}
                  onChange={(e) => update(index, { separator: e.target.value })}
                />
              </label>
            )}
            {link.rule === "age" && (
              <label>
                Age reference date
                <input
                  type="date"
                  value={link.as_of}
                  onChange={(e) => update(index, { as_of: e.target.value })}
                />
              </label>
            )}
            {link.rule === "after_date" && (
              <label>
                Days after source
                <input
                  type="number"
                  min="1"
                  max="36500"
                  value={link.days}
                  onChange={(e) =>
                    update(index, { days: Number(e.target.value) })
                  }
                />
              </label>
            )}
            <button
              type="button"
              className="btn small"
              onClick={() =>
                onChange({ field_links: links.filter((_, i) => i !== index) })
              }
            >
              Remove relationship
            </button>
          </div>
        ))}
        <button
          type="button"
          className="btn"
          disabled={links.length >= 50 || fields.length < 2}
          onClick={() =>
            onChange({
              field_links: [
                ...links,
                {
                  target: fields[1]?.id || "",
                  sources: fields[0] ? [fields[0].id] : [],
                  rule: "copy",
                  separator: " | ",
                  days: 365,
                  as_of: "2026-01-01",
                },
              ],
            })
          }
        >
          Add relationship
        </button>
      </details>
    </section>
  );
}
