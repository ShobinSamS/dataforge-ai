import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import SampleAnnotationEditor from "./SampleAnnotationEditor";
import { api, post } from "../api";
vi.mock("../api", () => ({ api: vi.fn(), post: vi.fn() }));
const record = {
  width: 500,
  height: 300,
  revision: 3,
  annotations: [
    {
      region_id: "name",
      class: "name",
      text: "Mira Dev",
      bbox: [20, 30, 200, 50],
    },
  ],
};
afterEach(cleanup);
beforeEach(() => vi.clearAllMocks());
it("saves corrected text, class, box and rejection with the loaded revision", async () => {
  vi.mocked(api)
    .mockResolvedValueOnce(record)
    .mockResolvedValueOnce({ ...record, revision: 4 });
  const saved = vi.fn();
  render(
    <SampleAnnotationEditor
      endpoint="/samples/a/annotations"
      imageUrl="/api/samples/a/image"
      onSaved={saved}
    />,
  );
  await screen.findByDisplayValue("Mira Dev");
  fireEvent.change(screen.getByLabelText("Text name"), {
    target: { value: "Mira Sen" },
  });
  fireEvent.change(screen.getByLabelText("X name"), {
    target: { value: "25" },
  });
  fireEvent.click(screen.getByLabelText("Exclude this sample from exports"));
  fireEvent.click(screen.getByText("Save label corrections"));
  await screen.findByText("Annotations saved");
  const request = JSON.parse(String(vi.mocked(api).mock.calls[1][1]?.body));
  expect(request.revision).toBe(3);
  expect(request.rejected).toBe(true);
  expect(request.annotations[0]).toEqual({
    region_id: "name",
    kind: "name",
    text: "Mira Sen",
    bbox: [25, 30, 200, 50],
  });
  expect(saved).toHaveBeenCalled();
});
it("keeps draft corrections visible on revision conflict and regenerates explicitly", async () => {
  vi.mocked(api)
    .mockResolvedValueOnce(record)
    .mockRejectedValueOnce(new Error("Annotations changed; reload"))
    .mockResolvedValueOnce({ ...record, revision: 4 });
  vi.mocked(post).mockResolvedValue({});
  render(
    <SampleAnnotationEditor
      endpoint="/samples/a/annotations"
      imageUrl="/api/samples/a/image"
      regenerateEndpoint="/samples/a/regenerate"
    />,
  );
  await screen.findByDisplayValue("Mira Dev");
  fireEvent.change(screen.getByLabelText("Text name"), {
    target: { value: "Edited" },
  });
  fireEvent.click(screen.getByText("Save label corrections"));
  await screen.findByRole("alert");
  expect((screen.getByLabelText("Text name") as HTMLInputElement).value).toBe(
    "Edited",
  );
  fireEvent.click(screen.getByText("Regenerate this document"));
  await waitFor(() =>
    expect(post).toHaveBeenCalledWith("/samples/a/regenerate"),
  );
  await screen.findByText("Regenerated with a fresh seed");
});
