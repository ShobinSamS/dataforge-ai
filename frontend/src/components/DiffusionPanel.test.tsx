import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DiffusionPanel from "./DiffusionPanel";
import { api, post } from "../api";
vi.mock("../api", () => ({ api: vi.fn(), post: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
const job = {
  id: "job1",
  kind: "portrait",
  status: "completed",
  prompt: "A fictional adult",
  seed: 42,
  steps: 1,
  step: 1,
  image_url: "/api/diffusion/jobs/job1/image",
  metrics: { elapsed_seconds: 33, peak_worker_rss_mb: 4200 },
};
function mount(
  onUse?: (asset: { id: string; preview_url: string }) => void,
  onUseMany?: (assets: { id: string; preview_url: string }[]) => void,
  qwen = false,
) {
  const view = render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false, gcTime: 0 } },
        })
      }
    >
      <DiffusionPanel kind="portrait" onUse={onUse} onUseMany={onUseMany} />
    </QueryClientProvider>,
  );
  if (!qwen)
    fireEvent.change(screen.getByLabelText("Prompt mode"), {
      target: { value: "manual" },
    });
  return view;
}
it("generates with the chosen seed and saves a preview into the region", async () => {
  let rows: (typeof job)[] = [];
  vi.mocked(api).mockImplementation(async (path) =>
    path.endsWith("capabilities")
      ? { ready: true, available_ram_mb: 6000 }
      : rows,
  );
  const use = vi.fn();
  vi.mocked(post).mockImplementation(async (path) => {
    if (path.endsWith("/save"))
      return { id: "asset1", preview_url: "/api/portraits/asset1/image" };
    rows = [job];
    return job;
  });
  mount(use);
  await screen.findByText(/SD-Turbo ready/);
  fireEvent.click(screen.getByRole("button", { name: "1 image" }));
  fireEvent.change(screen.getByLabelText("Image description"), {
    target: { value: "A fictional adult with glasses" },
  });
  fireEvent.change(screen.getByLabelText("Image seed"), {
    target: { value: "91" },
  });
  fireEvent.change(screen.getByLabelText("Diffusion steps"), {
    target: { value: "1" },
  });
  fireEvent.click(screen.getByText("Generate image preview"));
  await screen.findByAltText("Generated fictional person preview");
  expect(post).toHaveBeenCalledWith(
    "/diffusion/jobs",
    expect.objectContaining({
      kind: "portrait",
      seed: 91,
      steps: 1,
      prompt: "A fictional adult with glasses",
    }),
  );
  expect(use).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Use in this region"));
  await waitFor(() =>
    expect(use).toHaveBeenCalledWith({
      id: "asset1",
      preview_url: "/api/portraits/asset1/image",
    }),
  );
});
it("shows setup instead of pretending an uninstalled model is ready", async () => {
  vi.mocked(api).mockImplementation(async (path) =>
    path.endsWith("capabilities")
      ? {
          ready: false,
          runtime: true,
          model_installed: false,
          setup_commands: ["python setup_diffusion_model.py"],
        }
      : [],
  );
  mount();
  await screen.findByText("SD-Turbo model is not installed.");
  expect(screen.getByText("Generate 10 images").hasAttribute("disabled")).toBe(
    true,
  );
  expect(post).not.toHaveBeenCalled();
});
it("exposes cancellation for a running preview and reports failures", async () => {
  vi.mocked(api).mockImplementation(async (path) =>
    path.endsWith("capabilities")
      ? { ready: true, available_ram_mb: 6000 }
      : [{ ...job, status: "running", image_url: undefined }],
  );
  vi.mocked(post).mockRejectedValue(new Error("Cancellation unavailable"));
  mount();
  fireEvent.click(
    await screen.findByText(/Fictional person · running · seed 42/),
  );
  fireEvent.click(screen.getByText("Cancel preview"));
  await screen.findByText("Cancellation unavailable");
});

it("submits one hundred-image run and applies the completed pool in one action", async () => {
  const items = Array.from({ length: 100 }, (_, index) => ({
    ...job,
    id: `item${index}`,
    batch_index: index,
    seed: 42 + index,
    image_url: `/api/images/${index}`,
  }));
  const batch = {
    ...job,
    id: "batch1",
    count: 100,
    completed: 100,
    items,
    download_url: "/api/diffusion/jobs/batch1/download",
  };
  let rows: unknown[] = [];
  vi.mocked(api).mockImplementation(async (path) =>
    path.endsWith("capabilities")
      ? { ready: true, available_ram_mb: 6000 }
      : rows,
  );
  const assets = items.map((item, index) => ({
    id: `asset${index}`,
    preview_url: item.image_url,
  }));
  vi.mocked(post).mockImplementation(async (path) => {
    if (path.endsWith("/save")) return { assets };
    rows = [batch];
    return batch;
  });
  const useMany = vi.fn();
  mount(undefined, useMany);
  await screen.findByText(/SD-Turbo ready/);
  expect(
    (screen.getByLabelText("Number of images") as HTMLInputElement).value,
  ).toBe("10");
  fireEvent.click(screen.getByRole("button", { name: "100 images" }));
  fireEvent.click(screen.getByText("Generate 100 images"));
  await screen.findByAltText("Batch image 100");
  expect(post).toHaveBeenCalledWith(
    "/diffusion/jobs",
    expect.objectContaining({ count: 100 }),
  );
  expect(
    vi.mocked(post).mock.calls.filter(([path]) => path === "/diffusion/jobs"),
  ).toHaveLength(1);
  expect(
    screen
      .getByRole("link", { name: "Download completed images ZIP" })
      .getAttribute("href"),
  ).toBe(batch.download_url);
  fireEvent.click(screen.getByText("Use completed images in this region"));
  await waitFor(() => expect(useMany).toHaveBeenCalledWith(assets));
});

