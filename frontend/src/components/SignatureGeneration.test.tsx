import { afterEach, it, expect, vi } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SignatureGeneration from "./SignatureGeneration";
import type { Config, Template } from "../types";
import { api } from "../api";
vi.mock("../api", () => ({ api: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
it("explains fixed saved styles and previews the batch override without changing the template", async () => {
  const config = {
    signatures: true,
    seed: 42,
    signature_content_override: "mixed",
  } as Config;
  const template = {
    regions: [
      {
        id: "s",
        kind: "signature",
        replace: true,
        label: "Signer",
        rule_options: {
          signature_style: "flourish",
          ink_opacity_mode: "fixed",
          ink_opacity: 0.3,
          signature_thickness: 2.2,
        },
      },
    ],
  } as Template;
  const onChange = vi.fn();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrap = (c: Config) => (
    <QueryClientProvider client={qc}>
      <SignatureGeneration config={c} template={template} onChange={onChange} />
    </QueryClientProvider>
  );
  const view = render(wrap(config));
  expect(screen.getByText(/Signer: flourish/)).toBeTruthy();
  expect(api).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Signature variety for this batch"), {
    target: { value: "mixed" },
  });
  expect(onChange).toHaveBeenCalledWith({ signature_style_override: "mixed" });
  view.rerender(wrap({ ...config, signature_style_override: "mixed" }));
  vi.mocked(api).mockResolvedValue([
    { style: "gestural", url: "/api/signatures/preview?seed=42" },
  ]);
  fireEvent.click(screen.getByText("Preview signature variations"));
  await waitFor(() =>
    expect(screen.getByAltText("Fictional gestural signature 1")).toBeTruthy(),
  );
  const query = new URL(vi.mocked(api).mock.calls[0][0], "http://local")
    .searchParams;
  expect(query.get("signature_content")).toBe("mixed");
  expect(query.get("ink_opacity")).toBe("0.3");
  expect(query.get("signature_thickness")).toBe("2.2");
  expect(query.get("text_color")).toBe("#000000");
  expect(query.getAll("color_palette")).toHaveLength(5);
  fireEvent.change(screen.getByLabelText("Signature content for this batch"), {
    target: { value: "alphabet" },
  });
  expect(onChange).toHaveBeenLastCalledWith({
    signature_content_override: "alphabet",
  });
  fireEvent.change(screen.getByLabelText("Signature variety for this batch"), {
    target: { value: "template" },
  });
  expect(onChange).toHaveBeenLastCalledWith({ signature_style_override: null });
  expect(template.regions[0].rule_options?.signature_style).toBe("flourish");
});
