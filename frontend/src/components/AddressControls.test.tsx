import { useState } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AddressControls from "./AddressControls";
import { defaultRuleOptions } from "./RegionRuleControls";
import type { RuleOptions } from "../types";
import { api, post } from "../api";
vi.mock("../api", () => ({ api: vi.fn(), post: vi.fn() }));
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api).mockResolvedValue([
    { code: "IN", name: "India", reference_rows: 256 },
    { code: "US", name: "United States", reference_rows: 256 },
  ]);
});
afterEach(cleanup);
function mount() {
  function Wrapper() {
    const [options, set] = useState<RuleOptions>({
      ...defaultRuleOptions,
      address_country: "",
      address_format: "{street}, {city}, {state}, {country}, {postal_code}",
      literal_text: "An old exact address",
    });
    return (
      <>
        <AddressControls
          options={options}
          set={(patch) => set((current) => ({ ...current, ...patch }))}
        />
        <output data-testid="address-options">{JSON.stringify(options)}</output>
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
}
const value = () =>
  JSON.parse(screen.getByTestId("address-options").textContent!);
it("selects a country and preserves component choices, order and line breaks", async () => {
  mount();
  await screen.findByText("India");
  fireEvent.change(screen.getByLabelText("Address country"), {
    target: { value: "IN" },
  });
  expect(value()).toMatchObject({ address_country: "IN", literal_text: null });
  fireEvent.click(screen.getByText("Separate lines"));
  expect(value().address_format).toBe(
    "{street}\n{city}\n{state}\n{country}\n{postal_code}",
  );
  fireEvent.click(screen.getByLabelText("Move postal_code up"));
  expect(value().address_format).toBe(
    "{street}\n{city}\n{state}\n{postal_code}\n{country}",
  );
  fireEvent.click(screen.getByLabelText("City / locality"));
  expect(value().address_format).not.toContain("{city}");
  fireEvent.change(screen.getByLabelText("Address format"), {
    target: { value: "{postal_code} {city}\n{country}" },
  });
  expect(value().address_format).toBe("{postal_code} {city}\n{country}");
});
it("previews with incrementing seeds and clears the old preview after a format edit", async () => {
  vi.mocked(post).mockResolvedValue({
    text: "12 Sample Road\nTest Locality\nIndia 123456",
    country_code: "IN",
    source: "GeoNames",
  });
  mount();
  await screen.findByText("India");
  fireEvent.change(screen.getByLabelText("Address country"), {
    target: { value: "IN" },
  });
  fireEvent.click(screen.getByText("Preview address"));
  await screen.findByLabelText("Generated address");
  expect(post).toHaveBeenLastCalledWith(
    "/addresses/preview",
    expect.objectContaining({ seed: 42 }),
  );
  fireEvent.click(screen.getByText("Another address example"));
  await waitFor(() => expect(post).toHaveBeenCalledTimes(2));
  expect(post).toHaveBeenLastCalledWith(
    "/addresses/preview",
    expect.objectContaining({ seed: 43 }),
  );
  fireEvent.click(screen.getByText("Separate lines"));
  expect(screen.queryByLabelText("Generated address")).toBeNull();
});
it("ignores an outdated response after changing country", async () => {
  let resolve: (value: unknown) => void = () => {};
  vi.mocked(post).mockReturnValue(
    new Promise((r) => {
      resolve = r;
    }),
  );
  mount();
  await screen.findByText("India");
  fireEvent.change(screen.getByLabelText("Address country"), {
    target: { value: "IN" },
  });
  fireEvent.click(screen.getByText("Preview address"));
  fireEvent.change(screen.getByLabelText("Address country"), {
    target: { value: "US" },
  });
  resolve({
    text: "Old India preview",
    country_code: "IN",
    source: "GeoNames",
  });
  await waitFor(() =>
    expect(
      (screen.getByText("Preview address") as HTMLButtonElement).disabled,
    ).toBe(false),
  );
  expect(screen.queryByLabelText("Generated address")).toBeNull();
});
