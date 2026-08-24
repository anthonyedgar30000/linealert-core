import { NextResponse } from "next/server";

const telemetryBridgeUrl =
  process.env.LINEALERT_BRIDGE_URL ?? "http://127.0.0.1:8765/api/telemetry";

const historyBridgeUrl = process.env.LINEALERT_HISTORY_URL ?? (() => {
  const url = new URL(telemetryBridgeUrl);
  url.pathname = "/api/history";
  url.search = "";
  return url.toString();
})();

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  const requestedLimit = Number(requestUrl.searchParams.get("limit") ?? "240");
  const limit = Number.isFinite(requestedLimit)
    ? Math.max(1, Math.min(Math.trunc(requestedLimit), 2000))
    : 240;

  const target = new URL(historyBridgeUrl);
  target.searchParams.set("limit", String(limit));

  try {
    const response = await fetch(target, {
      cache: "no-store",
      signal: AbortSignal.timeout(1500),
    });
    if (!response.ok) {
      return NextResponse.json(
        {
          schema_version: "linealert.observation.history.v1",
          persistence: "unavailable",
          count: 0,
          observations: [],
          reason_code: "EVIDENCE.HISTORY_BRIDGE_HTTP_ERROR",
        },
        { status: 503, headers: { "Cache-Control": "no-store" } },
      );
    }
    const payload = await response.json();
    return NextResponse.json(payload, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return NextResponse.json(
      {
        schema_version: "linealert.observation.history.v1",
        persistence: "unavailable",
        count: 0,
        observations: [],
        reason_code: "EVIDENCE.HISTORY_BRIDGE_UNAVAILABLE",
        error: error instanceof Error ? error.name : "UnknownError",
      },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
