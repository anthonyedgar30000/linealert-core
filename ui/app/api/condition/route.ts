import { NextResponse } from "next/server";

const telemetryBridgeUrl =
  process.env.LINEALERT_BRIDGE_URL ?? "http://127.0.0.1:8765/api/telemetry";

const conditionBridgeUrl = process.env.LINEALERT_CONDITION_URL ?? (() => {
  const url = new URL(telemetryBridgeUrl);
  url.pathname = "/api/condition";
  url.search = "";
  return url.toString();
})();

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const response = await fetch(conditionBridgeUrl, {
      cache: "no-store",
      signal: AbortSignal.timeout(1500),
    });
    if (!response.ok) {
      return NextResponse.json(
        {
          schema_version: "linealert.condition-runtime.v1",
          configured: false,
          running: false,
          source_mode: "unavailable",
          measurement_count: 0,
          refusal_count: 0,
          reason_code: "EVIDENCE.CONDITION_BRIDGE_HTTP_ERROR",
          condition: null,
        },
        { status: 503, headers: { "Cache-Control": "no-store" } },
      );
    }
    const payload = await response.json();
    return NextResponse.json(payload, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return NextResponse.json(
      {
        schema_version: "linealert.condition-runtime.v1",
        configured: false,
        running: false,
        source_mode: "unavailable",
        measurement_count: 0,
        refusal_count: 0,
        reason_code: "EVIDENCE.CONDITION_BRIDGE_UNAVAILABLE",
        error: error instanceof Error ? error.name : "UnknownError",
        condition: null,
      },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
