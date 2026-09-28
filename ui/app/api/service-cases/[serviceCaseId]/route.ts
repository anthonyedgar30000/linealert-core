import { NextResponse } from "next/server";

const serviceCaseBaseUrl =
  process.env.LINEALERT_SERVICE_CASE_URL ?? "http://127.0.0.1:8768";

export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ serviceCaseId: string }>;
};

export async function GET(_request: Request, context: RouteContext) {
  try {
    const { serviceCaseId } = await context.params;
    const response = await fetch(
      new URL(
        "/api/service-cases/" + encodeURIComponent(serviceCaseId),
        serviceCaseBaseUrl,
      ),
      {
        cache: "no-store",
        signal: AbortSignal.timeout(1500),
      },
    );
    const payload = await response.json();
    return NextResponse.json(payload, {
      status: response.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    return NextResponse.json(
      {
        schema_version: "linealert.service-case-service-error.v1",
        reason_code: "SERVICE_CASE.LOCAL_STORE_UNAVAILABLE",
        detail: "Local service-case persistence is unavailable.",
        error: error instanceof Error ? error.name : "UnknownError",
        authorized_action: false,
        equipment_effect: "none",
      },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
