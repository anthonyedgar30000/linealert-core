"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import OperatorActions, { type OperatorActionObservation } from "./operator-actions";
import styles from "./operator-view.module.css";

type RuntimeObservation = OperatorActionObservation & {
  temporal_rule_status?: string;
};

type ConditionPayload = {
  configured?: boolean;
  running?: boolean;
  source_mode?: string;
  measurement_count?: number;
  refusal_count?: number;
  reason_code?: string;
  claim_boundary?: string;
  condition?: {
    condition_signals?: {
      observations?: RuntimeObservation[];
    };
  } | null;
};

type RuntimeState = {
  state: "loading" | "active" | "unavailable";
  payload?: ConditionPayload;
};

const humanize = (value: string) => value
  .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
  .replaceAll("_", " ")
  .replace(/^./, (letter) => letter.toUpperCase());

const relationshipLabel = (observation: RuntimeObservation) => (
  `${humanize(observation.topology_from)} → ${humanize(observation.topology_to)}`
);

const outsideEnvelope = (observation: RuntimeObservation) => (
  observation.value < observation.min_value || observation.value > observation.max_value
);

export default function OperatorView() {
  const [runtime, setRuntime] = useState<RuntimeState>({ state: "loading" });

  useEffect(() => {
    let active = true;

    const readCondition = async () => {
      try {
        const response = await fetch("/api/condition", { cache: "no-store" });
        if (!response.ok) throw new Error("condition runtime unavailable");
        const payload = (await response.json()) as ConditionPayload;
        if (active) setRuntime({ state: "active", payload });
      } catch {
        if (active) setRuntime({ state: "unavailable" });
      }
    };

    readCondition();
    const timer = window.setInterval(readCondition, 1500);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const latestConditions = useMemo(() => {
    const observations = runtime.payload?.condition?.condition_signals?.observations?.filter(
      (observation) => observation.quality === "good" && Number.isFinite(observation.value),
    ) ?? [];
    const latest = new Map<string, RuntimeObservation>();
    for (const observation of observations) {
      latest.set(observation.relationship_id ?? observation.signal, observation);
    }
    return [...latest.values()];
  }, [runtime.payload]);

  const attentionConditions = latestConditions.filter(outsideEnvelope);
  const status = runtime.state === "unavailable"
    ? "EVIDENCE UNAVAILABLE"
    : attentionConditions.length > 0
      ? "ATTENTION"
      : latestConditions.length > 0
        ? "STABLE"
        : "NO ACTIVE CONDITION";
  const sourceMode = runtime.payload?.source_mode ?? "unknown";

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>LINEALERT · OPERATOR VIEW</span>
          <h1>Current admitted machine conditions</h1>
          <p>
            This view follows condition evidence produced by LineAlert. Active condition types are
            highlighted; inactive types stay visible but subdued and do not imply proven absence.
          </p>
        </div>
        <nav className={styles.nav} aria-label="Operator view navigation">
          <Link href="/health">Machine Health</Link>
          <Link className={styles.secondary} href="/commissioning">Commissioning Lab</Link>
        </nav>
      </header>

      <section className={styles.statusStrip} aria-label="Current condition status">
        <div>
          <span>STATION STATUS</span>
          <b>{status}</b>
        </div>
        <div>
          <span>SOURCE MODE</span>
          <b>{sourceMode}</b>
        </div>
        <div>
          <span>ADMITTED MEASUREMENTS</span>
          <b>{runtime.payload?.measurement_count ?? 0}</b>
        </div>
        <div>
          <span>REFUSALS</span>
          <b>{runtime.payload?.refusal_count ?? 0}</b>
        </div>
      </section>

      <section className={styles.workspace}>
        <div className={styles.sectionHeading}>
          <div>
            <span>ACTIVE EVIDENCE</span>
            <h2>Relationships requiring operator attention</h2>
          </div>
          <small>Latest admitted measurement per relationship</small>
        </div>

        {runtime.state === "loading" && (
          <div className={styles.emptyState}>Reading the current condition stream…</div>
        )}

        {runtime.state === "unavailable" && (
          <div className={styles.emptyState}>
            Condition evidence is unavailable. Do not substitute a commissioning scenario for live
            or retained machine evidence.
          </div>
        )}

        {runtime.state === "active" && latestConditions.length === 0 && (
          <div className={styles.emptyState}>
            No admitted condition measurement is active. Machine Health remains available for
            retained history; the commissioning lab is a separate synthetic test environment.
          </div>
        )}

        {latestConditions.length > 0 && (
          <div className={styles.conditionGrid}>
            {latestConditions.map((observation) => {
              const outside = outsideEnvelope(observation);
              return (
                <article
                  className={`${styles.conditionCard} ${outside ? styles.attention : ""}`}
                  key={observation.relationship_id ?? observation.signal}
                >
                  <div className={styles.cardHeader}>
                    <span>{outside ? "OUTSIDE ENVELOPE" : "IN ENVELOPE"}</span>
                    <b>{observation.value.toFixed(0)} {observation.unit}</b>
                  </div>
                  <h3>{relationshipLabel(observation)}</h3>
                  <dl>
                    <div><dt>Commissioned</dt><dd>{observation.min_value}–{observation.max_value} {observation.unit}</dd></div>
                    <div><dt>Signal</dt><dd>{observation.signal}</dd></div>
                    <div><dt>Asset</dt><dd>{observation.asset_id}</dd></div>
                    <div><dt>Correlation</dt><dd>{observation.correlation_id ?? "—"}</dd></div>
                  </dl>
                  <p>
                    {outside
                      ? "The measured relationship requires investigation. This does not establish physical root cause."
                      : "The latest admitted measurement is inside its commissioned envelope."}
                  </p>

                  {outside && (
                    <OperatorActions observation={observation} sourceMode={sourceMode} />
                  )}

                  <Link className={styles.historyLink} href="/health">
                    Review retained condition history →
                  </Link>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section className={styles.boundary}>
        <div>
          <span>EVIDENCE BOUNDARY</span>
          <b>Operator conclusions follow admitted evidence—not canned scenario state.</b>
        </div>
        <p>
          {runtime.payload?.claim_boundary
            ?? "Condition evidence does not by itself establish physical root cause, remaining useful life, future failure, or equipment-action authority."}
        </p>
      </section>

      <section className={styles.commissioningCard}>
        <div>
          <span>CONDITION REFERENCE</span>
          <h2>Known machine condition types</h2>
          <p>
            Arrival phase, pressure, slip, tension, and sensor sequence remain available as a shared
            troubleshooting vocabulary. Only admitted evidence can mark a condition active.
          </p>
        </div>
        <Link href="/commissioning">Review condition detail →</Link>
      </section>
    </main>
  );
}
