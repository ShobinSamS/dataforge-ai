import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import QrCapacity from "./QrCapacity";
import { api } from "../api";
import type { Config, Template } from "../types";
vi.mock("../api", () => ({ api: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
const template: Template = {
  id: "fixture",
  name: "Test",
  width: 500,
  height: 500,
  regions: [],
  warnings: [],
  engine: "manual",
  revision: 1,
  privacy_confirmed: true,
  created_at: "",
};
const config: Config = {
  template_id: "fixture",
  name: "Test",
  count: 10,
  seed: 42,
  qr_codes: true,
  qr_payload_length: 219,
  blur_probability: 0,
  rotation_probability: 0,
  rotation_degrees: 0,
  noise_sigma: 0,
  signatures: true,
  seals: true,
  barcodes: false,
  max_retries: 0,
};
it("shows the actual field override and directs the user to the selected QR field", async () => {
  vi.mocked(api).mockResolvedValue({
    valid: false,
    errors: ["Too small"],
    qr_regions: [
      {
        region_id: "qr",
        label: "QR code",
        width: 128,
        height: 122,
        payload_characters: 500,
        payload_source: "field length override",
        required_size: 219,
        max_automatic_characters: 122,
        fits: false,
        error: "Too small",
      },
    ],
  });
  const state = vi.fn(),
    edit = vi.fn();
  render(
    <QrCapacity
      config={config}
      template={template}
      onEdit={edit}
      onState={state}
    />,
  );
  expect(state).toHaveBeenCalledWith("checking");
  await screen.findByText(/Effective payload: 500 characters/);
  expect(screen.getByText(/Required: 219 × 219 px/)).toBeTruthy();
  expect(screen.getByText(/field length overrides/)).toBeTruthy();
  expect(state).toHaveBeenLastCalledWith("invalid");
  fireEvent.click(screen.getByText("Edit this QR field"));
  expect(edit).toHaveBeenCalledWith("qr");
});
it("checks changed defaults, permits valid settings, and skips disabled QR generation", async () => {
  vi.mocked(api).mockResolvedValue({ valid: true, errors: [], qr_regions: [] });
  const state = vi.fn();
  const view = render(
    <QrCapacity config={config} template={template} onState={state} />,
  );
  await waitFor(() => expect(state).toHaveBeenLastCalledWith("valid"));
  view.rerender(
    <QrCapacity
      config={{ ...config, qr_payload_length: 10 }}
      template={template}
      onState={state}
    />,
  );
  await waitFor(() => expect(api).toHaveBeenCalledTimes(2));
  expect(
    JSON.parse(vi.mocked(api).mock.calls[1][1]!.body as string)
      .qr_payload_length,
  ).toBe(10);
  view.rerender(
    <QrCapacity
      config={{ ...config, qr_codes: false }}
      template={template}
      onState={state}
    />,
  );
  expect(screen.queryByText("QR size check")).toBeNull();
  expect(state).toHaveBeenLastCalledWith("valid");
});
