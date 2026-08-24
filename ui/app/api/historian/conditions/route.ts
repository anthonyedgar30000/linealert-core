import { NextRequest, NextResponse } from "next/server";

const historianBaseUrl = process.env.LINEALERT_HISTORIAN_URL ?? "http://127.0.0.1:8767";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const source = new URL("/api/history/conditions", historianBaseUrl);
    request.nextUrl.searchParams.forEach((value, key) => source.searchParams.set(key, value));
    const response = await fetch(source, {
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
        schema_version: "linealert.historian.condition-history.v1",
        persistence: "unavailable",
        count: 0,
        measurements: [],
        reason_code: "EVIDENCE.HISTORIAN_UNAVAILABLE",
        error: error instanceof Error ? error.name : "UnknownError",
      },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
