export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch("/api" + path, {
      ...options,
      headers:
        options.body instanceof FormData
          ? {}
          : { "Content-Type": "application/json", ...options.headers },
    });
  } catch (error) {
    if (
      typeof error === "object" &&
      error !== null &&
      "name" in error &&
      error.name === "AbortError"
    )
      throw error;
    throw new Error(
      "Cannot connect to DataForge. Start or restart it with npm.cmd start in the project folder, keep that terminal open, then refresh this page.",
    );
  }
  if (!response.ok) {
    let error;
    try {
      error = await response.json();
    } catch {
      error = null;
    }
    const fallback =
      response.status >= 500
        ? `DataForge API request failed (HTTP ${response.status}). Check that the backend is running; start or restart the app with npm.cmd start and keep that terminal open.`
        : response.statusText || `Request failed (HTTP ${response.status})`;
    throw new Error(
      typeof error?.detail === "string" && error.detail.trim()
        ? error.detail
        : Array.isArray(error?.detail)
          ? error.detail
              .map(
                (issue: { loc?: (string | number)[]; msg?: string }) =>
                  `${issue.loc?.filter((part) => part !== "body").join(" → ") || "Request"}: ${issue.msg || "Invalid value"}`,
              )
              .join("; ")
          : error?.detail
            ? JSON.stringify(error.detail)
            : fallback,
    );
  }
  return response.json();
}
export const post = <T>(path: string, body: unknown = {}) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
