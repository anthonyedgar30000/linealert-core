"use client";

import { useEffect, useMemo, useState } from "react";

import styles from "./functional-temporal-comparison.module.css";

type FunctionalTemporalHistoryRecord = {
  observed_at: string;
  record_id: string;
  cycle_id: string;
  record_kind: string;
  phase_id?: string | null;
  transition_id?: string | null;
  requirement_id?: string | null;
  epistemic_state: string;
};

type FunctionalTemporalHistoryPayload = {
  count: number;
  truncated?: boolean;
  records?: FunctionalTemporalHistoryRecord[];
  reason_code?: string;
};

type ComparisonMetric = {
  evidence_key: string;
  semantic?: string | null;
  unit: string;
  reference_value: number;
  selected_value: number;
  delta: number;
  reference_status?: string | null;
  selected_status?: string | null;
};

type ComparisonPoint = {
  identity: {
    key: string;
    record_kind: string;
    component_id: string;
    phase_id?: string | null;
    requirement_id?: string | null;
    transition_id?: string | null;
    record_semantic: string;
  };
  disposition: string;
  reference_state?: string | null;
  selected_state?: string | null;
  first_divergence_at?: string | null;
  metric_deltas: ComparisonMetric[];
  reasons: string[];
};

type ComparisonRefusal = {
  reason_code: string;
  detail: string;
  fields: string[];
};

type SelectedComparisonPayload = {
  disposition: string;
  reason_code?: string | null;
  detail?: string | null;
  reference?: {
    label: string;
    cycle_id?: string | null;
    record_count: number;
    truncated: boolean;
  };
  selected?: {
    label: string;
    cycle_id?: string | null;
    record_count: number;
    truncated: boolean;
  };
  comparison?: {
    disposition: string;
    reference_label: string;
    selected_label: string;
    changed_count: number;
    unresolved_count: number;
    reference_start?: string | null;
    reference_end?: string | null;
    selected_start?: string | null;
    selected_end?: string | null;
    claim_boundary: string;
    refusals: ComparisonRefusal[];
    points: ComparisonPoint[];
  } | null;
};

type CycleOption = {
  cycleId: string;
  firstObservedAt: string;
  lastObservedAt: string;
  recordCount: number;
};

type CompareState =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "active"; payload: SelectedComparisonPayload }
  | { state: "unavailable"; detail: string };

const formatTime = (value: string) => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
};

const cycleLabel = (cycle: CycleOption) => (
  `${formatTime(cycle.lastObservedAt)} · ${cycle.cycleId} · ${cycle.recordCount} record${cycle.recordCount === 1 ? "" : "s"}`
);

const pointLabel = (point: ComparisonPoint) => (
  point.identity.requirement_id
  ?? point.identity.transition_id
  ?? point.identity.phase_id
  ?? `${point.identity.record_kind} · ${point.identity.record_semantic}`
);

const signed = (value: number) => (
  value > 0 ? `+${value}` : String(value)
);

const firstDivergence = (points: ComparisonPoint[]) => {
  const timestamps = points
    .map((point) => point.first_divergence_at)
    .filter((value): value is string => Boolean(value))
    .sort((left, right) => new Date(left).getTime() - new Date(right).getTime());
  return timestamps.at(0) ?? null;
};

