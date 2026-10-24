import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import RegionRuleControls, { defaultRuleOptions } from "./RegionRuleControls";
import type { Region } from "../types";
vi.mock("../api", () => ({
  api: vi.fn(async () => ({ online_configured: false })),
  post: vi.fn(),
}));
const assets = Array.from({ length: 100 }, (_, index) => ({
  id: index.toString(16).padStart(32, "0"),
  preview_url: "/sample.png",
}));
vi.mock("./DiffusionPanel", () => ({
  default: ({ onUseMany }: { onUseMany: (assets: unknown[]) => void }) => (
    <button onClick={() => onUseMany(assets)}>Use generated batch</button>
  ),
}));
afterEach(cleanup);
it.each(["portrait", "stamp", "seal"] as const)(
  "applies a hundred-image batch to a %s region",
  async (kind) => {
    function Wrapper() {
      const [field, setField] = useState<Region>({
        id: "field",
        label: "Test",
        kind,
        box: [0, 0, 400, 400],
        text: "",
        confidence: 1,
        sensitive: false,
        replace: true,
        confirmed: true,
        page: 0,
        rule: "",
        rule_options: { ...defaultRuleOptions },
      });
      return (
        <>
          <RegionRuleControls
            field={field}
            onChange={(patch) => setField((v) => ({ ...v, ...patch }))}
          />
          <output data-testid="field">{JSON.stringify(field)}</output>
        </>
      );
    }
    render(
      <QueryClientProvider
        client={
          new QueryClient({
            defaultOptions: { queries: { retry: false, gcTime: 0 } },
          })
        }
      >
        <Wrapper />
      </QueryClientProvider>,
    );
    fireEvent.click(screen.getByText("Use generated batch"));
    await waitFor(() => {
      const field = JSON.parse(screen.getByTestId("field").textContent!);
      expect(
        field.rule_options[
          kind === "seal" ? "seal_artwork_ids" : "portrait_asset_ids"
        ],
      ).toHaveLength(100);
      if (kind === "seal")
        expect(field.rule_options.seal_style).toBe("corporate");
      else expect(field.rule_options.portrait_source).toBe("asset_pool");
    });
  },
);
