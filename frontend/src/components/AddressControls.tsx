import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post } from "../api";
import type { RuleOptions } from "../types";

const fields = [
  ["street", "Street"],
  ["city", "City / locality"],
  ["state", "State / province"],
  ["country", "Country"],
  ["postal_code", "PIN / ZIP / postal code"],
] as const;
const defaultFormat = "{street}, {city}, {state}, {country}, {postal_code}";
export default function AddressControls({
  options,
  set,
}: {
  options: RuleOptions;
  set: (patch: Partial<RuleOptions>) => void;
}) {
  const { data } = useQuery({
    queryKey: ["address-countries"],
    queryFn: () =>
      api<{ code: string; name: string; reference_rows: number }[]>(
        "/addresses/countries",
      ),
    staleTime: Infinity,
  });
  const countries = Array.isArray(data) ? data : [];
  const format = options.address_format ?? defaultFormat;
  const order = [
    ...new Set(
      [...format.matchAll(/\{(street|city|state|country|postal_code)\}/g)].map(
        (m) => m[1],
      ),
    ),
  ];
  const [preview, setPreview] = useState<{
      text: string;
      country_code: string;
      source: string;
    } | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [seed, setSeed] = useState(42);
  const revision = useRef(0);
  useEffect(() => {
    revision.current++;
    setPreview(null);
    setError("");
  }, [options.address_country, format]);
  const update = (patch: Partial<RuleOptions>) =>
    set({ ...patch, literal_text: null });
  const reorder = (next: string[]) => {
    if (next.length)
      update({
        address_format: next
          .map((f) => `{${f}}`)
          .join(format.includes("\n") ? "\n" : ", "),
      });
  };
  return (
    <div className="address-controls">
      <label>
        Address country
        <select
          value={options.address_country || ""}
          onChange={(e) => update({ address_country: e.target.value })}
        >
          <option value="">
            Legacy fictional placeholder · choose a country to configure
          </option>
          {countries.map((c) => (
            <option key={c.code} value={c.code}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      <div role="group" aria-label="Address components and order">
        <p className="field-hint">
          Select components, then move them into the order you want.
        </p>
        {[
          ...order,
          ...fields.map(([f]) => f).filter((f) => !order.includes(f)),
        ].map((key) => {
          const entry = fields.find(([f]) => f === key)!;
          const index = order.indexOf(key);
          return (
            <div key={key} className="address-component-row">
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={index >= 0}
                  onChange={(e) =>
                    reorder(
                      e.target.checked
                        ? [...order, key]
                        : order.filter((f) => f !== key),
                    )
                  }
                />
                {entry[1]}
              </label>
              <button
                type="button"
                className="btn small"
                aria-label={`Move ${key} up`}
                disabled={index <= 0}
                onClick={() => {
                  const next = [...order];
                  [next[index - 1], next[index]] = [
                    next[index],
                    next[index - 1],
                  ];
                  reorder(next);
                }}
              >
                ↑
              </button>
              <button
                type="button"
                className="btn small"
                aria-label={`Move ${key} down`}
                disabled={index < 0 || index === order.length - 1}
                onClick={() => {
                  const next = [...order];
                  [next[index + 1], next[index]] = [
                    next[index],
                    next[index + 1],
                  ];
                  reorder(next);
                }}
              >
                ↓
              </button>
            </div>
          );
        })}
      </div>
      <div className="rule-buttons">
        <button
          type="button"
          className="btn small"
          onClick={() =>
            update({
              address_format: (order.length ? order : fields.map(([f]) => f))
                .map((f) => `{${f}}`)
                .join(", "),
            })
          }
        >
          Single line
        </button>
        <button
          type="button"
          className="btn small"
          onClick={() =>
            update({
              address_format: (order.length ? order : fields.map(([f]) => f))
                .map((f) => `{${f}}`)
                .join("\n"),
            })
          }
        >
          Separate lines
        </button>
      </div>
      <label>
        Address format
        <textarea
          rows={4}
          maxLength={500}
          value={format}
          onChange={(e) => update({ address_format: e.target.value })}
        />
      </label>
      <p className="field-hint">
        You can type custom separators, labels and line breaks. Extra
        placeholders:{" "}
        {"{house_number}, {street_name}, {state_code}, {country_code}"}. Country
        selection and format are reused for a fresh address per sample. Increase
        the field height for multiple lines.
      </p>
      <button
        type="button"
        className="btn"
        disabled={!options.address_country || !!options.literal_text || busy}
        onClick={async () => {
          const current = revision.current;
          setBusy(true);
          setError("");
          try {
            const result = await post<{
              text: string;
              country_code: string;
              source: string;
            }>("/addresses/preview", { options, seed });
            if (current === revision.current) {
              setPreview(result);
              setSeed((s) => s + 1);
            }
          } catch (e) {
            if (current === revision.current)
              setError(
                e instanceof Error ? e.message : "Address preview failed",
              );
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy
          ? "Generating…"
          : preview
            ? "Another address example"
            : "Preview address"}
      </button>
      {preview && (
        <pre className="address-preview" aria-label="Generated address">
          {preview.text}
        </pre>
      )}
      {error && (
        <p role="alert" className="rule-error">
          {error}
        </p>
      )}
      <p className="field-hint">
        Locality, state and postal codes come from a bundled{" "}
        <a href="https://www.geonames.org/" target="_blank" rel="noreferrer">
          GeoNames
        </a>{" "}
        subset (
        <a
          href="https://creativecommons.org/licenses/by/4.0/"
          target="_blank"
          rel="noreferrer"
        >
          CC BY 4.0
        </a>
        ). Streets and house numbers are synthetic. Deliverability is not
        verified. No network request is made during generation.
      </p>
    </div>
  );
}
