import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import DocumentOutputControls from "./DocumentOutputControls";
import type { Config } from "../types";

afterEach(cleanup);
const config: Config = {
  template_id: "fixture",
  name: "Test",
  count: 1,
  seed: 42,
  blur_probability: 0,
  rotation_probability: 0,
  rotation_degrees: 0,
  noise_sigma: 0,
  signatures: true,
  seals: true,
  qr_codes: true,
  barcodes: false,
  max_retries: 0,
};
it("exposes character counts, zero QR padding and a required QR setting", () => {
  const change = vi.fn();
  const view = render(
    <DocumentOutputControls config={config} onChange={change} />,
  );
  expect((screen.getByLabelText(/^QR padding/) as HTMLInputElement).value).toBe(
    "0",
  );
  fireEvent.change(screen.getByLabelText(/^Default identifier length/), {
    target: { value: "16" },
  });
  expect(change).toHaveBeenLastCalledWith({ identifier_length: 16 });
  expect(
    (screen.getByLabelText("QR payload characters") as HTMLInputElement).max,
  ).toBe("500");
  fireEvent.change(screen.getByLabelText("QR payload characters"), {
    target: { value: "500" },
  });
  expect(change).toHaveBeenLastCalledWith({ qr_payload_length: 500 });
  fireEvent.click(
    screen.getByLabelText("Require a reviewed QR replacement region"),
  );
  expect(change).toHaveBeenLastCalledWith({ qr_required: true });
  view.rerender(
    <DocumentOutputControls
      config={{ ...config, qr_codes: false }}
      onChange={change}
    />,
  );
  expect(
    (screen.getByLabelText("QR payload characters") as HTMLInputElement)
      .disabled,
  ).toBe(true);
});
