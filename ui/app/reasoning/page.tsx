"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import styles from "../triage-board.module.css";

type HistorianStatus = {
  connected?: boolean;
  source_available?: boolean;
  reason_code?: string;
  updated_at?: string;
};

type EvidenceRecord = {
  observed_at?: string;
  record_id?: string;
  episode_id?: string;
  asset_id?: string;
  cycle_id?: string;
  record_kind?: string;
  epistemic_state?: string;
  evidence_validity?: string;
  temporal_coverage?: string;
  source_id?: string;
  evidence_ids?: string[];
  reasons?: string[];
  operating_context?: {
    component_id?: string;
    profile_id?: string;
    operating_mode?: string;
    configuration_version?: string;
  };
};

type HistoryPayload = {
  persistence?: string;
  count?: number;
  truncated?: boolean;
  records?: EvidenceRecord[];
  reason_code?: string;
};

function observedLabel(value?: string) {
  if (!value) return "No timestamp";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export default function ReasoningInputs() {
  const [status, setStatus] = useState<HistorianStatus | null>(null);
  const [history, setHistory] = useState<HistoryPayload | null>(null);
  const [reachable, setReachable] = useState(false);

  useEffect(() => {
    let active = true;

    const read = async () => {
      try {
        const [statusResponse, historyResponse] = await Promise.all([
          fetch("/api/historian/status", { cache: "no-store" }),
          fetch("/api/historian/functional-temporal?limit=8", { cache: "no-store" }),
        ]);
        const [statusPayload, historyPayload] = await Promise.all([
          statusResponse.json() as Promise<HistorianStatus>,
          historyResponse.json() as Promise<HistoryPayload>,
        ]);
        if (!active) return;
        setStatus(statusPayload);
        setHistory(historyPayload);
        setReachable(statusResponse.ok && historyResponse.ok);
      } catch {
        if (!active) return;
        setReachable(false);
      }
    };

    void read();
    const timer = window.setInterval(() => void read(), 2500);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const records = useMemo(() => history?.records ?? [], [history]);
  const historianState = status?.connected ? "CONNECTED" : "OFFLINE · FAIL CLOSED";
  const sourceState = status?.source_available ? "SOURCE AVAILABLE" : "SOURCE UNAVAILABLE";
  const recordState = reachable ? `${history?.count ?? 0} RETAINED RECORDS` : "NO LIVE HISTORY";

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>LINEALERT · REASONING INPUTS · READ ONLY</span>
          <h1>Evidence before explanation</h1>
          <p>
            This surface exposes admitted historian evidence and retrieval readiness for governed reasoning.
            It does not diagnose a fault, prove physical state, or authorize an equipment action.
          </p>
          <p>
            <small>
              Telemetry ≠ diagnosis. Historical pattern ≠ current root cause. Recommendation ≠ authorized action.
            </small>
          </p>
        </div>
        <nav className={styles.nav}>
          <Link href="/">Plant canvas</Link>
          <Link href="/health">Evidence</Link>
          <Link className={styles.activeView} href="/reasoning">Reasoning inputs</Link>
        </nav>
      </header>

      <section className={styles.posture}>
        <div><span>HISTORIAN</span><b>{historianState}</b></div>
        <div><span>UPSTREAM SOURCE</span><b>{sourceState}</b></div>
        <div><span>FUNCTIONAL / TEMPORAL</span><b>{recordState}</b></div>
        <div><span>REASON CODE</span><b>{status?.reason_code ?? history?.reason_code ?? "WAITING"}</b></div>
      </section>

      <section className={styles.trialCard} aria-label="Reasoning capability boundary">
        <div className={styles.trialHeading}>
          <div>
            <span>CONTEXT ASSEMBLY BOUNDARY</span>
            <h2>Retrieval is evidence plumbing, not causal authority</h2>
            <small>Current UI reads only the existing historian service.</small>
          </div>
          <b>NO INFERENCE ENDPOINT EXPOSED</b>
        </div>
        <div className={styles.trialGrid}>
          <div><span>01 · OBSERVE</span><strong>Qualified evidence</strong><small>Source identity, timestamps, clock quality, asset and context stay attached.</small></div>
          <div><span>02 · RETAIN</span><strong>Timescale historian</strong><small>History is bounded and queryable only when the local historian is available.</small></div>
          <div><span>03 · ASSEMBLE</span><strong>Reasoning context</strong><small>Backend context-bundle and historian retrieval logic can consume governed evidence without changing it.</small></div>
          <div><span>04 · REVIEW</span><strong>Human authority</strong><small>Any explanation or recommendation remains subject to evidence limits and plant authority.</small></div>
        </div>
      </section>
      <section className={styles.trialCard} aria-label="Recent functional temporal evidence">
        <div className={styles.trialHeading}>
          <div>
            <span>RECENT ADMITTED HISTORY</span>
            <h2>Functional / temporal evidence</h2>
            <small>{history?.persistence ?? "Historian not available"} · newest bounded query window</small>
          </div>
          <b>{history?.truncated ? "OLDER MATCHES OMITTED" : "BOUNDED VIEW"}</b>
        </div>

        <div className={styles.trialEvidence}>
          {records.length === 0 ? (
            <div>
              <span>NO RETAINED RECORDS AVAILABLE</span>
              <p>
                {status?.connected
                  ? "The historian is reachable but this query returned no functional / temporal evidence."
                  : "The historian is unavailable, so LineAlert is refusing to present cached history as current evidence."}
              </p>
            </div>
          ) : records.map((record) => (
            <div key={record.record_id ?? `${record.episode_id}-${record.observed_at}`}>
              <span>{record.record_kind ?? "EVIDENCE RECORD"} · {record.evidence_validity ?? "UNKNOWN VALIDITY"}</span>
              <p><b>{record.asset_id ?? "Unknown asset"}</b> · {record.operating_context?.component_id ?? "Unknown component"} · {observedLabel(record.observed_at)}</p>
              <p>Episode {record.episode_id ?? "—"} · Cycle {record.cycle_id ?? "—"} · State {record.epistemic_state ?? "—"} · Coverage {record.temporal_coverage ?? "—"}</p>
              <small>Source {record.source_id ?? "—"} · Evidence IDs {record.evidence_ids?.length ?? 0} · Reasons {record.reasons?.join(" · ") || "none recorded"}</small>
            </div>
          ))}
        </div>
      </section>
      <section className={styles.provenance}>
        <span>LIVE READINESS</span>
        <small>Historian connected · {String(Boolean(status?.connected))}</small>
        <small>Historian source available · {String(Boolean(status?.source_available))}</small>
        <small>Last historian status update · {observedLabel(status?.updated_at)}</small>
        <small>HTTP retrieval healthy · {String(reachable)}</small>
      </section>

      <section className={styles.boundary}>
        <div>
          <span>REASONING SURFACE BOUNDARY</span>
          <b>Admitted evidence → bounded retrieval → governed context → human review.</b>
        </div>
        <p>
          This page is read-only. It does not write historian evidence, issue commands, change equipment state,
          infer a root cause, or grant production authority. A successful retrieval only establishes that evidence
          was retrievable under the displayed context; it does not establish that an explanation is true.
        </p>
      </section>
    </main>
  );
}
