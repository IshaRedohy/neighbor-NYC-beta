export async function api<T = any>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch("/api" + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const data = await response.json().catch(() => ({
    error: "The service is temporarily unavailable. Please try again.",
  }));
  if (
    response.status === 401 &&
    path !== "/me" &&
    !path.startsWith("/auth/") &&
    path !== "/application" &&
    typeof window !== "undefined"
  )
    window.dispatchEvent(new Event("session-expired"));
  if (!response.ok)
    throw Object.assign(
      new Error(data.error || "Something went wrong. Please try again."),
      { status: response.status },
    );
  return data;
}
export const post = (path: string, data: unknown = {}) =>
  api(path, { method: "POST", body: JSON.stringify(data) });
export const initials = (name: string) =>
  name
    .split(" ")
    .slice(0, 2)
    .map((n) => n[0])
    .join("");
export const title = (s: string) => s.replace(/\b\w/g, (c) => c.toUpperCase());
