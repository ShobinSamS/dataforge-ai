import { afterEach, it, expect, vi } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  waitFor,
} from "@testing-library/react";
import SealControls from "./SealControls";
import { defaultRuleOptions } from "./RegionRuleControls";
import { post } from "../api";
import type { Region } from "../types";
vi.mock("../api", () => ({ post: vi.fn(), api: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
const field = {
  id: "seal-a",
  kind: "seal",
  rule: "",
  box: [0, 0, 300, 200],
} as Region;

it("applies complete corporate reference presets without changing the selected ink", () => {
  const set = vi.fn();
  render(
    <SealControls
      field={field}
      options={{ ...defaultRuleOptions, text_color: "#173574" }}
      set={set}
    />,
  );
  fireEvent.change(screen.getByLabelText("Seal reference layout"), {
    target: { value: "shipping" },
  });
  expect(set).toHaveBeenLastCalledWith(
    expect.objectContaining({
      seal_style: "form_block",
      seal_text_mode: "custom",
      seal_border: "double",
      seal_body_format: "REG NO: {reference}\nTO:\nPRODUCT:\nBATCH:",
      seal_artwork_ids: [],
    }),
  );
  expect(set.mock.calls[0][0]).not.toHaveProperty("text_color");
  fireEvent.change(screen.getByLabelText("Seal reference layout"), {
    target: { value: "corporate" },
  });
  expect(set).toHaveBeenLastCalledWith(
    expect.objectContaining({
      seal_style: "corporate",
      seal_center_motif: "shield",
      seal_border: "rosettes",
    }),
  );
});

it("offers random, static and custom wording with explicit repetition control", () => {
  const set = vi.fn();
  const view = render(
    <SealControls field={field} options={defaultRuleOptions} set={set} />,
  );
  expect(
    (screen.getByLabelText("Seal wording") as HTMLSelectElement).value,
  ).toBe("random");
  fireEvent.change(screen.getByLabelText("Seal wording"), {
    target: { value: "static" },
  });
  expect(set).toHaveBeenLastCalledWith({
    seal_text_mode: "static",
    literal_text: null,
  });
  view.rerender(
    <SealControls
      field={field}
      options={{
        ...defaultRuleOptions,
        seal_text_mode: "static",
        seal_text: "CUSTOM TITLE",
      }}
      set={set}
    />,
  );
  expect(
    (screen.getByLabelText("Seal main text") as HTMLInputElement).value,
  ).toBe("CUSTOM TITLE");
  view.rerender(
    <SealControls
      field={field}
      options={{ ...defaultRuleOptions, seal_text_mode: "custom" }}
      set={set}
    />,
  );
  fireEvent.change(screen.getByLabelText("Body format"), {
    target: { value: "{name}\n{reference}" },
  });
  expect(set).toHaveBeenLastCalledWith({
    seal_body_format: "{name}\n{reference}",
  });
  fireEvent.click(screen.getByLabelText("Allow repeated words"));
  expect(set).toHaveBeenLastCalledWith({ seal_allow_repeated_words: true });
});

it("previews actual wording and reports validation failures", async () => {
  const set = vi.fn();
  vi.mocked(post).mockResolvedValue({
    image: "data:image/png;base64,fixture",
    metadata: { shape: "ring", text: "CEDAR LAB\nMIRA DEV" },
  });
  render(
    <SealControls
      field={field}
      options={{ ...defaultRuleOptions, seal_text_mode: "custom" }}
      set={set}
    />,
  );
  fireEvent.click(screen.getByText("Preview seal variation"));
  await waitFor(() =>
    expect(screen.getByAltText("Fictional ring seal preview")).toBeTruthy(),
  );
  expect(post).toHaveBeenCalledWith(
    "/seals/preview",
    expect.objectContaining({
      region_id: "seal-a",
      width: 300,
      height: 200,
      seed: 42,
    }),
  );
  expect(screen.getByText(/CEDAR LAB/)).toBeTruthy();
  vi.mocked(post).mockRejectedValue(new Error("Repeated seal words: cedar"));
  fireEvent.click(screen.getByText("Preview seal variation"));
  await waitFor(() =>
    expect(screen.getByRole("alert").textContent).toMatch(
      /Repeated seal words/,
    ),
  );
});

it("preserves a literal heading when editing other seal settings", () => {
  const set = vi.fn();
  render(
    <SealControls
      field={{ ...field, rule: "literal:EXACT HEADING" }}
      options={defaultRuleOptions}
      set={set}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Seal ink #6a338e" }));
  expect(set).toHaveBeenCalledWith({
    seal_text: "EXACT HEADING",
    seal_text_mode: "static",
    seal_color: "black",
    color_mode: "manual",
    text_color: "#6a338e",
  });
});

it("offers reference layouts, inner arcs and handwritten attestation fields", () => {
  const set = vi.fn();
  const view = render(
    <SealControls
      field={field}
      options={{ ...defaultRuleOptions, seal_style: "corporate" }}
      set={set}
    />,
  );
  const shape = screen.getByLabelText("Seal shape") as HTMLSelectElement;
  for (const value of ["attestation", "corporate", "form_block", "nameplate"]) {
    expect(
      Array.from(shape.options).some((option) => option.value === value),
    ).toBe(true);
  }
  fireEvent.change(screen.getByLabelText("Inner top arc"), {
    target: { value: "INCORPORATED {year}" },
  });
  expect(set).toHaveBeenLastCalledWith({
    seal_inner_top_text: "INCORPORATED {year}",
  });
  fireEvent.change(screen.getByLabelText("Center motif"), {
    target: { value: "shield" },
  });
  expect(set).toHaveBeenLastCalledWith({ seal_center_motif: "shield" });
  view.rerender(
    <SealControls
      field={field}
      options={{
        ...defaultRuleOptions,
        seal_style: "attestation",
        seal_embedded_signature: true,
      }}
      set={set}
    />,
  );
  fireEvent.change(screen.getByLabelText("Field value writing"), {
    target: { value: "cursive" },
  });
  expect(set).toHaveBeenLastCalledWith({ seal_field_writing: "cursive" });
  fireEvent.change(
    screen.getByLabelText("Signing name (blank generates a name)"),
    { target: { value: "Mira Dev" } },
  );
  expect(set).toHaveBeenLastCalledWith({ seal_signer_name: "Mira Dev" });
  fireEvent.click(
    screen.getByLabelText("Add a generated signature inside the stamp"),
  );
  expect(set).toHaveBeenLastCalledWith({ seal_embedded_signature: false });
});
