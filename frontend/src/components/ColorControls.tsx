import type { RuleOptions } from "../types";

export const defaultPalette = [
  "#000000",
  "#173574",
  "#a61c32",
  "#216e39",
  "#6a338e",
];
const swatches = [
  "#000000",
  "#434343",
  "#666666",
  "#999999",
  "#ffffff",
  "#173574",
  "#0000ff",
  "#0070c0",
  "#00b0f0",
  "#216e39",
  "#00b050",
  "#92d050",
  "#a61c32",
  "#ff0000",
  "#ff6600",
  "#ffc000",
  "#ffff00",
  "#6a338e",
  "#c000c0",
  "#8b4c29",
];

export default function ColorControls({
  options,
  set,
  label = "Text color",
  source = false,
  seal = false,
}: {
  options: RuleOptions;
  set: (patch: Partial<RuleOptions>) => void;
  label?: string;
  source?: boolean;
  seal?: boolean;
}) {
  const mode =
    options.color_mode === "black" &&
    options.text_color &&
    options.text_color.toLowerCase() !== "#000000"
      ? "manual"
      : options.color_mode || "black";
  const palette = options.color_palette || defaultPalette;
  const change = (patch: Partial<RuleOptions>) =>
    set({ ...patch, ...(seal ? { seal_color: "black" as const } : {}) });
  return (
    <div className="color-controls">
      <label>
        {label} mode
        <select
          value={mode}
          onChange={(e) =>
            change({
              color_mode: e.target.value as RuleOptions["color_mode"],
              ...(e.target.value === "black" ? { text_color: "#000000" } : {}),
            })
          }
        >
          <option value="black">Default · black</option>
          <option value="manual">Custom color</option>
          <option value="random">Random from selected colors per sample</option>
          {source && <option value="auto">Match original lettering</option>}
          {seal && <option value="mixed">Vary border and text colors</option>}
          {!source && mode === "auto" && (
            <option value="auto">Use saved color settings</option>
          )}
        </select>
      </label>
      <div
        className="color-swatches"
        role="group"
        aria-label={`${label} palette`}
      >
        {[...new Set([...swatches, ...palette])].map((color) => (
          <button
            key={color}
            type="button"
            title={color}
            aria-label={`${label} ${color}`}
            aria-pressed={
              mode === "random" || mode === "mixed"
                ? palette.includes(color)
                : (options.text_color || "#000000").toLowerCase() === color
            }
            style={{ backgroundColor: color }}
            disabled={
              (mode === "random" || mode === "mixed") &&
              palette.length >= 20 &&
              !palette.includes(color)
            }
            onClick={() => {
              if (mode === "random" || mode === "mixed") {
                const next = palette.includes(color)
                  ? palette.filter((c) => c !== color)
                  : [...palette, color];
                if (next.length) change({ color_palette: next });
              } else change({ color_mode: "manual", text_color: color });
            }}
          />
        ))}
      </div>
      <label>
        {label}
        <input
          type="color"
          value={options.text_color || "#000000"}
          onChange={(e) => {
            if (mode === "random" || mode === "mixed")
              change({
                text_color: e.target.value,
                color_palette: [...new Set([...palette, e.target.value])].slice(
                  -20,
                ),
              });
            else change({ text_color: e.target.value, color_mode: "manual" });
          }}
        />
      </label>
      <p className="field-hint">
        {mode === "random" || mode === "mixed"
          ? `${palette.length} colors selected. Click swatches to include or remove colors; the picker adds a custom color. Selection varies with the sample seed.`
          : `Choose a standard swatch or any color with the picker. Current color: ${options.text_color || "#000000"}.`}
      </p>
    </div>
  );
}
