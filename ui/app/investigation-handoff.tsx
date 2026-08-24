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
  relationshipId: string;
  episodeId: string;
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
  history?: "persisted" | "unavailable";
};

type HistorianState = {
  state: "unknown" | "active" | "unavailable";
  count?: number;
};

type HistorianMeasurement = {
  observed_at: string;
  observation_id: string;
  episode_id: string;
  asset_id: string;
  relationship_id: string;
  signal: string;
  value: number;
  unit: string;
  min_value: number;
  max_value: number;
  temporal_rule_status: string;
  quality: string;
  reason_code: string;
  correlation_id: string;
  topology_from: string;
  topology_to: string;
  source_mode: string;
};

type HistorianOutcome = {
  recorded_at: string;
  outcome_id: string;
  asset_id: string;
  relationship_id: string;
  outcome_type: string;
  status: string;
  actor_role?: string | null;
  note?: string | null;
  related_observation_id?: string | null;
  verification_value?: number | null;
  verification_unit?: string | null;
  verification_status?: string | null;
};

type HistorianEpisode = {
  schema_version: string;
  episode_id: string;
  condition_measurements: HistorianMeasurement[];
  outcomes: HistorianOutcome[];
  claim_boundary?: string;
};

type EpisodeTimelineState = {
  state: "idle" | "active" | "unavailable";
  episode?: HistorianEpisode;
};

