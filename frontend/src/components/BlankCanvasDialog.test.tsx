import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import BlankCanvasDialog from "./BlankCanvasDialog";
import { post } from "../api";
vi.mock("../api", () => ({ post: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

it("creates a white A4 canvas by default and opens the returned template", async () => {
  const template = { id: "blank", engine: "canvas" };
  vi.mocked(post).mockResolvedValue(template);
  const created = vi.fn();
  render(<BlankCanvasDialog onCreated={created} />);
  fireEvent.click(screen.getByText("Create from scratch"));
  expect(
    (screen.getByLabelText("Document size") as HTMLSelectElement).value,
  ).toBe("a4");
  fireEvent.click(screen.getByText("Create canvas"));
  await waitFor(() => expect(created).toHaveBeenCalledWith(template));
  expect(post).toHaveBeenCalledWith(
    "/templates/blank",
    expect.objectContaining({
      paper: "a4",
      dpi: 150,
      background: "white",
      starter: "blank",
    }),
  );
});

it("supports a custom transparent asset canvas and leaves errors editable", async () => {
  vi.mocked(post).mockRejectedValue(new Error("Canvas too large"));
  render(<BlankCanvasDialog onCreated={vi.fn()} />);
  fireEvent.click(screen.getByText("Create from scratch"));
  fireEvent.change(screen.getByLabelText("Document size"), {
    target: { value: "custom" },
  });
  fireEvent.change(screen.getByLabelText("Size units"), {
    target: { value: "px" },
  });
  fireEvent.change(screen.getByLabelText("Width"), {
    target: { value: "800" },
  });
  fireEvent.change(screen.getByLabelText("Height"), {
    target: { value: "300" },
  });
  fireEvent.change(screen.getByLabelText("Orientation"), {
    target: { value: "landscape" },
  });
  fireEvent.change(screen.getByLabelText("Canvas background"), {
    target: { value: "transparent" },
  });
  fireEvent.change(screen.getByLabelText("Start with"), {
    target: { value: "signature" },
  });
  fireEvent.click(screen.getByText("Create canvas"));
  await screen.findByRole("alert");
  expect(post).toHaveBeenCalledWith(
    "/templates/blank",
    expect.objectContaining({
      width: 800,
      height: 300,
      unit: "px",
      orientation: "landscape",
      background: "transparent",
      starter: "signature",
    }),
  );
  expect(screen.getByRole("alert").textContent).toContain("Canvas too large");
});
