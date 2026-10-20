import { useState } from "react";
import { afterEach, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import ColorControls from "./ColorControls";
import { defaultRuleOptions } from "./RegionRuleControls";
import type { RuleOptions } from "../types";

afterEach(cleanup);
function mount(seal = false) {
  function Wrapper() {
    const [options, setOptions] = useState<RuleOptions>({
      ...defaultRuleOptions,
    });
    return (
      <>
        <ColorControls
          options={options}
          set={(patch) => setOptions((current) => ({ ...current, ...patch }))}
          seal={seal}
        />
        <output data-testid="colors">{JSON.stringify(options)}</output>
      </>
    );
  }
  render(<Wrapper />);
}
const value = () => JSON.parse(screen.getByTestId("colors").textContent!);
it("defaults to black and supports standard swatches and the native custom picker", () => {
  mount();
  expect(
    (screen.getByLabelText("Text color mode") as HTMLSelectElement).value,
  ).toBe("black");
  fireEvent.click(screen.getByRole("button", { name: "Text color #ff0000" }));
  expect(value()).toMatchObject({
    color_mode: "manual",
    text_color: "#ff0000",
  });
  fireEvent.change(screen.getByLabelText("Text color", { exact: true }), {
    target: { value: "#123456" },
  });
  expect(value().text_color).toBe("#123456");
  fireEvent.change(screen.getByLabelText("Text color mode"), {
    target: { value: "black" },
  });
  expect(value()).toMatchObject({ color_mode: "black", text_color: "#000000" });
});
it("lets users define random variation palettes and retains at least one color", () => {
  mount(true);
  fireEvent.change(screen.getByLabelText("Text color mode"), {
    target: { value: "random" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Text color #ff0000" }));
  expect(value().color_palette).toContain("#ff0000");
  expect(value().seal_color).toBe("black");
  fireEvent.change(screen.getByLabelText("Text color", { exact: true }), {
    target: { value: "#123456" },
  });
  expect(value().color_mode).toBe("random");
  expect(value().color_palette).toContain("#123456");
  fireEvent.change(screen.getByLabelText("Text color mode"), {
    target: { value: "mixed" },
  });
  expect(value().color_mode).toBe("mixed");
});