export default function FunctionalTemporalComparison({
  assetId,
  selectedCycleHint,
}: {
  assetId: string;
  selectedCycleHint?: string;
}) {
  const [cycles, setCycles] = useState<CycleOption[]>([]);
  const [historyState, setHistoryState] = useState<"loading" | "active" | "unavailable">("loading");
  const [historyTruncated, setHistoryTruncated] = useState(false);
  const [referenceCycle, setReferenceCycle] = useState("");
  const [selectedCycle, setSelectedCycle] = useState("");
  const [comparison, setComparison] = useState<CompareState>({ state: "idle" });

  useEffect(() => {
    let active = true;

    const readCycles = async () => {
      try {
        const params = new URLSearchParams({
          asset_id: assetId,
          limit: "5000",
        });
        const response = await fetch(
          `/api/historian/functional-temporal?${params.toString()}`,
          { cache: "no-store" },
        );
        if (!active) return;
        if (!response.ok) {
          setHistoryState("unavailable");
          return;
        }
        const payload = (await response.json()) as FunctionalTemporalHistoryPayload;
        const records = payload.records ?? [];
        const grouped = new Map<string, CycleOption>();
        for (const record of records) {
          const existing = grouped.get(record.cycle_id);
          if (!existing) {
            grouped.set(record.cycle_id, {
              cycleId: record.cycle_id,
              firstObservedAt: record.observed_at,
              lastObservedAt: record.observed_at,
              recordCount: 1,
            });
            continue;
          }
          existing.recordCount += 1;
          if (new Date(record.observed_at).getTime() < new Date(existing.firstObservedAt).getTime()) {
            existing.firstObservedAt = record.observed_at;
          }
          if (new Date(record.observed_at).getTime() > new Date(existing.lastObservedAt).getTime()) {
            existing.lastObservedAt = record.observed_at;
          }
        }
        const ordered = [...grouped.values()].sort(
          (left, right) => new Date(right.lastObservedAt).getTime() - new Date(left.lastObservedAt).getTime(),
        );
        setCycles(ordered);
        setHistoryTruncated(Boolean(payload.truncated));
        if (selectedCycleHint && grouped.has(selectedCycleHint)) {
          setSelectedCycle(selectedCycleHint);
        }
        setHistoryState("active");
      } catch {
        if (active) setHistoryState("unavailable");
      }
    };

    readCycles();
    return () => {
      active = false;
    };
  }, [assetId, selectedCycleHint]);

  const canCompare = Boolean(
    referenceCycle
    && selectedCycle
    && referenceCycle !== selectedCycle
    && comparison.state !== "loading",
  );

  const selectedHintMissing = useMemo(
    () => Boolean(
      selectedCycleHint
      && historyState === "active"
      && !cycles.some((cycle) => cycle.cycleId === selectedCycleHint),
    ),
    [cycles, historyState, selectedCycleHint],
  );

  const runComparison = async () => {
    if (!canCompare) return;
    setComparison({ state: "loading" });
    const params = new URLSearchParams({
      asset_id: assetId,
      limit: "1000",
      reference_label: `Reference cycle ${referenceCycle}`,
      reference_cycle_id: referenceCycle,
      selected_label: `Selected cycle ${selectedCycle}`,
      selected_cycle_id: selectedCycle,
    });
    try {
      const response = await fetch(
        `/api/historian/functional-temporal/compare?${params.toString()}`,
        { cache: "no-store" },
      );
      const payload = (await response.json()) as SelectedComparisonPayload;
      if (!response.ok) {
        setComparison({
          state: "unavailable",
          detail: payload.detail ?? payload.reason_code ?? "Comparison request failed.",
        });
        return;
      }
      setComparison({ state: "active", payload });
    } catch {
      setComparison({
        state: "unavailable",
        detail: "Shared functional-temporal comparison is unavailable.",
      });
    }
  };

  const admitted = comparison.state === "active"
    ? comparison.payload.comparison?.disposition === "ADMITTED"
    : false;
  const comparisonResult = comparison.state === "active"
    ? comparison.payload.comparison
    : null;
  const changedPoints = (comparisonResult?.points.filter(
    (point) => point.disposition === "CHANGED",
  ) ?? []).sort((left, right) => {
    const leftTime = left.first_divergence_at
      ? new Date(left.first_divergence_at).getTime()
      : Number.POSITIVE_INFINITY;
    const rightTime = right.first_divergence_at
      ? new Date(right.first_divergence_at).getTime()
      : Number.POSITIVE_INFINITY;
    return leftTime - rightTime || left.identity.key.localeCompare(right.identity.key);
  });
  const divergence = comparisonResult ? firstDivergence(comparisonResult.points) : null;

  return (
    <section className={styles.panel} aria-label="Functional-temporal history comparison">
      <div className={styles.header}>
        <div>
          <span>FUNCTIONAL-TEMPORAL COMPARE · READ ONLY</span>
          <b>Reference ↔ selected cycle</b>
        </div>
        <small>Explicit selection · no automatic commissioning designation</small>
      </div>

      {historyState === "loading" && (
        <div className={styles.status}>Loading persisted phase evidence…</div>
      )}

      {historyState === "unavailable" && (
        <div className={styles.statusAttention}>
          Functional-temporal historian evidence is unavailable. No historical comparison is substituted.
        </div>
      )}

      {historyState === "active" && cycles.length === 0 && (
        <div className={styles.status}>
          No persisted functional-temporal cycles exist for this asset yet.
        </div>
      )}

      {historyState === "active" && cycles.length > 0 && (
        <>
          <div className={styles.selectGrid}>
            <label>
              <span>REFERENCE CYCLE</span>
              <select value={referenceCycle} onChange={(event) => {
                setReferenceCycle(event.target.value);
                setComparison({ state: "idle" });
              }}>
                <option value="">Choose explicit reference…</option>
                {cycles.map((cycle) => (
                  <option key={`reference:${cycle.cycleId}`} value={cycle.cycleId}>
                    {cycleLabel(cycle)}
                  </option>
                ))}
              </select>
              <small>Choosing a reference does not certify it as commissioned truth.</small>
            </label>

            <label>
              <span>SELECTED CYCLE</span>
              <select value={selectedCycle} onChange={(event) => {
                setSelectedCycle(event.target.value);
                setComparison({ state: "idle" });
              }}>
                <option value="">Choose cycle to inspect…</option>
                {cycles.map((cycle) => (
                  <option key={`selected:${cycle.cycleId}`} value={cycle.cycleId}>
                    {cycleLabel(cycle)}
                  </option>
                ))}
              </select>
              <small>
                {selectedCycleHint
                  ? `Current investigation hint: ${selectedCycleHint}`
                  : "Select the incident/current cycle explicitly."}
              </small>
            </label>
          </div>

          {historyTruncated && (
            <div className={styles.statusAttention}>
              The cycle picker shows only the newest 5,000 records. A comparison still re-reads each chosen cycle independently and will refuse a truncated selection.
            </div>
          )}
          {selectedHintMissing && (
            <div className={styles.statusAttention}>
              The current investigation cycle is not yet present in persisted functional-temporal history.
            </div>
          )}
          {referenceCycle && selectedCycle && referenceCycle === selectedCycle && (
            <div className={styles.statusAttention}>
              Choose two distinct cycles to make a useful comparison.
            </div>
          )}

          <button
            className={styles.compareAction}
            type="button"
            disabled={!canCompare}
            onClick={runComparison}
          >
            {comparison.state === "loading" ? "Comparing…" : "Compare selected cycles"}
          </button>
        </>
      )}

      {comparison.state === "unavailable" && (
        <div className={styles.resultRefused}>
          <span>COMPARISON UNAVAILABLE</span>
          <b>{comparison.detail}</b>
        </div>
      )}

      {comparison.state === "active" && comparison.payload.disposition !== "READY" && (
        <div className={styles.resultRefused}>
          <span>SELECTION NOT ADMITTED</span>
          <b>{comparison.payload.detail ?? comparison.payload.reason_code ?? comparison.payload.disposition}</b>
          <small>The backend selector refused the handoff before comparison.</small>
        </div>
      )}

      {comparison.state === "active" && comparison.payload.disposition === "READY" && !admitted && comparisonResult && (
        <div className={styles.resultRefused}>
          <span>COMPARISON NOT ADMITTED</span>
          <b>{comparisonResult.refusals.at(0)?.detail ?? comparisonResult.disposition}</b>
          {comparisonResult.refusals.at(0)?.fields?.length ? (
            <small>Context fields: {comparisonResult.refusals.at(0)?.fields.join(", ")}</small>
          ) : null}
        </div>
      )}

      {admitted && comparisonResult && (
        <div className={styles.result}>
          <div className={styles.summaryGrid}>
            <div><span>Changed semantics</span><b>{comparisonResult.changed_count}</b></div>
            <div><span>Unresolved</span><b>{comparisonResult.unresolved_count}</b></div>
            <div><span>First divergence</span><b>{divergence ? formatTime(divergence) : "None observed"}</b></div>
          </div>

          {changedPoints.length ? (
            <div className={styles.changeList}>
              {changedPoints.slice(0, 6).map((point) => {
                const metric = point.metric_deltas.at(0);
                return (
                  <article key={point.identity.key}>
                    <div>
                      <span>{point.identity.record_kind} · {point.identity.component_id}</span>
                      <b>{pointLabel(point)}</b>
                    </div>
                    <strong>
                      {point.reference_state ?? "—"} → {point.selected_state ?? "—"}
                    </strong>
                    {metric ? (
                      <p>
                        {metric.reference_value} → {metric.selected_value} {metric.unit}
                        {" · "}{signed(metric.delta)} {metric.unit}
                        {metric.selected_status ? ` · ${metric.selected_status}` : ""}
                      </p>
                    ) : (
                      <p>Retained state/coverage/transition evidence changed.</p>
                    )}
                    {point.first_divergence_at && (
                      <small>First divergence · {formatTime(point.first_divergence_at)}</small>
                    )}
                  </article>
                );
              })}
              {changedPoints.length > 6 && (
                <small className={styles.moreChanges}>
                  Showing the earliest 6 of {changedPoints.length} changed semantics.
                </small>
              )}
            </div>
          ) : (
            <div className={styles.status}>
              No retained state or numeric difference was found in comparable evidence.
            </div>
          )}

          <small className={styles.boundary}>{comparisonResult.claim_boundary}</small>
        </div>
      )}
    </section>
  );
}
