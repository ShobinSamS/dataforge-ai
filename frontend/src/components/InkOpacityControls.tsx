import type { RuleOptions } from "../types";

export default function InkOpacityControls({
  options,
  set,
}: {
  options: RuleOptions;
  set: (patch: Partial<RuleOptions>) => void;
}) {
  const mode = options.ink_opacity_mode || "random";
  const low = options.ink_opacity_min ?? 0.45;
  const high = options.ink_opacity_max ?? 1;
  return (
    <>
      <label>
        Ink finish
        <select
          value={options.ink_finish || "natural"}
          onChange={(e) =>
            set({ ink_finish: e.target.value as RuleOptions["ink_finish"] })
          }
        >
          <option value="clean">Clean</option>
          <option value="natural">Natural imperfections</option>
          <option value="worn">Worn / dry ink</option>
        </select>
      </label>
      {(options.ink_finish || "natural") !== "clean" && (
        <label>
          Imperfection strength ·{" "}
          {Math.round((options.ink_irregularity ?? 0.55) * 100)}%
          <input
            aria-label="Imperfection strength"
            type="range"
            min={0}
            max={100}
            step={1}
            value={Math.round((options.ink_irregularity ?? 0.55) * 100)}
            onChange={(e) =>
              set({ ink_irregularity: Number(e.target.value) / 100 })
            }
          />
        </label>
      )}
      <p className="field-hint">
        Natural adds uneven pressure, small distortions and occasional ink
        breaks. Worn adds stronger defects. Each sample varies reproducibly with
        its seed. For a pristine seal, also set Ink wear to zero.
      </p>
      <label>
        Ink opacity
        <select
          value={mode}
          onChange={(e) =>
            set({ ink_opacity_mode: e.target.value as "random" | "fixed" })
          }
        >
          <option value="random">Random per sample</option>
          <option value="fixed">Fixed opacity</option>
        </select>
      </label>
      {mode === "random" ? (
        <>
          <label>
            Minimum ink opacity · {Math.round(low * 100)}%
            <input
              aria-label="Minimum ink opacity"
              type="range"
              min={5}
              max={100}
              step={1}
              value={Math.round(low * 100)}
              onChange={(e) => {
                const value = Number(e.target.value) / 100;
                set({
                  ink_opacity_min: value,
                  ink_opacity_max: Math.max(high, value),
                });
              }}
            />
          </label>
          <label>
            Maximum ink opacity · {Math.round(high * 100)}%
            <input
              aria-label="Maximum ink opacity"
              type="range"
              min={5}
              max={100}
              step={1}
              value={Math.round(high * 100)}
              onChange={(e) => {
                const value = Number(e.target.value) / 100;
                set({
                  ink_opacity_max: value,
                  ink_opacity_min: Math.min(low, value),
                });
              }}
            />
          </label>
        </>
      ) : (
        <label>
          Fixed ink opacity · {Math.round((options.ink_opacity ?? 1) * 100)}%
          <input
            aria-label="Fixed ink opacity"
            type="range"
            min={5}
            max={100}
            step={1}
            value={Math.round((options.ink_opacity ?? 1) * 100)}
            onChange={(e) => set({ ink_opacity: Number(e.target.value) / 100 })}
          />
        </label>
      )}
      <p className="field-hint">
        Random opacity varies faint and strong ink independently of pen
        thickness and design. The same seed and settings reproduce the same
        opacity. Backgrounds remain transparent.
      </p>
    </>
  );
}
