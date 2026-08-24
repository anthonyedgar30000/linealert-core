"use client";

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";

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

type VerificationResult = {
  state: "idle" | "checking" | "recovered" | "persists" | "unavailable";
  latest?: number;
  unit?: string;
  min?: number;
  max?: number;
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

const subscribeLocation = () => () => undefined;
const getPathname = () => window.location.pathname;
const getSearch = () => window.location.search;
const getServerLocation = () => "";

export default function InvestigationHandoff() {
  const path = useSyncExternalStore(subscribeLocation, getPathname, getServerLocation);
  const search = useSyncExternalStore(subscribeLocation, getSearch, getServerLocation);
  const [healthContext, setHealthContext] = useState<HandoffContext | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [verification, setVerification] = useState<VerificationResult>({ state: "idle" });

  const incomingContext = useMemo<HandoffContext | null>(() => {
    if (path !== "/") return null;
    const params = new URLSearchParams(search);
    if (params.get("source") !== "health") return null;

    const latest = parseNumber(params.get("latest"));
    const min = parseNumber(params.get("min"));
    const max = parseNumber(params.get("max"));
    const violations = parseNumber(params.get("violations"));
    if (latest === null || min === null || max === null || violations === null) return null;

    return {
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
    };
  }, [path, search]);

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

  useEffect(() => {
    setVerification({ state: "idle" });
  }, [incomingContext?.observationId, incomingContext?.signal]);

  const investigationHref = useMemo(() => {
    if (!healthContext) return "/?source=health";
    const params = new URLSearchParams({
      source: "health",
      focus: "label-presentation-response",
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

  const verifyCondition = async () => {
    if (!incomingContext) return;
    setVerification({ state: "checking" });
    try {
      const response = await fetch("/api/condition", { cache: "no-store" });
      if (!response.ok) {
        setVerification({ state: "unavailable" });
        return;
      }
      const payload = (await response.json()) as ConditionPayload;
      const matching = payload.condition?.condition_signals?.observations?.filter(
        (observation) => observation.quality === "good"
          && Number.isFinite(observation.value)
          && observation.signal === incomingContext.signal
          && humanizeRelationship(observation.topology_from, observation.topology_to) === incomingContext.relationship,
      ) ?? [];
      const latest = matching.at(-1);
      if (!latest) {
        setVerification({ state: "unavailable" });
        return;
      }

      const recovered = latest.value >= latest.min_value && latest.value <= latest.max_value;
      setVerification({
        state: recovered ? "recovered" : "persists",
        latest: latest.value,
        unit: latest.unit,
        min: latest.min_value,
        max: latest.max_value,
      });
    } catch {
      setVerification({ state: "unavailable" });
    }
  };

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
        <div><span>Investigation target</span><b>Label presentation response</b></div>
      </div>
      <div className={styles.claimBoundary}>
        <div><span>KNOWN</span><b>The command → peel-point relationship is degraded.</b></div>
        <div><span>NOT YET KNOWN</span><b>Which physical, controls, timing, or coordination condition caused it.</b></div>
      </div>
      <p>
        Treat the scenario cards below as candidate checks, not as the explanation for this condition. Improvement in arrival phase or another local metric does not clear the handoff until LineAlert re-measures this original relationship inside its commissioned envelope.
      </p>
      {verification.state !== "idle" && (
        <div className={`${styles.verificationResult} ${styles[`verification_${verification.state}`]}`} role="status">
          {verification.state === "checking" && <><span>VERIFYING ORIGINAL RELATIONSHIP</span><b>Reading the latest admitted condition measurement…</b></>}
          {verification.state === "recovered" && <><span>CONDITION RECOVERED</span><b>{verification.latest?.toFixed(0)} {verification.unit} is inside {verification.min}–{verification.max} {verification.unit}.</b><small>Recovery is established for this relationship; physical root cause is still not proven.</small></>}
          {verification.state === "persists" && <><span>DEGRADATION PERSISTS</span><b>{verification.latest?.toFixed(0)} {verification.unit} remains outside {verification.min}–{verification.max} {verification.unit}.</b><small>Continue the bounded investigation; a local improvement elsewhere did not clear the original condition.</small></>}
          {verification.state === "unavailable" && <><span>VERIFICATION UNAVAILABLE</span><b>No fresh admitted measurement for the original relationship is available.</b><small>Do not infer recovery from a different metric or scenario outcome.</small></>}
        </div>
      )}
      <div className={styles.operatorActions}>
        <a href="/health">← Machine Health</a>
        <button className={styles.verifyAction} type="button" onClick={verifyCondition} disabled={verification.state === "checking"}>Verify original condition</button>
        <span>Context retained from the condition evidence chain</span>
      </div>
    </aside>
  );
}
