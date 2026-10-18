import type React from "react";
import { Database, FolderOpen } from "lucide-react";
const statusLabel = (s: string) => s.replaceAll("_", " ");
export function Badge({
  status,
  children,
}: {
  status?: string;
  children?: React.ReactNode;
}) {
  return (
    <span className={"badge " + (status || "neutral")}>
      {children || statusLabel(status || "")}
    </span>
  );
}
export function Empty({
  icon: Icon = FolderOpen,
  title,
  body,
  action,
}: {
  icon?: typeof FolderOpen;
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <Icon size={34} strokeWidth={1.4} />
      <h3>{title}</h3>
      <p>{body}</p>
      {action}
    </div>
  );
}
export function Stat({
  label,
  value,
  detail,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  detail: string;
  icon: typeof Database;
}) {
  return (
    <div className="stat">
      <div className="stat-top">
        <span>{label}</span>
        <Icon size={18} />
      </div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}