it("keeps completed previews visible and offers resume for a cancelled batch", async () => {
  vi.mocked(api).mockImplementation(async (path) =>
    path.endsWith("capabilities")
      ? { ready: true, available_ram_mb: 6000 }
      : [
          {
            ...job,
            id: "partial",
            status: "cancelled",
            count: 3,
            completed: 1,
            items: [{ ...job, batch_index: 0 }],
            download_url: "/partial.zip",
          },
        ],
  );
  vi.mocked(post).mockResolvedValue({});
  mount();
  fireEvent.click(
    await screen.findByRole("button", {
      name: /Fictional person · cancelled · seed 42/,
    }),
  );
  expect(
    (
      screen.getByRole("progressbar", {
        name: "Image batch progress",
      }) as HTMLProgressElement
    ).value,
  ).toBe(1);
  expect(screen.getByAltText("Batch image 1")).toBeTruthy();
  fireEvent.click(screen.getByText("Resume remaining images"));
  await waitFor(() =>
    expect(post).toHaveBeenCalledWith("/diffusion/jobs/partial/resume"),
  );
});

it("defaults to Qwen variation, previews a sample and sends the editable brief for each-image planning", async () => {
  let rows: unknown[] = [];
  vi.mocked(api).mockImplementation(async (path) =>
    path.endsWith("capabilities")
      ? {
          ready: true,
          available_ram_mb: 7000,
          prompt_llm: { installed: true, model: "qwen3:1.7b" },
        }
      : rows,
  );
  const description =
    "A fictional adult man in his fifties with curly gray hair, a green sweater and a relaxed expression.";
  vi.mocked(post).mockImplementation(async (path) => {
    if (path.endsWith("/prompts/preview"))
      return {
        generated_prompt: description,
        prompt_seed: 111,
        prompt_model: "qwen3:1.7b",
      };
    const planned = {
      ...job,
      prompt_mode: "qwen",
      generated_prompt: description,
      prompt_seed: 222,
      prompt_model: "qwen3:1.7b",
    };
    rows = [planned];
    return planned;
  });
  mount(undefined, undefined, true);
  await screen.findByText(/qwen3:1.7b is available/);
  expect(
    (screen.getByLabelText("Prompt mode") as HTMLSelectElement).value,
  ).toBe("qwen");
  expect(
    (screen.getByLabelText("Image brief") as HTMLTextAreaElement).value,
  ).toContain("One anonymous fictional adult");
  fireEvent.change(screen.getByLabelText("Image brief"), {
    target: {
      value: "Fictional South Asian women with varied clothing and hairstyles",
    },
  });
  fireEvent.click(screen.getByText("Preview sample Qwen prompt"));
  await screen.findByText(description);
  expect(post).toHaveBeenCalledWith(
    "/diffusion/prompts/preview",
    expect.objectContaining({
      prompt_mode: "qwen",
      prompt: "Fictional South Asian women with varied clothing and hairstyles",
    }),
  );
  fireEvent.click(screen.getByRole("button", { name: "1 image" }));
  fireEvent.click(screen.getByText("Generate image preview"));
  await screen.findByAltText("Generated fictional person preview");
  expect(post).toHaveBeenCalledWith(
    "/diffusion/jobs",
    expect.objectContaining({
      prompt_mode: "qwen",
      prompt: "Fictional South Asian women with varied clothing and hairstyles",
      count: 1,
    }),
  );
  expect(screen.getByText("Prompt used for this image")).toBeTruthy();
});

it("requires local Qwen for randomized mode and keeps manual generation available", async () => {
  vi.mocked(api).mockImplementation(async (path) =>
    path.endsWith("capabilities")
      ? {
          ready: true,
          available_ram_mb: 7000,
          prompt_llm: { installed: false, model: "qwen3:1.7b" },
        }
      : [],
  );
  mount(undefined, undefined, true);
  await screen.findByText(/Start local Ollama/);
  expect(screen.getByText("Generate 10 images").hasAttribute("disabled")).toBe(
    true,
  );
  fireEvent.change(screen.getByLabelText("Prompt mode"), {
    target: { value: "manual" },
  });
  expect(screen.getByText("Generate 10 images").hasAttribute("disabled")).toBe(
    false,
  );
  expect(screen.getByLabelText("Image description")).toBeTruthy();
});
