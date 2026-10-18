import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import AssetStyleControls from "./AssetStyleControls";
import { defaultRuleOptions } from "./RegionRuleControls";
import type { Region } from "../types";
afterEach(cleanup);
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
