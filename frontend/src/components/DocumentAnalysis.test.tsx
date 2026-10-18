import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DocumentAnalysis, { applyPii, tableCsv } from "./DocumentAnalysis";
import { api, post } from "../api";
import type { Region, Template } from "../types";
vi.mock("../api", () => ({ api: vi.fn(), post: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
const raw: Region = {
  id: "ocr",
  label: "Arun Kumar",
  kind: "text",
  box: [10, 10, 150, 25],
  text: "Arun Kumar",
  confidence: 0.9,
  sensitive: true,
  replace: true,
  confirmed: false,
  page: 0,
  rule: "",
  origin: "ocr",
};
const candidate: Region = {
  ...raw,
  id: "pii",
  label: "Person (PII)",
  kind: "name",
  action: "erase",
  origin: "pii",
  pii_value: "Arun Kumar",
  pii_reason: "The OCR contains an applicant name value.",
};
const template: Template = {
  id: "fixture",
  name: "Test",
  width: 500,
  height: 300,
  regions: [raw],
  warnings: [],
  engine: "ocr",
  revision: 1,
  privacy_confirmed: false,
  created_at: "",
};

it("replaces untouched OCR suggestions but preserves manual edits and skips overlaps", () => {
  const manual = {
    ...raw,
    id: "manual",
    origin: "manual" as const,
    box: [200, 100, 100, 40] as Region["box"],
  };
  const result = applyPii(
    [raw, manual],
    [candidate, { ...candidate, id: "conflict", box: manual.box }],
    template,
    true,
  );
  expect(result.added).toBe(1);
  expect(result.skipped).toBe(1);
  expect(result.regions).toEqual([manual, { ...candidate, confirmed: true }]);
  expect(
    applyPii(
      [{ ...raw, label: "Edited by user" }],
      [candidate],
      template,
      false,
    ).regions,
  ).toHaveLength(1);
});

it("requires explicit apply, preserves OCR coordinates, and carries human verification", async () => {
  vi.mocked(api).mockResolvedValue({
    models: { printed: true, handwritten: true },
    language: "English",
  });
  vi.mocked(post).mockResolvedValue({
    candidates: [candidate],
    engine: "local_qwen",
    ocr_engine: "existing_text",
    analyzed_count: 1,
    warnings: [],
  });
  const apply = vi.fn(),
    preview = vi.fn();
  render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false, gcTime: 0 } },
        })
      }
    >
      <DocumentAnalysis
        template={template}
        regions={[raw]}
        onApply={apply}
        onPreview={preview}
      />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByText("Find PII and auto-label"));
  await screen.findByText(/1 suggestions from 1/);
  expect(screen.getByText("Arun Kumar")).toBeTruthy();
  expect(
    screen.getByText(/Why selected: The OCR contains an applicant name value/),
  ).toBeTruthy();
  expect(apply).not.toHaveBeenCalled();
  expect(preview).toHaveBeenLastCalledWith([candidate]);
  fireEvent.change(screen.getByLabelText("Correct extracted value"), {
    target: { value: "Arun K. Kumar" },
  });
  expect(screen.getByText("Arun K. Kumar")).toBeTruthy();
  fireEvent.click(
    screen.getByLabelText("I checked the selected PII boxes and labels"),
  );
  fireEvent.click(screen.getByText("Apply selected as erase regions"));
  expect(apply).toHaveBeenLastCalledWith([
    {
      ...candidate,
      confirmed: true,
      pii_value: "Arun K. Kumar",
      pii_reason: "User-corrected transcription. " + candidate.pii_reason,
    },
  ]);
});

it("exports cell rows including blanks and protects CSV from spreadsheet formulas", () => {
  const cells = [
    {
      id: "a",
      table: 0,
      row: 0,
      column: 0,
      box: raw.box,
      text: "=DANGEROUS()",
      confidence: 1,
    },
    {
      id: "b",
      table: 0,
      row: 1,
      column: 1,
      box: raw.box,
      text: 'A,"B"',
      confidence: 1,
    },
  ];
  const csv = tableCsv(cells);
  expect(csv).toContain('"\'=DANGEROUS()",""');
  expect(csv).toContain('"","A,""B"""');
});
