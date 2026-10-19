import { afterEach, it, expect, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import AssetStyleControls from "./AssetStyleControls";
import { defaultRuleOptions } from "./RegionRuleControls";
import type { Region } from "../types";

afterEach(cleanup);

for (const kind of ["signature", "seal"] as const) {
  it(`configures random and fixed ${kind} opacity and resets review`, () => {
    const change = vi.fn();
    const field = {
      id: "asset",
      kind,
      box: [0, 0, 300, 150],
      confirmed: true,
      rule: "",
    } as Region;
    const view = render(
      <AssetStyleControls
        field={field}
        options={defaultRuleOptions}
        onChange={change}
      />,
    );
    expect(
      (screen.getByLabelText("Ink opacity") as HTMLSelectElement).value,
    ).toBe("random");
    fireEvent.change(screen.getByLabelText("Minimum ink opacity"), {
      target: { value: "60" },
    });
    expect(change).toHaveBeenLastCalledWith(
      expect.objectContaining({
        confirmed: false,
        rule: "",
        rule_options: expect.objectContaining({
          ink_opacity_min: 0.6,
          ink_opacity_max: 1,
        }),
      }),
    );
    fireEvent.change(screen.getByLabelText("Maximum ink opacity"), {
      target: { value: "30" },
    });
    expect(change).toHaveBeenLastCalledWith(
      expect.objectContaining({
        rule_options: expect.objectContaining({
          ink_opacity_min: 0.3,
          ink_opacity_max: 0.3,
        }),
      }),
    );
    fireEvent.change(screen.getByLabelText("Ink opacity"), {
      target: { value: "fixed" },
    });
    expect(change).toHaveBeenLastCalledWith(
      expect.objectContaining({
        rule_options: expect.objectContaining({ ink_opacity_mode: "fixed" }),
      }),
    );
    view.rerender(
      <AssetStyleControls
        field={field}
        options={{ ...defaultRuleOptions, ink_opacity_mode: "fixed" }}
        onChange={change}
      />,
    );
    expect(screen.queryByLabelText("Minimum ink opacity")).toBeNull();
    fireEvent.change(screen.getByLabelText("Fixed ink opacity"), {
      target: { value: "25" },
    });
    expect(change).toHaveBeenLastCalledWith(
      expect.objectContaining({
        rule_options: expect.objectContaining({ ink_opacity: 0.25 }),
      }),
    );
  });
}

it("preserves literal seal wording when opacity changes", () => {
  const change = vi.fn();
  render(
    <AssetStyleControls
      field={
        {
          id: "s",
          kind: "seal",
          rule: "literal:CEDAR LAB",
          box: [0, 0, 240, 240],
        } as Region
      }
      options={defaultRuleOptions}
      onChange={change}
    />,
  );
  fireEvent.change(screen.getByLabelText("Ink opacity"), {
    target: { value: "fixed" },
  });
  expect(change).toHaveBeenLastCalledWith(
    expect.objectContaining({
      rule: "",
      rule_options: expect.objectContaining({
        seal_text: "CEDAR LAB",
        seal_text_mode: "static",
        ink_opacity_mode: "fixed",
      }),
    }),
  );
});

it("preserves literal signature text when opacity changes", () => {
  const change = vi.fn();
  render(
    <AssetStyleControls
      field={
        {
          id: "s",
          kind: "signature",
          rule: "literal:Mira Dev",
          box: [0, 0, 300, 100],
        } as Region
      }
      options={defaultRuleOptions}
      onChange={change}
    />,
  );
  fireEvent.change(screen.getByLabelText("Ink opacity"), {
    target: { value: "fixed" },
  });
  expect(change).toHaveBeenLastCalledWith(
    expect.objectContaining({
      rule: "",
      rule_options: expect.objectContaining({
        literal_text: "Mira Dev",
        ink_opacity_mode: "fixed",
      }),
    }),
  );
});