type EpisodeMoment = {
  key: string;
  label: string;
  detail: string;
  timestamp: string;
  tone: "normal" | "attention" | "outcome" | "recovered";
  meta: string;
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

const isOutsideEnvelope = (measurement: HistorianMeasurement) => (
  measurement.value < measurement.min_value || measurement.value > measurement.max_value
);

const formatEpisodeTime = (timestamp: string) => {
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) return timestamp;
  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const buildEpisodeMoments = (episode: HistorianEpisode): EpisodeMoment[] => {
  const measurements = episode.condition_measurements ?? [];
  const outcomes = episode.outcomes ?? [];
  if (!measurements.length && !outcomes.length) return [];

  const moments: EpisodeMoment[] = [];
  const first = measurements.at(0);
  const firstOutside = measurements.find(isOutsideEnvelope);
  const latest = measurements.at(-1);

  if (first) {
    moments.push({
      key: `start:${first.observation_id}`,
      label: "Episode evidence begins",
      detail: `${first.value.toFixed(0)} ${first.unit} · ${isOutsideEnvelope(first) ? "outside" : "inside"} commissioned envelope`,
      timestamp: first.observed_at,
      tone: isOutsideEnvelope(first) ? "attention" : "normal",
      meta: first.correlation_id,
    });
  }

  if (firstOutside && firstOutside.observation_id !== first?.observation_id) {
    moments.push({
      key: `deviation:${firstOutside.observation_id}`,
      label: "First boundary exit",
      detail: `${firstOutside.value.toFixed(0)} ${firstOutside.unit} · ${firstOutside.temporal_rule_status}`,
      timestamp: firstOutside.observed_at,
      tone: "attention",
      meta: firstOutside.correlation_id,
    });
  }

  if (latest && latest.observation_id !== first?.observation_id) {
    moments.push({
      key: `latest:${latest.observation_id}`,
      label: "Latest persisted condition",
      detail: `${latest.value.toFixed(0)} ${latest.unit} · ${latest.temporal_rule_status}`,
      timestamp: latest.observed_at,
      tone: isOutsideEnvelope(latest) ? "attention" : "normal",
      meta: latest.correlation_id,
    });
  }

  const operatorOutcomes = outcomes.filter((outcome) => outcome.actor_role === "operator_view");
  const visibleOutcomes = (operatorOutcomes.length ? operatorOutcomes : outcomes).slice(-2);
  for (const outcome of visibleOutcomes) {
    const recovered = outcome.status === "recovered";
    const value = typeof outcome.verification_value === "number"
      ? `${outcome.verification_value.toFixed(0)} ${outcome.verification_unit ?? ""}`.trim()
      : "Outcome recorded";
    moments.push({
      key: `outcome:${outcome.outcome_id}`,
      label: recovered ? "Recovery verification recorded" : "Verification recorded",
      detail: `${value} · ${outcome.status}`,
      timestamp: outcome.recorded_at,
      tone: recovered ? "recovered" : "outcome",
      meta: outcome.actor_role ?? outcome.outcome_type,
    });
  }

  return moments.sort((left, right) => (
    new Date(left.timestamp).getTime() - new Date(right.timestamp).getTime()
  ));
};

const subscribeLocation = () => () => undefined;
const getPathname = () => window.location.pathname;
const getSearch = () => window.location.search;
const getServerLocation = () => "";

function EpisodeTimeline({ timeline }: { timeline: EpisodeTimelineState }) {
  if (timeline.state === "idle") {
    return (
      <section className={styles.episodeTimeline} aria-label="Shared historian episode timeline">
        <div className={styles.timelineHeader}>
          <div>
            <span>SHARED EPISODE</span>
            <b>Loading durable evidence timeline…</b>
          </div>
        </div>
      </section>
    );
  }

  if (timeline.state === "unavailable" || !timeline.episode) {
    return (
      <section className={styles.episodeTimeline} aria-label="Shared historian episode timeline">
        <div className={styles.timelineHeader}>
          <div>
            <span>SHARED EPISODE</span>
            <b>Durable timeline unavailable</b>
          </div>
          <small>Live evidence remains usable; no historical inference is substituted.</small>
        </div>
      </section>
    );
  }

  const episode = timeline.episode;
  const moments = buildEpisodeMoments(episode);
  return (
    <section className={styles.episodeTimeline} aria-label="Shared historian episode timeline">
      <div className={styles.timelineHeader}>
        <div>
          <span>SHARED EPISODE · {episode.episode_id}</span>
          <b>{episode.condition_measurements.length} measurements · {episode.outcomes.length} outcome records</b>
        </div>
        <small>Sequence and association only · root cause is not inferred</small>
      </div>
      {moments.length > 0 ? (
        <div className={styles.timelineTrack}>
          {moments.map((moment) => (
            <article
              className={`${styles.timelineMoment} ${styles[`timeline_${moment.tone}`]}`}
              key={moment.key}
            >
              <span className={styles.timelineDot} aria-hidden="true" />
              <small>{formatEpisodeTime(moment.timestamp)}</small>
              <b>{moment.label}</b>
              <p>{moment.detail}</p>
              <em>{moment.meta}</em>
            </article>
          ))}
        </div>
      ) : (
        <small className={styles.timelineEmpty}>Episode exists but has no retained records yet.</small>
      )}
    </section>
  );
}

export default function InvestigationHandoff() {
  const path = useSyncExternalStore(subscribeLocation, getPathname, getServerLocation);
  const search = useSyncExternalStore(subscribeLocation, getSearch, getServerLocation);
  const [healthContext, setHealthContext] = useState<HandoffContext | null>(null);
  const [historian, setHistorian] = useState<HistorianState>({ state: "unknown" });
  const [episodeTimeline, setEpisodeTimeline] = useState<EpisodeTimelineState>({ state: "idle" });
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
      relationshipId: params.get("relationshipId") ?? "relationship:label-presentation-delay",
      episodeId: params.get("episodeId") ?? "condition-runtime-replay",
      signal: params.get("signal") ?? "label_presentation_delay_ms",
      latest,
      unit: params.get("unit") ?? "ms",
      min,
      max,
      violations,
      status: params.get("status") === "DEGRADED"
        ? "DEGRADED"
        : params.get("status") === "DRIFTING"
          ? "DRIFTING"
          : "HEALTHY",
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
          (observation) => observation.value < observation.min_value
            || observation.value > observation.max_value,
        ).length;
        const latestOutside = latest.value < latest.min_value || latest.value > latest.max_value;
        const status: HandoffContext["status"] = violations >= 3
          ? "DEGRADED"
          : latestOutside
            ? "DRIFTING"
            : "HEALTHY";
        const sourceMode = payload.source_mode ?? "unknown";

        setHealthContext({
          asset: latest.asset_id || "label-application-station",
          relationship: humanizeRelationship(latest.topology_from, latest.topology_to),
          relationshipId: latest.relationship_id ?? `relationship:${latest.signal}`,
          episodeId: sourceMode === "deterministic_event_replay"
            ? "condition-runtime-replay"
            : `runtime:${latest.correlation_id ?? latest.observation_id ?? latest.signal}`,
          signal: latest.signal,
          latest: latest.value,
          unit: latest.unit,
          min: latest.min_value,
          max: latest.max_value,
          violations,
          status,
          sourceMode,
          observationId: latest.observation_id,
          correlationId: latest.correlation_id,
        });
      } catch {
        // The health page already exposes runtime availability. Keep the handoff quiet if unavailable.
      }
    };

    const readHistorian = async () => {
      try {
        const response = await fetch("/api/historian/conditions?limit=1", { cache: "no-store" });
        if (!active) return;
        if (!response.ok) {
          setHistorian({ state: "unavailable" });
          return;
        }
        const payload = (await response.json()) as { count?: number };
        setHistorian({ state: "active", count: payload.count ?? 0 });
      } catch {
        if (active) setHistorian({ state: "unavailable" });
      }
    };

    readCondition();
    readHistorian();
    const conditionTimer = window.setInterval(readCondition, 1500);
    const historianTimer = window.setInterval(readHistorian, 3000);
    return () => {
      active = false;
      window.clearInterval(conditionTimer);
      window.clearInterval(historianTimer);
    };
  }, [path]);

  const episodeId = path === "/health"
    ? healthContext?.episodeId
    : incomingContext?.episodeId;

  useEffect(() => {
    if ((path !== "/" && path !== "/health") || !episodeId) return;
    let active = true;

    const readEpisode = async () => {
      try {
        const response = await fetch(
          `/api/historian/episodes/${encodeURIComponent(episodeId)}?limit=500`,
          { cache: "no-store" },
        );
        if (!active) return;
        if (!response.ok) {
          setEpisodeTimeline({ state: "unavailable" });
          return;
        }
        const episode = (await response.json()) as HistorianEpisode;
        setEpisodeTimeline({ state: "active", episode });
      } catch {
        if (active) setEpisodeTimeline({ state: "unavailable" });
      }
    };

    readEpisode();
    const timer = window.setInterval(readEpisode, 2500);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [episodeId, path, verification.history]);

  const investigationHref = useMemo(() => {
    if (!healthContext) return "/?source=health";
    const params = new URLSearchParams({
      source: "health",
      focus: "label-presentation-response",
      asset: healthContext.asset,
      relationship: healthContext.relationship,
      relationshipId: healthContext.relationshipId,
      episodeId: healthContext.episodeId,
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

  const persistVerification = async (
    context: HandoffContext,
    observation: RuntimeObservation,
    recovered: boolean,
  ) => {
    try {
      const response = await fetch("/api/historian/outcomes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          episode_id: context.episodeId,
          asset_id: context.asset,
          relationship_id: context.relationshipId,
          outcome_type: "condition_verification",
          status: recovered ? "recovered" : "persists",
          actor_role: "operator_view",
          related_observation_id: observation.observation_id,
          verification_value: observation.value,
          verification_unit: observation.unit,
          verification_status: recovered
            ? "inside_commissioned_envelope"
            : "outside_commissioned_envelope",
          details: {
            handoff_observation_id: context.observationId,
            handoff_correlation_id: context.correlationId,
            verification_correlation_id: observation.correlation_id,
            source_mode: context.sourceMode,
          },
        }),
        cache: "no-store",
      });
      return response.ok;
    } catch {
      return false;
    }
  };

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
          && humanizeRelationship(observation.topology_from, observation.topology_to)
            === incomingContext.relationship,
      ) ?? [];
      const latest = matching.at(-1);
      if (!latest) {
        setVerification({ state: "unavailable" });
        return;
      }

      const recovered = latest.value >= latest.min_value && latest.value <= latest.max_value;
      const persisted = await persistVerification(incomingContext, latest, recovered);
      setVerification({
        state: recovered ? "recovered" : "persists",
        latest: latest.value,
        unit: latest.unit,
        min: latest.min_value,
        max: latest.max_value,
        history: persisted ? "persisted" : "unavailable",
      });
    } catch {
      setVerification({ state: "unavailable" });
    }
  };

  if (path === "/health") {
    const episode = episodeTimeline.episode;
    const latestPersisted = episode?.condition_measurements.at(-1);
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
          {episodeTimeline.state === "active" && episode && (
            <small className={styles.healthHistorySummary}>
              Shared episode · {episode.condition_measurements.length} measurements · {episode.outcomes.length} outcomes
              {latestPersisted ? ` · latest persisted ${latestPersisted.value.toFixed(0)} ${latestPersisted.unit}` : ""}
            </small>
          )}
          {historian.state === "active" && episodeTimeline.state !== "active" && (
            <small>Shared history active · loading durable episode</small>
          )}
          {historian.state === "unavailable" && (
            <small>Shared history unavailable · live evidence remains visible</small>
          )}
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
      <EpisodeTimeline timeline={episodeTimeline} />
      {verification.state !== "idle" && (
        <div className={`${styles.verificationResult} ${styles[`verification_${verification.state}`]}`} role="status">
          {verification.state === "checking" && <><span>VERIFYING ORIGINAL RELATIONSHIP</span><b>Reading the latest admitted condition measurement…</b></>}
          {verification.state === "recovered" && <><span>CONDITION RECOVERED</span><b>{verification.latest?.toFixed(0)} {verification.unit} is inside {verification.min}–{verification.max} {verification.unit}.</b><small>Recovery is established for this relationship; physical root cause is still not proven.</small></>}
          {verification.state === "persists" && <><span>DEGRADATION PERSISTS</span><b>{verification.latest?.toFixed(0)} {verification.unit} remains outside {verification.min}–{verification.max} {verification.unit}.</b><small>Continue the bounded investigation; a local improvement elsewhere did not clear the original condition.</small></>}
          {verification.state === "unavailable" && <><span>VERIFICATION UNAVAILABLE</span><b>No fresh admitted measurement for the original relationship is available.</b><small>Do not infer recovery from a different metric or scenario outcome.</small></>}
          {verification.history === "persisted" && <small>Verification appended to the shared historian episode.</small>}
          {verification.history === "unavailable" && <small>Shared historian unavailable; this verification is live-only.</small>}
        </div>
      )}
      <div className={styles.operatorActions}>
        <a href="/health">← Machine Health</a>
        <button
          className={styles.verifyAction}
          type="button"
          onClick={verifyCondition}
          disabled={verification.state === "checking"}
        >
          Verify original condition
        </button>
        <span>Context retained from the condition evidence chain</span>
      </div>
    </aside>
  );
}
