import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import DocumentLab from "./DocumentLab";
import { api, post } from "../api";
vi.mock("../api", () => ({ api: vi.fn(), post: vi.fn() }));
afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api).mockResolvedValue([]);
});
function mount() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <DocumentLab />
    </QueryClientProvider>,
  );
  return client;
}
it("submits multi-page generation with controlled percentages and split settings", async () => {
  vi.mocked(post).mockResolvedValue({ id: "run" });
  const client = mount();
  fireEvent.change(screen.getByLabelText("Document packs"), {
    target: { value: "3" },
  });
  fireEvent.change(screen.getByLabelText("Pages per pack"), {
    target: { value: "2" },
  });
  fireEvent.click(screen.getByText("Generate 3 packs · 6 pages"));
  await waitFor(() => expect(post).toHaveBeenCalled());
  expect(vi.mocked(post).mock.calls[0][0]).toBe("/document-lab/jobs");
  expect(vi.mocked(post).mock.calls[0][1]).toMatchObject({
    count: 3,
    pages: 2,
    signature_percent: 80,
    negative_percent: 10,
    train_percent: 80,
    validation_percent: 10,
  });
  client.clear();
});
it("prevents invalid split proportions and oversized runs", () => {
  const client = mount();
  fireEvent.change(screen.getByLabelText("Train %"), {
    target: { value: "95" },
  });
  expect(
    (screen.getByText("Generate 10 packs · 20 pages") as HTMLButtonElement)
      .disabled,
  ).toBe(true);
  fireEvent.change(screen.getByLabelText("Train %"), {
    target: { value: "80" },
  });
  fireEvent.change(screen.getByLabelText("Document packs"), {
    target: { value: "100" },
  });
  fireEvent.change(screen.getByLabelText("Pages per pack"), {
    target: { value: "5" },
  });
  expect(
    (screen.getByText("Generate 100 packs · 500 pages") as HTMLButtonElement)
      .disabled,
  ).toBe(true);
  client.clear();
});
