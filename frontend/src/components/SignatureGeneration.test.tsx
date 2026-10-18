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
  const config = { signatures: true, seed: 42 } as Config;
  const template = {
    regions: [
      {
        id: "s",
        kind: "signature",
        replace: true,
        label: "Signer",
        rule_options: { signature_style: "flourish" },
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
  expect(api).toHaveBeenCalledWith("/signatures/previews?style=mixed&seed=42");
  fireEvent.change(screen.getByLabelText("Signature variety for this batch"), {
    target: { value: "template" },
  });
  expect(onChange).toHaveBeenLastCalledWith({ signature_style_override: null });
  expect(template.regions[0].rule_options?.signature_style).toBe("flourish");
});
