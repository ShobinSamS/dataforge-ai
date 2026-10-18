import { useEffect, useRef, useState } from "react";
import {
  Stage,
  Layer,
  Image as KImage,
  Rect,
  Transformer,
  Text,
} from "react-konva";
import type Konva from "konva";
import useImage from "use-image";
import {
  Hand,
  MousePointer2,
  Plus,
  ZoomIn,
  ZoomOut,
  Maximize,
} from "lucide-react";
import type { Region, Template } from "./types";

interface Props {
  template: Template;
  regions: Region[];
  selected: string;
  onSelect: (id: string) => void;
  onChange: (regions: Region[]) => void;
}
export default function RegionEditor({
  template,
  regions,
  selected,
  onSelect,
  onChange,
}: Props) {
  const [image] = useImage(`/api/templates/${template.id}/image`);
  const stage = useRef<Konva.Stage>(null),
    transformer = useRef<Konva.Transformer>(null),
    holder = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 700, height: 530 }),
    [zoom, setZoom] = useState(1),
    [mode, setMode] = useState<"select" | "draw" | "pan">("select");
  const [start, setStart] = useState<{ x: number; y: number } | null>(null),
    [draft, setDraft] = useState<[number, number, number, number] | null>(null);
  useEffect(() => {
    const observer = new ResizeObserver(([e]) =>
      setSize({
        width: e.contentRect.width,
        height: Math.max(390, Math.min(650, e.contentRect.width * 0.77)),
      }),
    );
    if (holder.current) observer.observe(holder.current);
    return () => observer.disconnect();
  }, []);
  const fit = Math.min(
      (size.width - 64) / template.width,
      (size.height - 64) / template.height,
    ),
    scale = fit * zoom;
  useEffect(() => {
    const node = stage.current?.findOne("#region-" + selected);
    transformer.current?.nodes(node && mode === "select" ? [node] : []);
  }, [selected, regions, mode]);
  const update = (id: string, box: Region["box"]) =>
    onChange(
      regions.map((r) => (r.id === id ? { ...r, box, confirmed: false } : r)),
    );
  const constrain = (box: Region["box"]): Region["box"] => {
    let [x, y, w, h] = box;
    x = Math.max(0, Math.min(template.width - 4, Math.round(x)));
    y = Math.max(0, Math.min(template.height - 4, Math.round(y)));
    return [
      x,
      y,
      Math.max(4, Math.min(template.width - x, Math.round(w))),
      Math.max(4, Math.min(template.height - y, Math.round(h))),
    ];
  };
  const point = () => {
    const s = stage.current!;
    const p = s.getPointerPosition()!;
    return s.getAbsoluteTransform().copy().invert().point(p);
  };
  return (
    <div ref={holder} className="canvas-wrap">
      <div className="canvas-toolbar">
        <div className="tool-group">
          {(
            [
              { id: "select", icon: MousePointer2, label: "Select regions" },
              { id: "draw", icon: Plus, label: "Draw replacement region" },
              { id: "pan", icon: Hand, label: "Pan page" },
            ] as const
          ).map((t) => (
            <button
              key={t.id}
              title={t.label}
              aria-label={t.label}
              className={mode === t.id ? "tool active" : "tool"}
              onClick={() => setMode(t.id)}
            >
              <t.icon size={16} />
            </button>
          ))}
        </div>
        <span>Page 1 / 1</span>
        <div className="tool-group">
          <button
            className="tool"
            title="Zoom out"
            onClick={() => setZoom(Math.max(0.5, zoom - 0.2))}
          >
            <ZoomOut size={16} />
          </button>
          <span>{Math.round(zoom * 100)}%</span>
          <button
            className="tool"
            title="Zoom in"
            onClick={() => setZoom(Math.min(4, zoom + 0.2))}
          >
            <ZoomIn size={16} />
          </button>
          <button
            className="tool"
            title="Fit page"
            onClick={() => {
              setZoom(1);
              stage.current?.position({ x: 32, y: 32 });
            }}
          >
            <Maximize size={15} />
          </button>
        </div>
      </div>
      <Stage
        ref={stage}
        width={size.width}
        height={size.height}
        scaleX={scale}
        scaleY={scale}
        x={32}
        y={32}
        draggable={mode === "pan"}
        onWheel={(e) => {
          e.evt.preventDefault();
          setZoom((z) =>
            Math.max(0.5, Math.min(4, z * (e.evt.deltaY > 0 ? 0.9 : 1.1))),
          );
        }}
        onMouseDown={(e) => {
          if (mode === "draw") {
            const p = point();
            setStart(p);
            setDraft([p.x, p.y, 0, 0]);
          } else if (e.target === stage.current || e.target.name() === "paper")
            onSelect("");
        }}
        onMouseMove={() => {
          if (start) {
            const p = point();
            setDraft([
              Math.min(p.x, start.x),
              Math.min(p.y, start.y),
              Math.abs(p.x - start.x),
              Math.abs(p.y - start.y),
            ]);
          }
        }}
        onMouseUp={() => {
          if (draft && draft[2] > 8 && draft[3] > 8) {
            const id = crypto.randomUUID().replaceAll("-", "");
            onChange([
              ...regions,
              {
                id,
                label: "Custom region",
                kind: "text",
                box: constrain(draft),
                text: "",
                confidence: 0,
                sensitive: true,
                replace: true,
                confirmed: false,
                page: 0,
                rule: "",
              },
            ]);
            onSelect(id);
            setMode("select");
          }
          setStart(null);
          setDraft(null);
        }}
      >
        <Layer>
          <KImage
            name="paper"
            image={image}
            width={template.width}
            height={template.height}
          />
          {regions.map((r) => (
            <Rect
              key={r.id}
              id={"region-" + r.id}
              x={r.box[0]}
              y={r.box[1]}
              width={r.box[2]}
              height={r.box[3]}
              fill={
                r.action === "erase"
                  ? "#f59e0b22"
                  : r.replace
                    ? "#10b98116"
                    : "#64748b08"
              }
              stroke={
                r.id === selected
                  ? "#0f766e"
                  : r.action === "erase"
                    ? "#d97706"
                    : r.replace
                      ? "#14b8a6"
                      : "#94a3b8"
              }
              strokeWidth={(r.id === selected ? 2 : 1) / scale}
              dash={r.replace ? undefined : [5 / scale, 4 / scale]}
              draggable={mode === "select"}
              onClick={() => onSelect(r.id)}
              onTap={() => onSelect(r.id)}
              onDragEnd={(e) =>
                update(
                  r.id,
                  constrain([e.target.x(), e.target.y(), r.box[2], r.box[3]]),
                )
              }
              onTransformEnd={(e) => {
                const n = e.target;
                const b = constrain([
                  n.x(),
                  n.y(),
                  n.width() * n.scaleX(),
                  n.height() * n.scaleY(),
                ]);
                n.scaleX(1);
                n.scaleY(1);
                update(r.id, b);
              }}
            />
          ))}
          {draft && (
            <Rect
              x={draft[0]}
              y={draft[1]}
              width={draft[2]}
              height={draft[3]}
              stroke="#0f766e"
              strokeWidth={2 / scale}
              fill="#14b8a620"
            />
          )}
          <Transformer
            ref={transformer}
            rotateEnabled={false}
            flipEnabled={false}
            boundBoxFunc={(old, next) =>
              next.width < 4 || next.height < 4 ? old : next
            }
          />
        </Layer>
      </Stage>
      <div className="canvas-caption">
        <span>
          <i className="dot teal" /> Replacement region
        </span>
        <span>
          <i className="dot" style={{ background: "#d97706" }} /> Erase only
        </span>
        <span>
          <i className="dot gray" /> Preserved content
        </span>
        <span>Drag to adjust · scroll to zoom</span>
      </div>
    </div>
  );
}
