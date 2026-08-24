const DEFAULT_BRIDGE_URL = "http://127.0.0.1:8765";

const bridgeBaseUrl = () =>
  (process.env.LINEALERT_BRIDGE_URL ?? DEFAULT_BRIDGE_URL).replace(/\/+$/, "");

export async function proxyBridgeJson(path: string): Promise<Response> {
  if (!path.startsWith("/api/")) {
    return Response.json(
      {
        schema_version: "linealert.bridge-proxy-error.v1",
        reachable: false,
        reason_code: "EVIDENCE.BRIDGE_PROXY_PATH_REFUSED",
      },
      { status: 400, headers: { "Cache-Control": "no-store" } },
    );
  }

  try {
    const response = await fetch(`${bridgeBaseUrl()}${path}`, { cache: "no-store" });
    const body = await response.text();
    return new Response(body, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return Response.json(
      {
        schema_version: "linealert.bridge-proxy-error.v1",
        reachable: false,
        reason_code: "EVIDENCE.BRIDGE_UNREACHABLE",
      },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
