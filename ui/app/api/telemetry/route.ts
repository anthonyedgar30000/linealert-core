import { NextResponse } from "next/server";

const bridgeUrl = process.env.LINEALERT_BRIDGE_URL ?? "http://127.0.0.1:8765/api/telemetry";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const response = await fetch(bridgeUrl, { cache: "no-store", signal: AbortSignal.timeout(1500) });
    if (!response.ok) {
      return NextResponse.json(
        { connected: false, reason_code: "EVIDENCE.BRIDGE_HTTP_ERROR", signals: {} },
        { status: 503, headers: { "Cache-Control": "no-store" } },
      );
    }
    const payload = await response.json();
    return NextResponse.json(payload, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return NextResponse.json(
      {
        connected: false,
        reason_code: "EVIDENCE.BRIDGE_UNAVAILABLE",
        error: error instanceof Error ? error.name : "UnknownError",
        signals: {},
      },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
