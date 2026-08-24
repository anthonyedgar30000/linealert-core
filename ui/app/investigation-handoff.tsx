"use client";

import { useEffect, useMemo, useState } from "react";

import styles from "./investigation-handoff.module.css";

type RuntimeObservation = {
  signal: string;
  value: number;
  unit: string;
  min_value: number;
  max_value: number;
  asset_id: string;
  relationship_id?: string;
  observation_id?: string;
  correlation_id?: string;
  topology_from: string;
  topology_to: string;
  quality: string;
};

type ConditionPayload = {
  configured?: boolean;
  source_mode?: string;
  condition?: {
    condition_signals?: {
      observations?: RuntimeObservation[];
    };
  } | null;
};

type HandoffContext = {
  asset: string;
  relationship: string;
  signal: string;
  latest: number;
  unit: string;
  min: number;
  max: number;
  violations: number;
  status: "HEALTHY" | "DRIFTING" | "DEGRADED";
  sourceMode: string;
  observationId?: string;
  correlationId?: string;
};

const humanizeRelationship = (from: string, to: string) => {
  const labels: Record<string, string> = {
    LabelFeedCommand: "Label feed command",
    LabelAtPeelPoint: "Label at peel point",
  };
  return `${labels[from] ?? from} → ${labels[to] ?? to}`;
};

const parseNumber = (value: string | null) => {
  if (value === null) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

export default function InvestigationHandoff() {
  const [path, setPath] = useState<string | null>(null);
  const [healthContext, setHealthContext] = useState<HandoffContext | null>(null);
  const [incomingContext, setIncomingContext] = useState<HandoffContext | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    setPath(window.location.pathname);

    if (window.location.pathname !== "/") return;

    const params = new URLSearchParams(window.location.search);
    if (params.get("source") !== "health") return;

    const latest = parseNumber(params.get("latest"));
    const min = parseNumber(params.get("min"));
    const max = parseNumber(params.get("max"));
    const violations = parseNumber(params.get("violations"));
    if (latest === null || min === null || max === null || violations === null) return;

    setIncomingContext({
      asset: params.get("asset") ?? "label-application-station",
      relationship: params.get("relationship") ?? "Label feed command → Label at peel point",
      signal: params.get("signal") ?? "label_presentation_delay_ms",
      latest,
      unit: params.get("unit") ?? "ms",
      min,
      max,
      violations,
      status: params.get("status") === "DEGRADED" ? "DEGRADED" : params.get("status") === "DRIFTING" ? "DRIFTING" : "HEALTHY",
      sourceMode: params.get("sourceMode") ?? "unknown",
      observationId: params.get("observationId") ?? undefined,
      correlationId: params.get("correlationId") ?? undefined,
    });
  }, []);

  useEffect(() => {
    if (path !== "/health") return;
    let active = true;

    const readCondition = async () => {
      try {
        const response = await fetch("/api/condition", { cache: "no-store" });
        if (!response.ok) return;
        const payload = (await response.json()) as ConditionPayload;
        const observations = payload.condition?.condition_signals?.observations?.filter(
          (observation) => observation.quality === "good" && Number.isFinite(observation.value),
        ) ?? [];
        const latest = observations.at(-1);
        if (!active || !latest) return;

        const related = observations.filter(
          (observation) => observation.signal === latest.signal,
        );
        const violations = related.filter(
          (observation) => observation.value < observation.min_value || observation.value > observation.max_value,
        ).length;
        const latestOutside = latest.value < latest.min_value || latest.value > latest.max_value;
        const status: HandoffContext["status"] = violations >= 3
          ? "DEGRADED"
          : latestOutside
            ? "DRIFTING"
            : "HEALTHY";

        setHealthContext({
          asset: latest.asset_id || "label-application-station",
          relationship: humanizeRelationship(latest.topology_from, latest.topology_to),
          signal: latest.signal,
          latest: latest.value,
          unit: latest.unit,
          min: latest.min_value,
          max: latest.max_value,
          violations,
          status,
          sourceMode: payload.source_mode ?? "unknown",
          observationId: latest.observation_id,
          correlationId: latest.correlation_id,
        });
      } catch {
        // The health page already exposes runtime availability. Keep the handoff quiet if unavailable.
      }
    };

    readCondition();
    const timer = window.setInterval(readCondition, 1500);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [path]);

  const investigationHref = useMemo(() => {
    if (!healthContext) return "/?source=health&fault=alignment";
    const params = new URLSearchParams({
      source: "health",
      fault: "alignment",
      asset: healthContext.asset,
      relationship: healthContext.relationship,
      signal: healthContext.signal,
      latest: String(healthContext.latest),
      unit: healthContext.unit,
      min: String(healthContext.min),
      max: String(healthContext.max),
      violations: String(healthContext.violations),
      status: healthContext.status,
      sourceMode: healthContext.sourceMode,
      claim: "relationship-degradation-only",
    });
    if (healthContext.observationId) params.set("observationId", healthContext.observationId);
    if (healthContext.correlationId) params.set("correlationId", healthContext.correlationId);
    return `/?${params.toString()}`;
  }, [healthContext]);

  if (path === "/health") {
    return (
      <aside className={styles.healthHandoff} aria-label="Condition investigation handoff">
        <div>
          <span className={styles.kicker}>NEXT WORKFLOW</span>
          <strong>Investigate in Operator View</strong>
          <small>
            {healthContext
              ? `${healthContext.latest.toFixed(0)} ${healthContext.unit} latest · ${healthContext.violations} envelope violation${healthContext.violations === 1 ? "" : "s"}`
              : "Pass the current station condition into the troubleshooting workflow"}
          </small>
        </div>
        <a className={styles.primaryAction} href={investigationHref}>Investigate →</a>
      </aside>
    );
  }

  if (path !== "/" || !incomingContext || dismissed) return null;

  const replayLabel = incomingContext.sourceMode === "deterministic_event_replay"
    ? "Replay evidence"
    : "Runtime evidence";

  return (
    <aside className={styles.operatorHandoff} aria-label="Incoming condition investigation">
      <div className={styles.operatorHeader}>
        <div>
          <span className={styles.kicker}>CONDITION HANDOFF · {replayLabel.toUpperCase()}</span>
          <strong>{incomingContext.status}: {incomingContext.relationship}</strong>
        </div>
        <button type="button" onClick={() => setDismissed(true)} aria-label="Dismiss condition handoff">×</button>
      </div>
      <div className={styles.contextGrid}>
        <div><span>Latest</span><b>{incomingContext.latest.toFixed(0)} {incomingContext.unit}</b></div>
        <div><span>Commissioned</span><b>{incomingContext.min}–{incomingContext.max} {incomingContext.unit}</b></div>
        <div><span>Violations</span><b>{incomingContext.violations}</b></div>
        <div><span>Suggested scenario</span><b>Arrival phase drift</b></div>
      </div>
      <p>
        Condition monitoring has established relationship degradation only. Physical root cause remains unproven; use the role-bounded operator workflow to inspect, escalate, and verify recovery.
      </p>
      <div className={styles.operatorActions}>
        <a href="/health">← Machine Health</a>
        <span>Context retained from the condition evidence chain</span>
      </div>
    </aside>
  );
}
