import { afterEach, it, expect, vi } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import DeleteDataset from "./DeleteDataset";
import { api } from "../api";
vi.mock("../api", () => ({ api: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
const job = { id: "job-a", name: "Unneeded dataset", status: "completed" };

it("requires confirmation, permits cancellation, then deletes only the selected dataset", async () => {
  const onDeleted = vi.fn().mockResolvedValue(undefined);
  vi.mocked(api).mockResolvedValue({ warnings: [] });
  render(<DeleteDataset job={job} onDeleted={onDeleted} />);
  fireEvent.click(screen.getByText("Delete dataset"));
  expect(
    screen.getByText(/source template and other datasets are kept/),
  ).toBeTruthy();
  fireEvent.click(screen.getByText("Cancel"));
  expect(api).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Delete dataset"));
  fireEvent.click(screen.getByText("Permanently delete dataset"));
  await waitFor(() =>
    expect(onDeleted).toHaveBeenCalledWith("job-a", "Dataset deleted."),
  );
  expect(api).toHaveBeenCalledExactlyOnceWith("/jobs/job-a", {
    method: "DELETE",
  });
});
it("blocks active jobs and displays server failures without pretending deletion succeeded", async () => {
  const onDeleted = vi.fn();
  const view = render(
    <DeleteDataset job={{ ...job, status: "running" }} onDeleted={onDeleted} />,
  );
  expect(
    (screen.getByText("Delete dataset") as HTMLButtonElement).disabled,
  ).toBe(true);
  view.rerender(<DeleteDataset job={job} onDeleted={onDeleted} text />);
  vi.mocked(api).mockRejectedValue(new Error("Cancel the job first"));
  fireEvent.click(screen.getByText("Delete dataset"));
  fireEvent.click(screen.getByText("Permanently delete dataset"));
  await waitFor(() =>
    expect(screen.getByRole("alert").textContent).toBe("Cancel the job first"),
  );
  expect(api).toHaveBeenCalledWith("/text/jobs/job-a", { method: "DELETE" });
  expect(onDeleted).not.toHaveBeenCalled();
});
