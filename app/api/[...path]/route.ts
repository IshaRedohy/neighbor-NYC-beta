import { NextRequest, NextResponse } from "next/server";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
async function proxy(
  req: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  // Set the login cookie on the same host Google will redirect back to.
  if (
    req.method === "GET" &&
    ["auth/google", "auth/cognito"].includes(path.join("/"))
  ) {
    const loginUrl = new URL(
      "/api/" + path.join("/"),
      process.env.APP_URL || "http://localhost:3000",
    );
    if (req.headers.get("host") !== loginUrl.host) {
      return NextResponse.redirect(loginUrl, {
        status: 307,
        headers: { "Cache-Control": "no-store" },
      });
    }
  }
  const target = new URL(
    "/api/" + path.map(encodeURIComponent).join("/"),
    process.env.BACKEND_URL || "http://127.0.0.1:8000",
  );
  target.search = req.nextUrl.search;
  try {
    const headers = new Headers();
    for (const key of [
      "cookie",
      "content-type",
      "origin",
      "x-intake-timestamp",
      "x-intake-signature",
    ]) {
      const value = req.headers.get(key);
      if (value) headers.set(key, value);
    }
    let body: Uint8Array | undefined;
    if (!["GET", "HEAD"].includes(req.method)) {
      const reader = req.body?.getReader();
      const chunks: Uint8Array[] = [];
      let size = 0;
      if (reader)
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          size += value.length;
          if (size > 1048576) {
            await reader.cancel();
            return NextResponse.json(
              { error: "Maximum request size is 1 MB." },
              { status: 413 },
            );
          }
          chunks.push(value);
        }
      body = Buffer.concat(chunks);
    }
    const result = await fetch(target, {
      method: req.method,
      headers,
      body: body as BodyInit,
      redirect: "manual",
      cache: "no-store",
      signal: AbortSignal.timeout(20000),
    });
    const responseHeaders = new Headers({ "Cache-Control": "no-store" });
    for (const key of ["content-type", "location"]) {
      const value = result.headers.get(key);
      if (value) responseHeaders.set(key, value);
    }
    for (const cookie of result.headers.getSetCookie())
      responseHeaders.append("set-cookie", cookie);
    return new NextResponse(result.body, {
      status: result.status,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      {
        error:
          "Could not reach the Python backend. Check its terminal for startup errors and confirm its port matches BACKEND_URL in .env.",
      },
      { status: 503 },
    );
  }
}
export {
  proxy as GET,
  proxy as POST,
  proxy as PATCH,
  proxy as DELETE,
  proxy as PUT,
};
