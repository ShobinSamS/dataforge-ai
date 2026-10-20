import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { FilePlus2, X } from "lucide-react";
import { post } from "../api";
import type { Template } from "../types";

export default function BlankCanvasDialog({
  onCreated,
  disabled = false,
}: {
  onCreated: (template: Template) => Promise<void> | void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [form, setForm] = useState({
    name: "Untitled canvas",
    paper: "a4",
    orientation: "portrait",
    unit: "mm",
    width: 210,
    height: 297,
    dpi: 150,
    background: "white",
    background_color: "#ffffff",
    starter: "blank",
  });
  const patch = (value: Partial<typeof form>) =>
    setForm((current) => ({ ...current, ...value }));
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(value) => {
        if (!busy) {
          setOpen(value);
          setError("");
        }
      }}
    >
      <Dialog.Trigger asChild>
        <button className="btn" disabled={disabled}>
          <FilePlus2 size={16} />
          Create from scratch
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="modal-overlay" />
        <Dialog.Content className="modal blank-canvas-dialog">
          <div className="row-between">
            <Dialog.Title>Create a blank canvas</Dialog.Title>
            <Dialog.Close
              className="icon-button"
              aria-label="Close canvas creator"
              disabled={busy}
            >
              <X size={18} />
            </Dialog.Close>
          </div>
          <Dialog.Description>
            Start a document or a reusable asset. Add and position elements,
            draw with the pen, then preview and download a PNG.
          </Dialog.Description>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              try {
                const t = await post<Template>("/templates/blank", form);
                await onCreated(t);
                setOpen(false);
              } catch (e) {
                setError(
                  e instanceof Error ? e.message : "Could not create canvas",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            <fieldset disabled={busy} className="canvas-form-grid">
              <label className="span-two">
                Canvas name
                <input
                  value={form.name}
                  required
                  maxLength={200}
                  onChange={(e) => patch({ name: e.target.value })}
                />
              </label>
              <label>
                Document size
                <select
                  value={form.paper}
                  onChange={(e) => patch({ paper: e.target.value })}
                >
                  <option value="a4">A4 · 210 × 297 mm</option>
                  <option value="a5">A5 · 148 × 210 mm</option>
                  <option value="letter">US Letter</option>
                  <option value="custom">Custom size</option>
                </select>
              </label>
              <label>
                Orientation
                <select
                  value={form.orientation}
                  onChange={(e) => patch({ orientation: e.target.value })}
                >
                  <option value="portrait">Portrait</option>
                  <option value="landscape">Landscape</option>
                </select>
              </label>
              {form.paper === "custom" && (
                <>
                  <label>
                    Size units
                    <select
                      value={form.unit}
                      onChange={(e) => patch({ unit: e.target.value })}
                    >
                      <option value="mm">Millimeters</option>
                      <option value="px">Pixels</option>
                    </select>
                  </label>
                  <div />
                  <label>
                    Width
                    <input
                      type="number"
                      min={1}
                      max={6000}
                      step="any"
                      required
                      value={form.width}
                      onChange={(e) => patch({ width: Number(e.target.value) })}
                    />
                  </label>
                  <label>
                    Height
                    <input
                      type="number"
                      min={1}
                      max={6000}
                      step="any"
                      required
                      value={form.height}
                      onChange={(e) =>
                        patch({ height: Number(e.target.value) })
                      }
                    />
                  </label>
                </>
              )}
              <label>
                Resolution
                <select
                  value={form.dpi}
                  onChange={(e) => patch({ dpi: Number(e.target.value) })}
                >
                  <option value={72}>72 DPI</option>
                  <option value={150}>150 DPI</option>
                  <option value={300}>300 DPI</option>
                </select>
              </label>
              <label>
                Canvas background
                <select
                  value={form.background}
                  onChange={(e) => patch({ background: e.target.value })}
                >
                  <option value="white">White</option>
                  <option value="transparent">
                    Transparent · no background
                  </option>
                  <option value="color">Custom color</option>
                </select>
              </label>
              {form.background === "color" && (
                <label>
                  Background color
                  <input
                    type="color"
                    value={form.background_color}
                    onChange={(e) =>
                      patch({ background_color: e.target.value })
                    }
                  />
                </label>
              )}
              <label className="span-two">
                Start with
                <select
                  value={form.starter}
                  onChange={(e) => patch({ starter: e.target.value })}
                >
                  <option value="blank">Empty document</option>
                  <option value="signature">Signature</option>
                  <option value="text">Text</option>
                  <option value="seal">Seal</option>
                  <option value="portrait">Photo / image</option>
                  <option value="stamp">Postage / revenue stamp</option>
                  <option value="rubber_stamp">Rubber stamp</option>
                  <option value="qr">QR code</option>
                  <option value="barcode">Barcode</option>
                </select>
              </label>
            </fieldset>
            <p className="field-hint">
              A4 is the default. Choose Transparent for assets you will place on
              other images. Maximum 12 megapixels.
            </p>
            {error && (
              <p role="alert" className="rule-error">
                {error}
              </p>
            )}
            <button className="btn primary" disabled={busy}>
              {busy ? "Creating…" : "Create canvas"}
            </button>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
