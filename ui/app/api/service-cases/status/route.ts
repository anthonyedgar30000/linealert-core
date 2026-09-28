import { NextResponse } from "next/server";

const serviceCaseBaseUrl = process.env.LINEALERT_SERVICE_CASE_URL ?? "http://127.0.0.1:8768";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const response = await fetch(new URL("/api/status", serviceCaseBaseUrl), {
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
        schema_version: "linealert.service-case-service-status.v1",
        connected: false,
        storage_available: false,
        reason_code: "SERVICE_CASE.LOCAL_STORE_UNAVAILABLE",
        error: error instanceof Error ? error.name : "UnknownError",
        production_record_authority: false,
        equipment_authority: false,
      },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
