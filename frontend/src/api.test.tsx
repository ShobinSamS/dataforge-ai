import { afterEach, expect, it, vi } from "vitest";
import { api, post } from "./api";

afterEach(() => vi.unstubAllGlobals());

it("explains network failures and never automatically retries a mutation", async () => {
  const fetcher = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
  vi.stubGlobal("fetch", fetcher);
  await expect(post("/templates/demo")).rejects.toThrow(
    "Cannot connect to DataForge",
  );
  expect(fetcher).toHaveBeenCalledTimes(1);
});

it("preserves intentional request cancellation", async () => {
  const error = new DOMException("Cancelled", "AbortError");
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(error));
  await expect(api("/templates")).rejects.toBe(error);
});

it("provides a recovery message for empty API proxy failures", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("", { status: 500 })),
  );
  await expect(api("/templates")).rejects.toThrow("HTTP 500");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("Bad Gateway", { status: 502 })),
  );
  await expect(api("/templates")).rejects.toThrow("npm.cmd start");
});

it("preserves actual backend errors instead of replacing them with connection help", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ detail: "Unsupported image format" }), {
          status: 422,
        }),
      ),
  );
  await expect(api("/templates")).rejects.toThrow("Unsupported image format");
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ detail: "Backend processing error" }), {
          status: 500,
        }),
      ),
  );
  await expect(api("/templates")).rejects.toThrow("Backend processing error");
});

it("retains readable nested validation errors", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: [
              { loc: ["body", "regions", 2, "rule"], msg: "Invalid value" },
            ],
          }),
          { status: 422 },
        ),
      ),
  );
  await expect(api("/templates")).rejects.toThrow(
    "regions → 2 → rule: Invalid value",
  );
});

it("uploads multipart files without overriding their browser-generated boundary", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(
      new Response(JSON.stringify({ id: "new-template" }), { status: 201 }),
    );
  vi.stubGlobal("fetch", fetcher);
  const body = new FormData();
  body.append("file", new File(["fixture"], "new.png", { type: "image/png" }));
  expect(await api("/templates", { method: "POST", body })).toEqual({
    id: "new-template",
  });
  expect(fetcher).toHaveBeenCalledWith(
    "/api/templates",
    expect.objectContaining({ method: "POST", body, headers: {} }),
  );
});
