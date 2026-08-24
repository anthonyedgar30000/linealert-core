import { NextResponse } from "next/server";

const historianBaseUrl = process.env.LINEALERT_HISTORIAN_URL ?? "http://127.0.0.1:8767";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const response = await fetch(new URL("/api/status", historianBaseUrl), {
      cache: "no-store",
      signal: AbortSignal.timeout(1500),
    });
    const payload = await response.json();
    return NextResponse.json(payload, {
      status: response.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    return NextResponse.json(
      {
        schema_version: "linealert.historian-service-status.v1",
        connected: false,
        source_available: false,
        reason_code: "EVIDENCE.HISTORIAN_UNAVAILABLE",
        error: error instanceof Error ? error.name : "UnknownError",
      },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
