import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Trash2 } from "lucide-react";
import { api } from "../api";

export default function DeleteDataset({
  job,
  onDeleted,
  busy = false,
  text = false,
}: {
  job: { id: string; name: string; status: string };
  onDeleted: (id: string, message: string) => Promise<void>;
  busy?: boolean;
  text?: boolean;
}) {
  const [open, setOpen] = useState(false),
    [deleting, setDeleting] = useState(false),
    [error, setError] = useState("");
  const active = ["queued", "running", "cancelling"].includes(job.status);
  return (
    <>
      <button
        className="btn danger"
        disabled={busy || deleting || active}
        title={
          active
            ? "Cancel the job and wait for it to stop before deleting"
            : "Delete this dataset"
        }
        onClick={() => {
          setError("");
          setOpen(true);
        }}
      >
        <Trash2 size={14} />
        Delete dataset
      </button>
      <Dialog.Root
        open={open}
        onOpenChange={(v) => {
          if (!deleting) setOpen(v);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="modal-overlay" />
          <Dialog.Content className="modal delete-template-dialog">
            <Dialog.Title>Delete dataset?</Dialog.Title>
            <Dialog.Description>
              Permanently delete “{job.name}” ({job.id.slice(0, 8)}), its
              generated samples, annotations and local exports? The source
              template and other datasets are kept. Downloaded copies are
              unaffected.
            </Dialog.Description>
            {error && (
              <p role="alert" className="inline-error">
                {error}
              </p>
            )}
            <div className="delete-template-actions">
              <Dialog.Close className="btn" disabled={deleting}>
                Cancel
              </Dialog.Close>
              <button
                className="btn danger"
                disabled={deleting}
                onClick={async () => {
                  setDeleting(true);
                  setError("");
                  try {
                    const result = await api<{ warnings: string[] }>(
                      `${text ? "/text" : ""}/jobs/${job.id}`,
                      { method: "DELETE" },
                    );
                    setOpen(false);
                    await onDeleted(
                      job.id,
                      ["Dataset deleted.", ...result.warnings].join(" "),
                    );
                  } catch (e) {
                    setError(
                      e instanceof Error
                        ? e.message
                        : "Dataset could not be deleted",
                    );
                  } finally {
                    setDeleting(false);
                  }
                }}
              >
                {deleting ? "Deleting…" : "Permanently delete dataset"}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
