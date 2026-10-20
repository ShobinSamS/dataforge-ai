import { Badge } from "../components/ui";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export default function McpTools() {
  const { data: system } = useQuery({
    queryKey: ["system"],
    queryFn: () => api<{ api_port?: number }>("/system"),
  });
  const suffix =
    system?.api_port && system.api_port !== 8000
      ? ` --api-url http://127.0.0.1:${system.api_port}`
      : "";
  return (
    <div className="studio-grid mcp-tools">
      <section className="panel form-panel">
        <div className="panel-title">
          <h2>Connect an MCP client</h2>
          <Badge status="completed">IMPLEMENTED</Badge>
        </div>
        <p>
          Use signatures, stamps, templates and datasets from a standard MCP
          client. The optional MCP process connects to this running DataForge
          API.
        </p>
        <h3>Install once</h3>
        <pre>
          <code>{String.raw`.\.venv\Scripts\python.exe -m pip install -r requirements-mcp.txt`}</code>
        </pre>
        <h3>Streamable HTTP</h3>
        <pre>
          <code>{`npm.cmd run mcp${suffix ? ` --${suffix}` : ""}`}</code>
        </pre>
        <p>
          Default endpoint: <code>http://127.0.0.1:8001/mcp</code>
        </p>
        <p className="field-hint">
          Start the optional process before connecting. This page describes
          setup; it does not report whether that process is running. The
          endpoint runs on this computer.
        </p>
        <h3>Stdio client configuration</h3>
        <pre>
          <code>
            {String.raw`.\.venv\Scripts\python.exe scripts/mcp_config.py` +
              suffix}
          </code>
        </pre>
        <p>
          Copy the generated configuration into your client's MCP settings. It
          uses absolute paths and works from any client working directory. Keep
          the DataForge API running.
        </p>
        <p className="field-hint">
          Read docs/mcp.md in the project for the complete catalog, input
          examples, Linux/macOS commands and export download instructions.
        </p>
      </section>
      <section className="panel form-panel">
        <div className="panel-title">
          <h2>44 tools · 3 resources</h2>
          <Badge>STDIO / HTTP</Badge>
        </div>
        {[
          [
            "Visual assets",
            "Signatures, seals, postage/revenue stamps, rubber marks, QR codes, Code128 barcodes, text, country-aware addresses and portraits",
          ],
          [
            "Templates",
            "Create blank canvases, preview transparent compositions, upload, inspect, label, save reviews and delete",
          ],
          [
            "Document analysis",
            "Visual coordinates, OCR-grounded PII, table extraction, Qwen rules and font matching",
          ],
          [
            "Document datasets",
            "Preflight, generate, monitor, inspect samples and validate quality",
          ],
          [
            "Text datasets",
            "Classification, NER, Q&A, instructions, conversations, augmentation and multiple languages",
          ],
          [
            "Exports",
            "YOLO, COCO, OCR, CSV, JSON and JSONL with chunked downloads",
          ],
        ].map(([title, text]) => (
          <div className="setting-row" key={title}>
            <strong>{title}</strong>
            <span>{text}</span>
          </div>
        ))}
        <p>
          Images return as PNGs with masks and metadata. Assets support seeded
          variations, random opacity, natural ink flaws and the existing style
          controls.
        </p>
        <p>
          Client resources: <code>dataforge://guide</code>,{" "}
          <code>dataforge://schemas</code>, and{" "}
          <code>dataforge://templates</code>.
        </p>
        <p className="field-hint">
          Template revisions, explicit review flags, queue limits and deletion
          checks use the same rules as the app.
        </p>
      </section>
    </div>
  );
}
