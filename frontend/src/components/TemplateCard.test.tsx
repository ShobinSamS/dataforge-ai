import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import TemplateCard from "./TemplateCard";
import { api } from "../api";
import type { Template } from "../types";
vi.mock("../api", () => ({ api: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
const template: Template = {
  id: "fixture",
  name: "Sample.png",
  width: 500,
  height: 300,
  regions: [],
  warnings: [],
  engine: "manual",
  revision: 3,
  privacy_confirmed: false,
  created_at: "",
};

it("keeps open and delete separate and sends no deletion until confirmed", async () => {
  const opened = vi.fn(),
    deleted = vi.fn().mockResolvedValue(undefined);
  vi.mocked(api).mockResolvedValue({ retained_for_jobs: false, warnings: [] });
  const result = render(
    <TemplateCard
      template={template}
      busy={false}
      jobCount={0}
      onOpen={opened}
      onDeleted={deleted}
    />,
  );
  expect(result.container.querySelector("button button")).toBeNull();
  fireEvent.click(screen.getByLabelText("Open template Sample.png"));
  expect(opened).toHaveBeenCalledWith(template);
  opened.mockClear();
  fireEvent.click(screen.getByLabelText("Delete template Sample.png"));
  expect(screen.getByRole("dialog")).toBeTruthy();
  expect(api).not.toHaveBeenCalled();
  expect(opened).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Cancel"));
  expect(api).not.toHaveBeenCalled();
  fireEvent.click(screen.getByLabelText("Delete template Sample.png"));
  fireEvent.click(screen.getByRole("button", { name: "Delete template" }));
  await waitFor(() =>
    expect(deleted).toHaveBeenCalledWith("fixture", "Template deleted."),
  );
  expect(api).toHaveBeenCalledWith("/templates/fixture?revision=3", {
    method: "DELETE",
  });
});

it("explains retained job data and reports the deletion result", async () => {
  const deleted = vi.fn().mockResolvedValue(undefined);
  vi.mocked(api).mockResolvedValue({ retained_for_jobs: true, warnings: [] });
  render(
    <TemplateCard
      template={template}
      busy={false}
      jobCount={2}
      onOpen={vi.fn()}
      onDeleted={deleted}
    />,
  );
  fireEvent.click(screen.getByLabelText("Delete template Sample.png"));
  expect(
    screen.getByText(
      /2 existing generation jobs and generated datasets will remain/,
    ),
  ).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Delete template" }));
  await waitFor(() =>
    expect(deleted).toHaveBeenCalledWith(
      "fixture",
      expect.stringContaining("Existing jobs and datasets were kept"),
    ),
  );
});

it("keeps the confirmation open when deletion fails and does not remove the card", async () => {
  const deleted = vi.fn();
  vi.mocked(api).mockRejectedValue(
    new Error("Template changed; reload the library before deleting"),
  );
  render(
    <TemplateCard
      template={template}
      busy={false}
      jobCount={0}
      onOpen={vi.fn()}
      onDeleted={deleted}
    />,
  );
  fireEvent.click(screen.getByLabelText("Delete template Sample.png"));
  fireEvent.click(screen.getByRole("button", { name: "Delete template" }));
  await screen.findByRole("alert");
  expect(screen.getByRole("dialog")).toBeTruthy();
  expect(deleted).not.toHaveBeenCalled();
  expect(screen.getByLabelText("Open template Sample.png")).toBeTruthy();
});
