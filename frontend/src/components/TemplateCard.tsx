import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { ArrowUpRight, Trash2, X } from "lucide-react";
import { api } from "../api";
import type { Template } from "../types";
import { Badge } from "./ui";

export default function TemplateCard({
  template,
  busy,
  jobCount,
  onOpen,
  onDeleted,
}: {
  template: Template;
  busy: boolean;
  jobCount: number;
  onOpen: (t: Template) => void;
  onDeleted: (id: string, message: string) => Promise<void>;
}) {
  const [confirm, setConfirm] = useState(false),
    [deleting, setDeleting] = useState(false),
    [error, setError] = useState("");
  return (
    <article className="template-card">
      <button
        className="template-open"
        disabled={busy || deleting}
        aria-label={`Open template ${template.name}`}
        onClick={() => onOpen(template)}
      >
        <div className="template-thumb">
          <img
            src={`/api/templates/${template.id}/image`}
            alt={template.name}
          />
          <Badge status={template.privacy_confirmed ? "completed" : "paused"}>
            {template.privacy_confirmed ? "Reviewed" : "Review needed"}
          </Badge>
        </div>
        <div className="template-card-body">
          <h3>{template.name}</h3>
          <p>
            {template.regions.length} regions · v{template.revision} ·{" "}
            {template.width} × {template.height}
          </p>
          <span>
            {template.engine}
            <ArrowUpRight size={16} />
          </span>
        </div>
      </button>
      <div className="template-card-actions">
        <button
          className="btn danger"
          disabled={busy || deleting}
          aria-label={`Delete template ${template.name}`}
          onClick={() => {
            setError("");
            setConfirm(true);
          }}
        >
          <Trash2 size={14} />
          Delete
        </button>
      </div>
      <Dialog.Root
        open={confirm}
        onOpenChange={(v) => {
          if (!deleting) setConfirm(v);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="modal-overlay" />
          <Dialog.Content className="modal delete-template-dialog">
            <div className="row-between">
              <Dialog.Title>Delete template?</Dialog.Title>
              <Dialog.Close
                className="icon-button"
                aria-label="Close delete dialog"
                disabled={deleting}
              >
                <X size={18} />
              </Dialog.Close>
            </div>
            <Dialog.Description>
              {jobCount
                ? `Remove “${template.name}” from the library? Its ${jobCount} existing generation job${jobCount === 1 ? "" : "s"} and generated datasets will remain. The source is retained for those jobs; this template cannot be used for new generation.`
                : `Delete “${template.name}” from the library? If no generation jobs reference it, its source image and saved reviews are permanently deleted. Any existing jobs and datasets are kept, along with their required source.`}
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
                    const result = await api<{
                      retained_for_jobs: boolean;
                      warnings: string[];
                    }>(
                      `/templates/${template.id}?revision=${template.revision}`,
                      { method: "DELETE" },
                    );
                    const message = result.retained_for_jobs
                      ? "Template removed from the library. Existing jobs and datasets were kept."
                      : "Template deleted.";
                    setConfirm(false);
                    await onDeleted(
                      template.id,
                      [message, ...result.warnings].join(" "),
                    );
                  } catch (e) {
                    setError(
                      e instanceof Error
                        ? e.message
                        : "Template could not be deleted",
                    );
                  } finally {
                    setDeleting(false);
                  }
                }}
              >
                {deleting ? "Deleting…" : "Delete template"}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </article>
  );
}
