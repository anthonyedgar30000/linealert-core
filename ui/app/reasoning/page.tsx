import {
  type HistorianStatus,
  type HistoryPayload,
  ReasoningInputsClient,
} from "./reasoning-client";

const historianBaseUrl =
  process.env.LINEALERT_HISTORIAN_URL ?? "http://127.0.0.1:8767";

export const dynamic = "force-dynamic";

const unavailableStatus: HistorianStatus = {
  connected: false,
  source_available: false,
  reason_code: "EVIDENCE.HISTORIAN_UNAVAILABLE",
};

const unavailableHistory: HistoryPayload = {
  persistence: "Historian not available",
  count: 0,
  truncated: false,
  records: [],
  reason_code: "EVIDENCE.HISTORIAN_UNAVAILABLE",
};

async function readInitialHistorianState(): Promise<{
  status: HistorianStatus;
  history: HistoryPayload;
  reachable: boolean;
}> {
  try {
    const [statusResponse, historyResponse] = await Promise.all([
      fetch(new URL("/api/status", historianBaseUrl), {
        cache: "no-store",
        signal: AbortSignal.timeout(1500),
      }),
      fetch(new URL("/api/history/functional-temporal?limit=8", historianBaseUrl), {
        cache: "no-store",
        signal: AbortSignal.timeout(1500),
      }),
    ]);

    const [statusPayload, historyPayload] = await Promise.all([
      statusResponse.json() as Promise<HistorianStatus>,
      historyResponse.json() as Promise<HistoryPayload>,
    ]);

    return {
      status: statusPayload,
      history: historyPayload,
      reachable: statusResponse.ok && historyResponse.ok,
    };
  } catch {
    return {
      status: unavailableStatus,
      history: unavailableHistory,
      reachable: false,
    };
  }
}

export default async function ReasoningInputs() {
  const initial = await readInitialHistorianState();

  return (
    <ReasoningInputsClient
      initialStatus={initial.status}
      initialHistory={initial.history}
      initialReachable={initial.reachable}
    />
  );
}
