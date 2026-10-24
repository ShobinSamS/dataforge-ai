import { useState } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import RegionRuleControls, { defaultRuleOptions } from "./RegionRuleControls";
import { api, post } from "../api";
import type { Region } from "../types";

vi.mock("../api", () => ({ api: vi.fn(), post: vi.fn() }));
const original: Region = {
  id: "field",
  label: "Test field",
  kind: "text",
  box: [20, 20, 100, 80],
  text: "",
  confidence: 0,
  sensitive: true,
  replace: true,
  confirmed: true,
  page: 0,
  rule: "remove this completely",
};
function mount(initial: Partial<Region> = {}) {
  function Wrapper() {
    const [field, setField] = useState({ ...original, ...initial });
    return (
      <>
        <RegionRuleControls
          field={field}
          onChange={(patch) => setField((value) => ({ ...value, ...patch }))}
        />
        <output data-testid="field">{JSON.stringify(field)}</output>
      </>
    );
  }
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false, gcTime: 0 } },
        })
      }
    >
      <Wrapper />
    </QueryClientProvider>,
  );
}
const value = () => JSON.parse(screen.getByTestId("field").textContent!);
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api).mockResolvedValue({ online_configured: false });
});
afterEach(cleanup);

it("applies a prompt as an erase plan and requires fresh confirmation", async () => {
  vi.mocked(post).mockResolvedValue({
    region: { ...original, action: "erase", confirmed: false },
    engine: "deterministic",
    explanation: "Clear the selected area.",
  });
  mount();
  fireEvent.click(screen.getByText("Apply rule"));
  await screen.findByText(/Clear the selected area/);
  expect(post).toHaveBeenCalledWith("/document-rules/interpret", {
    region: original,
    engine: "auto",
  });
  expect(value().action).toBe("erase");
  expect(value().confirmed).toBe(false);
  expect(
    screen.getByText(/It receives no replacement or object annotation/),
  ).toBeTruthy();
});

it("supports explicit erase without a model and clears the old prompt", () => {
  mount();
  fireEvent.change(screen.getByLabelText("Action"), {
    target: { value: "erase" },
  });
  expect(value()).toMatchObject({
    action: "erase",
    replace: true,
    rule: "",
    confirmed: false,
  });
  expect(post).not.toHaveBeenCalled();
});

it("retains custom pattern case and lets the user configure generated length", () => {
  mount({
    kind: "identifier",
    rule: "",
    rule_options: { ...defaultRuleOptions, literal_text: "Old fixed label" },
  });
  fireEvent.change(screen.getByLabelText("Character pattern"), {
    target: { value: "inv-{lower:4}{digits:4}" },
  });
  expect(value().rule_options.identifier_pattern).toBe(
    "inv-{lower:4}{digits:4}",
  );
  expect(value().rule_options.literal_text).toBe(null);
  fireEvent.change(
    screen.getByLabelText("Generated character length (empty = automatic)"),
    { target: { value: "12" } },
  );
  expect(value().rule_options.character_length).toBe(12);
  expect(value().confirmed).toBe(false);
});

it("generates a 500-character QR payload without a custom pattern", () => {
  mount({ kind: "qr", rule: "" });
  const input = screen.getByLabelText(
    "Generated character length (empty = automatic)",
  ) as HTMLInputElement;
  expect(input.max).toBe("500");
  fireEvent.change(input, { target: { value: "500" } });
  expect(value().rule_options.character_length).toBe(500);
  expect(value().rule_options.identifier_pattern).toBe("");
  expect(post).not.toHaveBeenCalled();
});

it("shows the resolved PAN pattern, format source and honest fallback status", async () => {
  vi.mocked(post).mockResolvedValue({
    region: {
      ...original,
      kind: "identifier",
      confirmed: false,
      rule_options: { identifier_pattern: "AAAAA9999A" },
    },
    engine: "known_rule_fallback",
    explanation: "Use the verified character layout",
    warnings: [
      "Local Qwen did not return an executable plan; using recognized format.",
    ],
    references: [
      {
        title: "Official PAN format",
        url: "https://traces61contents.tdscpc.gov.in/en/faq-general-pan.html",
        verified_at: "2026-10-18",
        pattern: "AAAAA9999A",
      },
    ],
  });
  mount({ rule: "pan card pattern" });
  fireEvent.click(screen.getByText("Interpret with local Qwen"));
  await screen.findByText("Applied recognized rule fallback");
  expect(
    screen.getByText(/Local Qwen did not return an executable plan/),
  ).toBeTruthy();
  expect(
    screen.getByText("Official PAN format").getAttribute("href"),
  ).toContain("tdscpc.gov.in");
  expect(screen.getByText(/Resolved pattern/).textContent).toContain(
    "AAAAA9999A",
  );
  expect(value().kind).toBe("identifier");
});

