import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import StampControls from "./StampControls";
import AssetStyleControls from "./AssetStyleControls";
import { defaultRuleOptions } from "./RegionRuleControls";
import { post } from "../api";
import { fieldTypes, type Region } from "../types";

vi.mock("../api", () => ({ post: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
const field: Region = {
  id: "postage",
  kind: "stamp",
  label: "Postage",
  box: [0, 0, 180, 240],
  text: "",
  confidence: 1,
  sensitive: true,
  replace: true,
  confirmed: true,
  page: 0,
  rule: "",
};

it("keeps seals, paper stamps and rubber stamps as separate fields with separate controls", () => {
  expect(fieldTypes.slice(12, 14)).toEqual(["stamp", "rubber_stamp"]);
  expect(fieldTypes[14]).toBe("drawing");
  const view = render(
    <AssetStyleControls
      field={{ ...field, kind: "seal" }}
      options={defaultRuleOptions}
      onChange={vi.fn()}
    />,
  );
  expect(screen.getByLabelText("Seal wording")).toBeTruthy();
  expect(screen.queryByLabelText("Rubber stamp preset")).toBeNull();
  view.rerender(
    <AssetStyleControls
      field={field}
      options={defaultRuleOptions}
      onChange={vi.fn()}
    />,
  );
  expect(screen.getByLabelText("Stamp artwork style")).toBeTruthy();
  expect(
    (screen.getByLabelText("Stamp print") as HTMLSelectElement).value,
  ).toBe("default");
  expect(
    (screen.getByLabelText("Stamp palette") as HTMLSelectElement).value,
  ).toBe("black");
  expect(
    (screen.getByLabelText("Cancellation mark") as HTMLSelectElement).value,
  ).toBe("none");
  expect(screen.queryByLabelText("Seal wording")).toBeNull();
  expect(screen.queryByLabelText("Rubber stamp preset")).toBeNull();
  view.rerender(
    <AssetStyleControls
      field={{ ...field, kind: "rubber_stamp" }}
      options={defaultRuleOptions}
      onChange={vi.fn()}
    />,
  );
  expect(screen.getByLabelText("Rubber stamp preset")).toBeTruthy();
  expect(screen.queryByLabelText("Stamp artwork style")).toBeNull();
});

it("saves independent paper settings, resets confirmation and preserves opacity", () => {
  const change = vi.fn();
  render(
    <AssetStyleControls
      field={field}
      options={{ ...defaultRuleOptions, ink_opacity_mode: "random" }}
      onChange={change}
    />,
  );
  fireEvent.change(screen.getByLabelText("Stamp artwork style"), {
    target: { value: "revenue" },
  });
  expect(change).toHaveBeenLastCalledWith(
    expect.objectContaining({
      confirmed: false,
      rule: "",
      rule_resolved_hash: "",
      rule_options: expect.objectContaining({
        stamp_style: "revenue",
        ink_opacity_mode: "random",
      }),
    }),
  );
  fireEvent.click(screen.getByLabelText("Perforated paper edges"));
  expect(change).toHaveBeenLastCalledWith(
    expect.objectContaining({
      rule_options: expect.objectContaining({ stamp_perforated: false }),
    }),
  );
  fireEvent.change(screen.getByLabelText("Cancellation mark"), {
    target: { value: "pen" },
  });
  expect(change).toHaveBeenLastCalledWith(
    expect.objectContaining({
      rule_options: expect.objectContaining({ stamp_cancellation: "pen" }),
    }),
  );
});

it("preserves literal captions when changing appearance and replaces them on explicit caption edits", () => {
  const change = vi.fn();
  render(
    <AssetStyleControls
      field={{ ...field, rule: "literal:EXACT CAPTION" }}
      options={defaultRuleOptions}
      onChange={change}
    />,
  );
  fireEvent.change(screen.getByLabelText("Stamp palette"), {
    target: { value: "blue" },
  });
  expect(change).toHaveBeenLastCalledWith(
    expect.objectContaining({
      rule_options: expect.objectContaining({
        literal_text: "EXACT CAPTION",
        stamp_palette: "blue",
      }),
    }),
  );
  fireEvent.change(
    screen.getByLabelText("Stamp caption (empty = vary with artwork)"),
    { target: { value: "NEW CAPTION" } },
  );
  expect(change).toHaveBeenLastCalledWith(
    expect.objectContaining({
      rule_options: expect.objectContaining({
        literal_text: null,
        stamp_caption: "NEW CAPTION",
      }),
    }),
  );
});

it("previews the correct paper field and reports server sizing errors", async () => {
  vi.mocked(post).mockResolvedValueOnce({
    image: "data:image/png;base64,fixture",
    metadata: { value: "CEDAR POST\n15 P" },
  });
  render(
    <StampControls field={field} options={defaultRuleOptions} set={vi.fn()} />,
  );
  fireEvent.click(screen.getByText("Preview paper stamp"));
  await waitFor(() =>
    expect(
      screen.getByAltText("Postage or revenue stamp preview"),
    ).toBeTruthy(),
  );
  expect(post).toHaveBeenCalledWith(
    "/assets/generate",
    expect.objectContaining({
      kind: "stamp",
      width: 180,
      height: 240,
      seed: 42,
    }),
  );
  vi.mocked(post).mockRejectedValueOnce(
    new Error("Paper stamp regions need at least 64×64 pixels"),
  );
  fireEvent.click(screen.getByText("Preview paper stamp"));
  await waitFor(() =>
    expect(screen.getByRole("alert").textContent).toContain("64×64"),
  );
});

it("does not apply an old preview after the selected settings change", async () => {
  let finish!: (value: unknown) => void;
  vi.mocked(post).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const view = render(
    <StampControls field={field} options={defaultRuleOptions} set={vi.fn()} />,
  );
  fireEvent.click(screen.getByText("Preview paper stamp"));
  view.rerender(
    <StampControls
      field={field}
      options={{ ...defaultRuleOptions, stamp_style: "revenue" }}
      set={vi.fn()}
    />,
  );
  finish({ image: "data:image/png;base64,old", metadata: { value: "OLD" } });
  await waitFor(() =>
    expect(
      (screen.getByText("Preview paper stamp") as HTMLButtonElement).disabled,
    ).toBe(false),
  );
  expect(screen.queryByAltText("Postage or revenue stamp preview")).toBeNull();
});
