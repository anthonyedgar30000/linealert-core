"use client";

import { useMemo, useState } from "react";

import styles from "./operator-view.module.css";

export type OperatorActionObservation = {
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
  source_mode?: string;
  condition?: {
    condition_signals?: {
      observations?: OperatorActionObservation[];
    };
  } | null;
};

type ActionState = {
  state: "idle" | "saving" | "saved" | "unavailable" | "error";
  message?: string;
};

type VerificationState = {
  state: "idle" | "checking" | "recovered" | "persists" | "unavailable";
  latest?: number;
  unit?: string;
  history?: "persisted" | "unavailable";
};

const observationOptions = [
  { code: "no_visible_obstruction", label: "No visible obstruction or drag" },
  { code: "web_drag_or_snag", label: "Label web / stock drag or snag observed" },
  { code: "peel_or_sensor_obstruction", label: "Peel-point or sensor obstruction observed" },
  { code: "setup_mismatch", label: "Recipe, job, or label-stock mismatch observed" },
] as const;

const outsideEnvelope = (observation: OperatorActionObservation) => (
  observation.value < observation.min_value || observation.value > observation.max_value
);

const episodeIdFor = (observation: OperatorActionObservation, sourceMode: string) => (
  sourceMode === "deterministic_event_replay"
    ? "condition-runtime-replay"
    : `runtime:${observation.correlation_id ?? observation.observation_id ?? observation.signal}`
);

const relationshipIdFor = (observation: OperatorActionObservation) => (
  observation.relationship_id ?? `relationship:${observation.signal}`
);

const sameRelationship = (
  candidate: OperatorActionObservation,
  original: OperatorActionObservation,
) => {
  if (candidate.signal !== original.signal) return false;
  if (original.relationship_id && candidate.relationship_id) {
    return candidate.relationship_id === original.relationship_id;
  }
  return candidate.topology_from === original.topology_from
    && candidate.topology_to === original.topology_to;
};

