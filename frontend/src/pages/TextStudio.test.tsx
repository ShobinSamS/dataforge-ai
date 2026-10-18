import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import TextStudio from "./TextStudio";
import { api, post } from "../api";
vi.mock("../api", () => ({ api: vi.fn(), post: vi.fn() }));
const caps = {
  max_samples: 2000,
  languages: { en: "English", hi: "Hindi" },
  llm: { installed: true, reachable: true, model: "qwen3:1.7b" },
  limitations: [],
};
function mount() {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false, gcTime: 0 } },
        })
      }
    >
      <TextStudio />
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api).mockImplementation(async (path) =>
    path === "/text/capabilities" ? caps : ([] as never),
  );
  vi.mocked(post).mockResolvedValue({ id: "queued-job" });
});
afterEach(cleanup);
describe("Text dataset studio", () => {
  it("offers all six tasks and all five output languages", async () => {
    mount();
    const select = screen.getByLabelText("Dataset task") as HTMLSelectElement;
    expect(Array.from(select.options).map((o) => o.value)).toEqual([
      "classification",
      "ner",
      "qa",
      "instruction",
      "conversation",
      "augmentation",
    ]);
    for (const language of ["English", "Spanish", "French", "German", "Hindi"])
      expect(screen.getByLabelText(language)).toBeTruthy();
    await screen.findByText("No text jobs yet");
  });
  it("submits task, count, languages and seed through the actual form", async () => {
    mount();
    await screen.findByText("No text jobs yet");
    fireEvent.change(screen.getByLabelText("Dataset task"), {
      target: { value: "ner" },
    });
    fireEvent.change(screen.getByLabelText(/Sample count/), {
      target: { value: "123" },
    });
    fireEvent.change(screen.getByLabelText("Random seed"), {
      target: { value: "718" },
    });
    fireEvent.click(screen.getByLabelText("Hindi"));
    fireEvent.click(screen.getByText("Generate text dataset"));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/text/jobs",
        expect.objectContaining({
          task: "ner",
          count: 123,
          seed: 718,
          languages: ["en", "hi"],
        }),
      ),
    );
  });
  it("shows local Qwen controls and validates augmentation input JSON", async () => {
    mount();
    await screen.findByText("No text jobs yet");
    fireEvent.change(screen.getByLabelText("Generation engine"), {
      target: { value: "ollama" },
    });
    await screen.findByText("qwen3:1.7b available locally");
    expect(screen.getByLabelText("Content instructions")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Dataset task"), {
      target: { value: "augmentation" },
    });
    fireEvent.change(screen.getByLabelText("Source texts JSON"), {
      target: { value: "broken JSON" },
    });
    fireEvent.click(screen.getByText("Generate text dataset"));
    await screen.findByRole("alert");
    expect(post).not.toHaveBeenCalled();
  });
  it("requires review before exporting and offers CSV, JSON and JSONL", async () => {
    const job = {
      id: "job-one",
      name: "Existing text dataset",
      status: "completed",
      total: 2,
      completed: 2,
      error: "",
      metrics: {},
      config: { backend: "procedural", task: "ner" },
    };
    vi.mocked(api).mockImplementation(async (path) => {
      if (path === "/text/capabilities") return caps as never;
      if (path === "/text/jobs") return [job] as never;
      if (path.includes("/records")) return { items: [], total: 2 } as never;
      if (path.includes("/quality"))
        return {
          requested: 2,
          total: 2,
          accepted: 2,
          rejected: 0,
          labels: {},
          languages: { en: 2 },
          errors: {},
          warnings: [],
        } as never;
      return [] as never;
    });
    mount();
    await screen.findByLabelText("Text export format");
    const options = Array.from(
      (screen.getByLabelText("Text export format") as HTMLSelectElement)
        .options,
    ).map((o) => o.value);
    expect(options).toEqual(["jsonl", "json", "csv"]);
    const button = screen.getByText(
      "Download text dataset",
    ) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.click(screen.getByLabelText(/I reviewed generated text/));
    expect(button.disabled).toBe(false);
  });
});
