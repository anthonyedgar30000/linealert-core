"use client";

import { useState } from "react";

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

type ActionState = {
  state: "idle" | "saving" | "saved" | "unavailable" | "error";
  message?: string;
};

type CheckDisposition = "continue" | "handoff";

type CheckAnswer = {
  code: string;
  label: string;
  disposition: CheckDisposition;
  handoffReason?: string;
};

type OperatorCheck = {
  id: string;
  question: string;
  reason: string;
  answers: CheckAnswer[];
};

const operatorChecks: OperatorCheck[] = [
  {
    id: "visible_label_path",
    question: "Does the visible label web appear clear of an obvious snag or obstruction?",
    reason: "A visible drag or obstruction can help explain why this admitted label-feed relationship needs investigation.",
    answers: [
      { code: "label_path_clear", label: "Yes — it appears clear", disposition: "continue" },
      {
        code: "label_path_obstruction_observed",
        label: "No — I can see a snag or obstruction",
        disposition: "handoff",
        handoffReason: "A visible label-path issue was observed. No additional operator action is requested from this evidence alone.",
      },
      {
        code: "label_path_not_safely_verified",
        label: "Not sure — I cannot verify this safely",
        disposition: "handoff",
        handoffReason: "The check could not be completed safely from the approved operating position.",
      },
    ],
  },
  {
    id: "peel_point_clear",
    question: "Does the visible peel-point area appear clear?",
    reason: "An obvious obstruction or contamination at the visible peel-point or label-present area can interrupt label presentation.",
    answers: [
      { code: "peel_point_clear", label: "Yes — it appears clear", disposition: "continue" },
      {
        code: "peel_point_obstruction_observed",
        label: "No — I can see an obstruction or contamination",
        disposition: "handoff",
        handoffReason: "A visible peel-point issue was observed. Clearing or adjustment requires the applicable site/OEM procedure and authority.",
      },
      {
        code: "peel_point_not_safely_verified",
        label: "Not sure — I cannot verify this safely",
        disposition: "handoff",
        handoffReason: "The peel-point check could not be completed safely from the approved operating position.",
      },
    ],
  },
  {
    id: "job_stock_confirmed",
    question: "Can you confirm the intended recipe/job and label stock are loaded?",
    reason: "A setup mismatch can make the current physical response inconsistent with the job LineAlert is evaluating.",
    answers: [
      { code: "job_stock_confirmed", label: "Yes — confirmed", disposition: "continue" },
      {
        code: "job_stock_mismatch_observed",
        label: "No — I found a mismatch",
        disposition: "handoff",
        handoffReason: "A setup mismatch was observed. The next move depends on site authority and the approved job/change procedure.",
      },
      {
        code: "job_stock_not_verified",
        label: "Not sure — I cannot verify it",
        disposition: "handoff",
        handoffReason: "The intended job or label stock could not be verified.",
      },
    ],
  },
];

const episodeIdFor = (observation: OperatorActionObservation, sourceMode: string) => (
  sourceMode === "deterministic_event_replay"
    ? "condition-runtime-replay"
    : `runtime:${observation.correlation_id ?? observation.observation_id ?? observation.signal}`
);

const relationshipIdFor = (observation: OperatorActionObservation) => (
  observation.relationship_id ?? `relationship:${observation.signal}`
);