export default function OperatorActions({
  observation,
  sourceMode,
}: {
  observation: OperatorActionObservation;
  sourceMode: string;
}) {
  const [inspectionOpen, setInspectionOpen] = useState(false);
  const [selectedObservation, setSelectedObservation] = useState<string>("");
  const [note, setNote] = useState("");
  const [actionState, setActionState] = useState<ActionState>({ state: "idle" });
  const [verification, setVerification] = useState<VerificationState>({ state: "idle" });

  const selectedLabel = useMemo(() => (
    observationOptions.find((option) => option.code === selectedObservation)?.label ?? ""
  ), [selectedObservation]);

  const persistOutcome = async (payload: Record<string, unknown>) => {
    try {
      const response = await fetch("/api/historian/outcomes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return response.ok;
    } catch {
      return false;
    }
  };

  const recordObservation = async () => {
    if (!selectedObservation && !note.trim()) {
      setActionState({
        state: "error",
        message: "Choose an observation or add a note before recording it.",
      });
      return;
    }

    setActionState({ state: "saving", message: "Recording operator observation…" });
    const persisted = await persistOutcome({
      episode_id: episodeIdFor(observation, sourceMode),
      asset_id: observation.asset_id,
      relationship_id: relationshipIdFor(observation),
      outcome_type: "operator_observation",
      status: selectedObservation || "note_recorded",
      actor_role: "operator_view",
      note: note.trim() || selectedLabel || undefined,
      related_observation_id: observation.observation_id,
      details: {
        source_mode: sourceMode,
        signal: observation.signal,
        correlation_id: observation.correlation_id,
        observation_code: selectedObservation || undefined,
      },
    });

    setActionState(persisted
      ? { state: "saved", message: "Observation appended to the shared historian episode." }
      : {
          state: "unavailable",
          message: "Historian unavailable; the observation was not durably recorded.",
        });
  };

  const escalate = async () => {
    setActionState({ state: "saving", message: "Recording maintenance escalation…" });
    const persisted = await persistOutcome({
      episode_id: episodeIdFor(observation, sourceMode),
      asset_id: observation.asset_id,
      relationship_id: relationshipIdFor(observation),
      outcome_type: "operator_escalation",
      status: "escalated",
      actor_role: "operator_view",
      note: note.trim() || selectedLabel || "Condition exceeded operator recovery boundary.",
      related_observation_id: observation.observation_id,
      details: {
        source_mode: sourceMode,
        signal: observation.signal,
        correlation_id: observation.correlation_id,
        dispatch_delivery_claimed: false,
      },
    });

    setActionState(persisted
      ? {
          state: "saved",
          message: "Escalation recorded. No dispatch connector delivery is claimed yet.",
        }
      : {
          state: "unavailable",
          message: "Historian unavailable; no durable escalation record was created.",
        });
  };

  const verifyOriginalCondition = async () => {
    setVerification({ state: "checking" });
    try {
      const response = await fetch("/api/condition", { cache: "no-store" });
      if (!response.ok) throw new Error("condition runtime unavailable");
      const payload = (await response.json()) as ConditionPayload;
      const candidates = payload.condition?.condition_signals?.observations?.filter(
        (candidate) => candidate.quality === "good" && sameRelationship(candidate, observation),
      ) ?? [];
      const latest = candidates.at(-1);
      if (!latest) {
        setVerification({ state: "unavailable" });
        return;
      }

      const persists = outsideEnvelope(latest);
      const persisted = await persistOutcome({
        episode_id: episodeIdFor(observation, payload.source_mode ?? sourceMode),
        asset_id: latest.asset_id,
        relationship_id: relationshipIdFor(latest),
        outcome_type: "condition_verification",
        status: persists ? "persists" : "recovered",
        actor_role: "operator_view",
        related_observation_id: latest.observation_id,
        verification_value: latest.value,
        verification_unit: latest.unit,
        verification_status: persists
          ? "outside_commissioned_envelope"
          : "inside_commissioned_envelope",
        details: {
          source_mode: payload.source_mode ?? sourceMode,
          handoff_observation_id: observation.observation_id,
          handoff_correlation_id: observation.correlation_id,
          verification_correlation_id: latest.correlation_id,
        },
      });

      setVerification({
        state: persists ? "persists" : "recovered",
        latest: latest.value,
        unit: latest.unit,
        history: persisted ? "persisted" : "unavailable",
      });
    } catch {
      setVerification({ state: "unavailable" });
    }
  };

  return (
    <section className={styles.actionPanel} aria-label="Bounded operator actions">
      <div className={styles.actionHeading}>
        <div>
          <span>OPERATOR ACTIONS</span>
          <h4>Inspect → record → escalate or recover → verify</h4>
        </div>
        <small>Evidence guides the next safe check; it does not grant extra machine authority.</small>
      </div>

      <div className={styles.actionButtons}>
        <button type="button" onClick={() => setInspectionOpen((open) => !open)}>
          {inspectionOpen ? "Hide inspection checks" : "Inspect label path"}
        </button>
        <button type="button" onClick={recordObservation} disabled={actionState.state === "saving"}>
          Record observation
        </button>
        <button className={styles.escalateButton} type="button" onClick={escalate} disabled={actionState.state === "saving"}>
          Escalate to maintenance
        </button>
        <button className={styles.verifyButton} type="button" onClick={verifyOriginalCondition} disabled={verification.state === "checking"}>
          {verification.state === "checking" ? "Verifying…" : "Verify original condition"}
        </button>
      </div>

      {inspectionOpen && (
        <div className={styles.inspectionBox}>
          <div>
            <b>Allowed first checks</b>
            <ul>
              <li>Look for visible label-web drag, snagging, misrouting, wrinkling, or obstruction.</li>
              <li>Inspect the peel point and visible label-present sensor area for obvious blockage or contamination.</li>
              <li>Confirm the intended recipe/job and label stock are loaded.</li>
              <li>If site/OEM procedure explicitly authorizes clearing a simple obstruction, do so and then verify this same relationship.</li>
            </ul>
          </div>
          <p>
            Do not change servo tuning, PLC logic, timing values, hidden parameters, or bypasses from
            this condition evidence alone. If the required action exceeds operator scope, escalate.
          </p>
        </div>
      )}

      <div className={styles.observationRecorder}>
        <div className={styles.observationChoices}>
          {observationOptions.map((option) => (
            <label key={option.code}>
              <input
                type="radio"
                name={`operator-observation-${relationshipIdFor(observation)}`}
                value={option.code}
                checked={selectedObservation === option.code}
                onChange={(event) => setSelectedObservation(event.target.value)}
              />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
        <label className={styles.noteField}>
          <span>Optional operator note</span>
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="What did you actually observe?"
            rows={2}
          />
        </label>
      </div>

      {actionState.message && (
        <p className={`${styles.actionMessage} ${styles[`action_${actionState.state}`]}`}>
          {actionState.message}
        </p>
      )}

      {verification.state !== "idle" && verification.state !== "checking" && (
        <div className={`${styles.verificationResult} ${styles[`verification_${verification.state}`]}`}>
          {verification.state === "unavailable" ? (
            <b>Original relationship could not be re-read.</b>
          ) : (
            <>
              <b>{verification.state === "recovered" ? "RECOVERED" : "DEGRADATION PERSISTS"}</b>
              <span>{verification.latest?.toFixed(0)} {verification.unit}</span>
              <small>
                {verification.history === "persisted"
                  ? "Verification appended to the shared historian episode."
                  : "Historian unavailable; this verification is live-only."}
              </small>
            </>
          )}
        </div>
      )}
    </section>
  );
}
