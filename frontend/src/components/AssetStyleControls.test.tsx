import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import AssetStyleControls from "./AssetStyleControls";
import { defaultRuleOptions } from "./RegionRuleControls";
import type { Region } from "../types";
afterEach(cleanup);
it("offers rubber stamp presets through the existing seal renderer and preserves ink settings", () => {
  const changed = vi.fn();
  const field: Region = {
    id: "stamp",
    label: "Stamp",
    kind: "seal",
    box: [0, 0, 300, 100],
    text: "",
    confidence: 1,
    sensitive: true,
    replace: true,
    confirmed: true,
    page: 0,
    rule: "literal:OLD TEXT",
  };
  render(
    <AssetStyleControls
      field={field}
      options={{
        ...defaultRuleOptions,
        ink_finish: "worn",
        ink_opacity_mode: "random",
      }}
      onChange={changed}
    />,
  );
  for (const word of [
    "RECEIVED",
    "PAID",
    "APPROVED",
    "REJECTED",
    "COPY",
    "CONFIDENTIAL",
  ]) {
    fireEvent.change(screen.getByLabelText("Rubber stamp preset"), {
      target: { value: word },
    });
    expect(changed).toHaveBeenLastCalledWith(
      expect.objectContaining({
        confirmed: false,
        rule: "",
        rule_options: expect.objectContaining({
          seal_text: word,
          seal_subtext: "",
          seal_text_mode: "static",
          literal_text: null,
          seal_style: "rectangle",
          ink_finish: "worn",
          ink_opacity_mode: "random",
        }),
      }),
    );
  }
});
it("offers mixed, abbreviated and undecorated signatures and resets confirmation on changes", () => {
  const field: Region = {
    id: "sign",
    label: "Signature",
    kind: "signature",
    box: [10, 10, 300, 80],
    text: "",
    confidence: 1,
    sensitive: true,
    replace: true,
    confirmed: true,
    page: 0,
    rule: "",
  };
  const changed = vi.fn();
  render(
    <AssetStyleControls
      field={field}
      options={defaultRuleOptions}
      onChange={changed}
    />,
  );
  const select = screen.getByLabelText("Signature style") as HTMLSelectElement;
  expect(select.value).toBe("mixed");
  for (const value of [
    "mixed",
    "name",
    "first_name",
    "single_letter",
    "two_letters",
    "initials",
    "letter_wave",
    "monogram",
    "flourish",
    "tall_initial",
    "compact",
    "angular",
    "looped",
    "sweeping",
    "gestural",
    "stacked",
    "initial_bridge",
    "terminal_loop",
    "crossed",
    "minimal",
    "surname",
    "split",
    "enclosed",
    "interwoven",
  ]) {
    expect(Array.from(select.options).some((o) => o.value === value)).toBe(
      true,
    );
    fireEvent.change(select, { target: { value } });
    expect(changed).toHaveBeenLastCalledWith(
      expect.objectContaining({
        confirmed: false,
        rule: "",
        rule_options: expect.objectContaining({ signature_style: value }),
      }),
    );
  }
});