export default function OperatorActions({
  observation,
  sourceMode,
}: {
  observation: OperatorActionObservation;
  sourceMode: string;
}) {
  const [checkIndex, setCheckIndex] = useState(0);
  const [lastAnswer, setLastAnswer] = useState<CheckAnswer | null>(null);
  const [handoffReason, setHandoffReason] = useState<string | null>(null);
  const [actionState, setActionState] = useState<ActionState>({ state: "idle" });

  const currentCheck = operatorChecks[checkIndex];

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

  const answerCheck = async (answer: CheckAnswer) => {
    setActionState({ state: "saving", message: "Recording observation…" });

    const persisted = await persistOutcome({
      episode_id: episodeIdFor(observation, sourceMode),
      asset_id: observation.asset_id,
      relationship_id: relationshipIdFor(observation),
      outcome_type: "operator_observation",
      status: answer.code,
      actor_role: "operator_view",
      note: answer.label,
      related_observation_id: observation.observation_id,
      details: {
        source_mode: sourceMode,
        signal: observation.signal,
        correlation_id: observation.correlation_id,
        check_id: currentCheck.id,
        interaction_contract: "one_question_one_reason_one_safe_response",
      },
    });

    setLastAnswer(answer);
    setActionState(persisted
      ? { state: "saved", message: "Observation recorded." }
      : {
          state: "unavailable",
          message: "Historian unavailable; this response is not durably recorded.",
        });

    if (answer.disposition === "handoff") {
      setHandoffReason(answer.handoffReason ?? "The bounded operator check requires a qualified handoff.");
      return;
    }

    if (checkIndex === operatorChecks.length - 1) {
      setHandoffReason(
        "All bounded operator checks were clear. The admitted condition still requires investigation; do not invent another operator action.",
      );
    }
  };

  const continueToNextCheck = () => {
    if (!lastAnswer || lastAnswer.disposition !== "continue") return;
    if (checkIndex >= operatorChecks.length - 1) return;

    setCheckIndex((index) => index + 1);
    setLastAnswer(null);
    setActionState({ state: "idle" });
  };

  const recordHandoff = async () => {
    setActionState({ state: "saving", message: "Recording maintenance handoff…" });
    const persisted = await persistOutcome({
      episode_id: episodeIdFor(observation, sourceMode),
      asset_id: observation.asset_id,
      relationship_id: relationshipIdFor(observation),
      outcome_type: "operator_escalation",
      status: "escalated",
      actor_role: "operator_view",
      note: handoffReason ?? "Bounded operator inspection completed; qualified follow-up required.",
      related_observation_id: observation.observation_id,
      details: {
        source_mode: sourceMode,
        signal: observation.signal,
        correlation_id: observation.correlation_id,
        dispatch_delivery_claimed: false,
        interaction_contract: "one_question_one_reason_one_safe_response",
      },
    });

    setActionState(persisted
      ? {
          state: "saved",
          message: "Maintenance handoff recorded. No dispatch delivery is claimed.",
        }
      : {
          state: "unavailable",
          message: "Historian unavailable; no durable handoff record was created.",
        });
  };

  return (
    <section className={styles.actionPanel} aria-label="Single-step operator check">
      <div className={styles.actionHeading}>
        <div>
          <span>OPERATOR CHECK · {checkIndex + 1} OF {operatorChecks.length}</span>
          <h4>One question. One reason. One safe response.</h4>
        </div>
        <small>Answer only from the approved operating position. Do not open guards or infer a hidden machine state.</small>
      </div>

      <div className={styles.inspectionBox}>
        <div>
          <b>{currentCheck.question}</b>
          <p>{currentCheck.reason}</p>
        </div>
      </div>

      {!lastAnswer && !handoffReason && (
        <div className={styles.actionButtons}>
          {currentCheck.answers.map((answer) => (
            <button
              key={answer.code}
              type="button"
              onClick={() => answerCheck(answer)}
              disabled={actionState.state === "saving"}
            >
              {answer.label}
            </button>
          ))}
        </div>
      )}

      {lastAnswer && (
        <div className={styles.inspectionBox}>
          <div>
            <b>Recorded: {lastAnswer.label}</b>
            <p>
              {lastAnswer.disposition === "continue"
                ? "This observation does not prove the mechanism is healthy. It only supports moving to the next bounded check."
                : "No additional operator action is requested from this evidence alone."}
            </p>
          </div>
        </div>
      )}

      {lastAnswer?.disposition === "continue" && !handoffReason && checkIndex < operatorChecks.length - 1 && (
        <div className={styles.actionButtons}>
          <button type="button" onClick={continueToNextCheck}>
            Continue to next check
          </button>
        </div>
      )}

      {handoffReason && (
        <>
          <div className={styles.inspectionBox}>
            <div>
              <b>Next: qualified handoff</b>
              <p>{handoffReason}</p>
            </div>
          </div>
          <div className={styles.actionButtons}>
            <button
              className={styles.escalateButton}
              type="button"
              onClick={recordHandoff}
              disabled={actionState.state === "saving"}
            >
              Record maintenance handoff
            </button>
          </div>
        </>
      )}

      {actionState.message && (
        <p className={`${styles.actionMessage} ${styles[`action_${actionState.state}`]}`}>
          {actionState.message}
        </p>
      )}
    </section>
  );
}
