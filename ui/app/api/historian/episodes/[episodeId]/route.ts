import { NextRequest, NextResponse } from "next/server";

const historianBaseUrl = process.env.LINEALERT_HISTORIAN_URL ?? "http://127.0.0.1:8767";

export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ episodeId: string }>;
};

export async function GET(request: NextRequest, context: RouteContext) {
  try {
    const { episodeId } = await context.params;
    const target = new URL(
      `/api/history/episodes/${encodeURIComponent(episodeId)}`,
      historianBaseUrl,
    );
    const limit = request.nextUrl.searchParams.get("limit");
    if (limit) target.searchParams.set("limit", limit);

    const response = await fetch(target, {
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
        schema_version: "linealert.historian.episode.v1",
        unavailable: true,
        reason_code: "EVIDENCE.HISTORIAN_UNAVAILABLE",
        error: error instanceof Error ? error.name : "UnknownError",
      },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
