import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import FontControls from "./FontControls";
import { defaultRuleOptions } from "./RegionRuleControls";
import { api, post } from "../api";
import type { Region } from "../types";

vi.mock("../api", () => ({ api: vi.fn(), post: vi.fn() }));
afterEach(cleanup);
it("uses the selected source region for matching and applies the returned font without clearing its rule", async () => {
  const field: Region = {
    id: "source",
    kind: "identifier",
    label: "Code",
    box: [10, 10, 200, 40],
    text: "ABC1234",
    confidence: 1,
    sensitive: true,
    replace: true,
    confirmed: true,
    page: 0,
    rule: "employee code",
  };
  const changed = {
    ...field,
    confirmed: false,
    rule_options: { ...defaultRuleOptions, font_id: "arial", font_size: 24 },
  };
  vi.mocked(api).mockResolvedValue([{ id: "arial", label: "Arial Regular" }]);
  vi.mocked(post).mockResolvedValue({
    region: changed,
    match: {
      label: "Arial Regular",
      similarity: 0.93,
      warning: "Estimate only",
    },
  });
  const change = vi.fn();
  render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false, gcTime: 0 } },
        })
      }
    >
      <FontControls
        field={field}
        options={defaultRuleOptions}
        templateId="fixture"
        onChange={change}
      />
    </QueryClientProvider>,
  );
  await screen.findByText("Arial Regular");
  fireEvent.click(screen.getByText("Match source font"));
  await screen.findByText(/shape similarity 93%/);
  expect(post).toHaveBeenCalledWith("/templates/fixture/font-match", {
    region: field,
  });
  expect(change).toHaveBeenLastCalledWith(changed);
  expect(changed.rule).toBe("employee code");
  fireEvent.change(screen.getByLabelText("Font weight"), {
    target: { value: "bold" },
  });
  expect(change).toHaveBeenLastCalledWith(
    expect.objectContaining({
      confirmed: false,
      rule_options: expect.objectContaining({ font_weight: "bold" }),
    }),
  );
  fireEvent.change(screen.getByLabelText("Text background cleanup"), {
    target: { value: "solid" },
  });
  expect(change).toHaveBeenLastCalledWith(
    expect.objectContaining({
      rule_options: expect.objectContaining({
        background_mode: "solid",
        background_color: "#ffffff",
      }),
    }),
  );
});
