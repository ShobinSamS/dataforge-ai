import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import VisualRegions, { applyVisualRegions } from "./VisualRegions";
import { post } from "../api";
import type { Region, Template } from "../types";

vi.mock("../api", () => ({ post: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
const text: Region = {
  id: "ocr",
  label: "Text",
  text: "noise",
  box: [15, 15, 30, 15],
  kind: "text",
  origin: "ocr",
  confidence: 0.5,
  confirmed: false,
  replace: true,
  sensitive: true,
  page: 0,
  rule: "",
};
const qr: Region = {
  ...text,
  id: "visual_qr",
  label: "QR code (proposal)",
  text: "",
  kind: "qr",
  origin: "visual",
  box: [10, 10, 100, 100],
};
const template: Template = {
  id: "one",
  name: "Page",
  width: 500,
  height: 500,
  regions: [text],
  warnings: [],
  engine: "manual",
  revision: 1,
  privacy_confirmed: false,
  created_at: "",
};

it("removes only untouched contained upload OCR and skips duplicates or conflicts", () => {
  expect(applyVisualRegions([text], [qr], template).regions).toEqual([qr]);
  expect(applyVisualRegions([qr], [qr], template)).toMatchObject({
    added: 0,
    skipped: 1,
    regions: [qr],
  });
  for (const changed of [
    { ...text, label: "Edited" },
    { ...text, origin: "manual" as const },
    { ...text, confirmed: true },
    { ...text, box: [5, 5, 80, 15] as Region["box"] },
  ]) {
    expect(applyVisualRegions([changed], [qr], template)).toMatchObject({
      added: 0,
      regions: [changed],
    });
  }
  const full = Array.from({ length: 200 }, (_, i) => ({
    ...text,
    id: `r${i}`,
    box: [200, 200, 4, 4] as Region["box"],
  }));
  expect(applyVisualRegions(full, [qr], template).added).toBe(0);
});

it("rescans into editable draft boxes, showing warnings and errors", async () => {
  vi.mocked(post).mockResolvedValueOnce({
    candidates: [qr],
    warnings: ["Inspect estimated boxes"],
  });
  const apply = vi.fn();
  render(
    <VisualRegions template={template} regions={[text]} onApply={apply} />,
  );
  fireEvent.click(screen.getByText("Find visual regions"));
  await waitFor(() => expect(apply).toHaveBeenCalledWith([qr]));
  expect(screen.getByRole("status").textContent).toContain(
    "1 visual boxes added",
  );
  expect(screen.getByText("Inspect estimated boxes")).toBeTruthy();
  vi.mocked(post).mockRejectedValueOnce(new Error("CPU busy"));
  fireEvent.click(screen.getByText("Find visual regions"));
  await waitFor(() =>
    expect(screen.getByRole("alert").textContent).toBe("CPU busy"),
  );
});

it("uses current edits when a detection request completes and ignores unmounted results", async () => {
  let resolve!: (result: unknown) => void;
  vi.mocked(post).mockImplementation(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
  );
  const apply = vi.fn();
  const view = render(
    <VisualRegions template={template} regions={[text]} onApply={apply} />,
  );
  fireEvent.click(screen.getByText("Find visual regions"));
  const edited = { ...text, label: "Edit made during scan" };
  view.rerender(
    <VisualRegions template={template} regions={[edited]} onApply={apply} />,
  );
  resolve({ candidates: [qr], warnings: [] });
  await waitFor(() =>
    expect(screen.getByRole("status").textContent).toContain("1 existing"),
  );
  expect(apply).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Find visual regions"));
  view.unmount();
  resolve({ candidates: [qr], warnings: [] });
  await Promise.resolve();
  expect(apply).not.toHaveBeenCalled();
});
