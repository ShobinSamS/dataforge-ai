import { useEffect, useState } from "react";
import { api, post } from "../api";
import { fieldTypes } from "../types";
type Row = {
  region_id: string;
  class: string;
  text: string;
  bbox: [number, number, number, number];
};
type RecordData = {
  width: number;
  height: number;
  annotations: Row[];
  revision?: number;
  rejected?: boolean;
  review_note?: string;
};
export default function SampleAnnotationEditor({
  endpoint,
  imageUrl,
  regenerateEndpoint,
  onSaved,
  classes = fieldTypes,
}: {
  endpoint: string;
  imageUrl: string;
  regenerateEndpoint?: string;
  onSaved?: () => void;
  classes?: readonly string[];
}) {
  const [record, setRecord] = useState<RecordData | null>(null),
    [rows, setRows] = useState<Row[]>([]),
    [rejected, setRejected] = useState(false),
    [note, setNote] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [saved, setSaved] = useState("");
  useEffect(() => {
    let active = true;
    setRecord(null);
    setError("");
    setSaved("");
    void api<RecordData>(endpoint)
      .then((r) => {
        if (active) {
          setRecord(r);
          setRows(r.annotations);
          setRejected(!!r.rejected);
          setNote(r.review_note || "");
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [endpoint]);
  const update = (index: number, patch: Partial<Row>) => {
    setRows((current) =>
      current.map((r, i) => (i === index ? { ...r, ...patch } : r)),
    );
    setSaved("");
  };
  async function save() {
    if (!record) return;
    setBusy(true);
    setError("");
    try {
      const r = await api<RecordData>(endpoint, {
        method: "PUT",
        body: JSON.stringify({
          revision: record.revision || 0,
          rejected,
          note,
          annotations: rows.map((r) => ({
            region_id: r.region_id,
            kind: r.class,
            text: r.text,
            bbox: r.bbox,
          })),
        }),
      });
      setRecord({ ...record, ...r });
      setRows(r.annotations);
      setSaved("Annotations saved");
      onSaved?.();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function regenerate() {
    if (!regenerateEndpoint) return;
    setBusy(true);
    setError("");
    try {
      await post(regenerateEndpoint);
      const r = await api<RecordData>(endpoint);
      setRecord(r);
      setRows(r.annotations);
      setRejected(!!r.rejected);
      setSaved("Regenerated with a fresh seed");
      onSaved?.();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="annotation-editor">
      <h3>Edit sample labels</h3>
      {error && (
        <p role="alert" className="inline-error">
          {error}
        </p>
      )}
      {!record && !error && <p>Loading sample annotations…</p>}
      {record && (
        <>
          <div className="annotated-preview" style={{ maxWidth: 650 }}>
            <img
              src={`${imageUrl}?revision=${record.revision || 0}`}
              alt="Editable generated document"
            />
            {rows.map((r) => (
              <div
                key={r.region_id}
                title={`${r.class}: ${r.text}`}
                style={{
                  left: `${(r.bbox[0] / record.width) * 100}%`,
                  top: `${(r.bbox[1] / record.height) * 100}%`,
                  width: `${(r.bbox[2] / record.width) * 100}%`,
                  height: `${(r.bbox[3] / record.height) * 100}%`,
                }}
              />
            ))}
          </div>
          <p className="field-hint">
            Edit class, text and box coordinates. Changed boxes use rectangular
            masks; unchanged boxes retain their ink masks.
          </p>
          <div className="annotation-edit-list">
            {rows.map((r, index) => (
              <div className="annotation-edit-row" key={r.region_id}>
                <strong>{r.region_id}</strong>
                <label>
                  Class
                  <select
                    aria-label={`Class ${r.region_id}`}
                    value={r.class}
                    onChange={(e) => update(index, { class: e.target.value })}
                  >
                    {classes.map((c) => (
                      <option key={c}>{c}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Text
                  <input
                    aria-label={`Text ${r.region_id}`}
                    value={r.text}
                    onChange={(e) => update(index, { text: e.target.value })}
                  />
                </label>
                <div className="annotation-box-inputs">
                  {["X", "Y", "Width", "Height"].map((label, k) => (
                    <label key={label}>
                      {label}
                      <input
                        aria-label={`${label} ${r.region_id}`}
                        type="number"
                        min={k < 2 ? 0 : 1}
                        value={r.bbox[k]}
                        onChange={(e) => {
                          const box = [...r.bbox] as Row["bbox"];
                          box[k] = Number(e.target.value);
                          update(index, { bbox: box });
                        }}
                      />
                    </label>
                  ))}
                </div>
                <button
                  type="button"
                  className="btn small"
                  onClick={() => setRows(rows.filter((_, i) => i !== index))}
                >
                  Remove label
                </button>
              </div>
            ))}
          </div>
          <button
            type="button"
            className="btn"
            disabled={rows.length >= 200}
            onClick={() =>
              setRows([
                ...rows,
                {
                  region_id: `manual_${Date.now()}`,
                  class: "text",
                  text: "",
                  bbox: [20, 20, 100, 40],
                },
              ])
            }
          >
            Add label
          </button>
          <label>
            <input
              type="checkbox"
              checked={rejected}
              onChange={(e) => setRejected(e.target.checked)}
            />
            Exclude this sample from exports
          </label>
          <label>
            Review note
            <input
              value={note}
              maxLength={500}
              onChange={(e) => setNote(e.target.value)}
            />
          </label>
          <div className="button-row">
            <button
              type="button"
              className="btn primary"
              disabled={busy}
              onClick={() => void save()}
            >
              Save label corrections
            </button>
            {regenerateEndpoint && (
              <button
                type="button"
                className="btn"
                disabled={busy}
                onClick={() => void regenerate()}
              >
                Regenerate this document
              </button>
            )}
          </div>
          {saved && <p role="status">{saved}</p>}
        </>
      )}
    </section>
  );
}
