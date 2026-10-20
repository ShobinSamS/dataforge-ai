import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import CanvasTools from "./CanvasTools";
import type { Template, Region } from "../types";
import { post } from "../api";
vi.mock("../api", () => ({ post: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
const template = {
  id: "blank",
  name: "Asset",
  engine: "canvas",
  width: 800,
  height: 400,
  canvas: { dpi: 150, background: "transparent" },
} as Template;
const region = {
  id: "s",
  kind: "signature",
  box: [20, 20, 300, 100],
  rule: "",
  replace: true,
} as Region;

it("adds typed elements within the page and previews downloadable PNG without saving a review", async () => {
  const change = vi.fn(),
    select = vi.fn(),
    preview = vi.fn();
  vi.mocked(post).mockResolvedValue({
    image: "data:image/png;base64,test",
    errors: [],
  });
  render(
    <CanvasTools
      template={template}
      regions={[region]}
      selected="s"
      onChange={change}
      onSelect={select}
      onPreview={preview}
    />,
  );
  fireEvent.change(screen.getByLabelText("New element"), {
    target: { value: "seal" },
  });
  fireEvent.click(screen.getByText("Add element"));
  const added = change.mock.calls[0][0][1];
  expect(added.kind).toBe("seal");
  expect(added.box[0] + added.box[2]).toBeLessThanOrEqual(800);
  expect(select).toHaveBeenCalledWith(added.id);
  fireEvent.click(screen.getByText("Preview canvas"));
  await screen.findByText("Download PNG");
  expect(post).toHaveBeenCalledWith("/templates/blank/preview", {
    regions: [region],
    seed: 42,
  });
  expect(preview).toHaveBeenLastCalledWith("data:image/png;base64,test");
});

it("discards an outdated preview when elements change", async () => {
  let resolve: (value: unknown) => void = () => {};
  vi.mocked(post).mockReturnValue(
    new Promise((r) => {
      resolve = r;
    }),
  );
  const preview = vi.fn();
  const props = {
    template,
    regions: [region],
    selected: "s",
    onChange: vi.fn(),
    onSelect: vi.fn(),
    onPreview: preview,
  };
  const view = render(<CanvasTools {...props} />);
  fireEvent.click(screen.getByText("Preview canvas"));
  view.rerender(<CanvasTools {...props} regions={[]} />);
  resolve({ image: "data:image/png;base64,stale", errors: [] });
  await waitFor(() =>
    expect(
      (screen.getByText("Preview canvas") as HTMLButtonElement).disabled,
    ).toBe(false),
  );
  expect(screen.queryByText("Download PNG")).toBeNull();
  expect(preview).not.toHaveBeenCalledWith("data:image/png;base64,stale");
});