it("shows interpreted date bounds and format and permits explicit changes", async () => {
  vi.mocked(post).mockResolvedValue({
    region: {
      ...original,
      kind: "date",
      action: "replace",
      confirmed: false,
      rule_options: {
        date_format: "dd/mm/yyyy",
        date_start: "1980-01-01",
        date_end: "2000-12-31",
      },
    },
    engine: "local_qwen",
    explanation: "Date plan",
  });
  mount({ rule: "Pick a date of birth" });
  fireEvent.click(screen.getByText("Interpret with local Qwen"));
  await screen.findByLabelText("Date format");
  expect(vi.mocked(post).mock.calls[0][1]).toMatchObject({
    engine: "local_llm",
  });
  expect(
    (screen.getByLabelText("Earliest date") as HTMLInputElement).value,
  ).toBe("1980-01-01");
  fireEvent.change(screen.getByLabelText("Date format"), {
    target: { value: "yyyy-mm-dd" },
  });
  expect(value().rule_options.date_format).toBe("yyyy-mm-dd");
  expect(value().rule).toBe("");
});

it("uploads an approved portrait and selects the pool without automatic internet access", async () => {
  mount({ kind: "portrait", rule: "" });
  const input = screen.getByLabelText(
    "Add images or ZIP to pool (up to 20 per upload)",
  ) as HTMLInputElement;
  expect(input.disabled).toBe(true);
  fireEvent.click(
    screen.getByLabelText(
      "I have permission to use these images in this dataset.",
    ),
  );
  expect(input.disabled).toBe(false);
  vi.mocked(api).mockResolvedValue({ portraits: [{ id: "a".repeat(32) }] });
  fireEvent.change(input, {
    target: {
      files: [new File(["fixture"], "portrait.png", { type: "image/png" })],
    },
  });
  await waitFor(() =>
    expect(value().rule_options?.portrait_asset_ids).toEqual(["a".repeat(32)]),
  );
  expect(value().rule_options.portrait_source).toBe("asset_pool");
  const call = vi
    .mocked(api)
    .mock.calls.find(([path]) => path === "/portraits/batch")!;
  expect((call[1]?.body as FormData).get("rights_confirmed")).toBe("true");
  expect(
    (screen.getByText("Fetch from configured provider") as HTMLButtonElement)
      .disabled,
  ).toBe(true);
  expect(post).not.toHaveBeenCalled();
});

it("appends a multi-image ZIP batch to the existing pool in one update", async () => {
  mount({
    kind: "portrait",
    rule: "",
    rule_options: {
      ...defaultRuleOptions,
      portrait_source: "asset_pool",
      portrait_asset_ids: ["a".repeat(32)],
    },
  });
  fireEvent.click(
    screen.getByLabelText(
      "I have permission to use these images in this dataset.",
    ),
  );
  const input = screen.getByLabelText(
    "Add images or ZIP to pool (up to 20 per upload)",
  ) as HTMLInputElement;
  expect(input.multiple).toBe(true);
  expect(input.accept).toContain(".zip");
  vi.mocked(api).mockResolvedValue({
    portraits: [{ id: "b".repeat(32) }, { id: "c".repeat(32) }],
  });
  const files = [
    new File(["zip"], "photos.zip", { type: "application/zip" }),
    new File(["png"], "photo.png", { type: "image/png" }),
  ];
  fireEvent.change(input, { target: { files } });
  await waitFor(() =>
    expect(value().rule_options.portrait_asset_ids).toEqual([
      "a".repeat(32),
      "b".repeat(32),
      "c".repeat(32),
    ]),
  );
  const body = vi
    .mocked(api)
    .mock.calls.find(([path]) => path === "/portraits/batch")![1]
    ?.body as FormData;
  expect(body.getAll("files")).toHaveLength(2);
  expect(body.get("max_count")).toBe("20");
  expect(value().confirmed).toBe(false);
  expect(input.value).toBe("");
});

it("leaves the selected pool unchanged when a batch is rejected", async () => {
  mount({
    kind: "portrait",
    rule: "",
    rule_options: {
      ...defaultRuleOptions,
      portrait_asset_ids: ["a".repeat(32)],
    },
  });
  fireEvent.click(
    screen.getByLabelText(
      "I have permission to use these images in this dataset.",
    ),
  );
  vi.mocked(api).mockRejectedValue(
    new Error("Batch exceeds remaining image slots"),
  );
  fireEvent.change(
    screen.getByLabelText("Add images or ZIP to pool (up to 20 per upload)"),
    { target: { files: [new File(["zip"], "photos.zip")] } },
  );
  expect((await screen.findByRole("alert")).textContent).toContain(
    "remaining image slots",
  );
  expect(value().rule_options.portrait_asset_ids).toEqual(["a".repeat(32)]);
});

it("explains unsupported rules without altering the selected region", async () => {
  vi.mocked(post).mockRejectedValue(
    new Error("Unsupported rule; select explicit controls"),
  );
  mount();
  fireEvent.click(screen.getByText("Apply rule"));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Unsupported rule",
  );
  expect(value()).toEqual(original);
});
