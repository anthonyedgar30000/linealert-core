"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import styles from "./service-workspace.module.css";

type VerificationState =
  | "plant_relay_only"
  | "technician_viewed_source"
  | "technician_retained_copy";

type ReportedTimeKind = "exact" | "approximate" | "window" | "unknown";

type PersistedPlantContext = {
  schema_version: "linealert.plant-reported-context.v1";
  context_id: string;
  service_case_id: string;
  asset_id: string;
  entered_at: string;
  entered_by: string;
  reported_source_class: string;
  reported_source: string;
  original_wording_or_bounded_summary: string;
  source_verification_state: VerificationState;
  reported_time_kind: ReportedTimeKind;
  reported_clock_quality: string;
  reported_event_start: string | null;
  reported_event_end: string | null;
  source_record_reference: string | null;
  plant_contact_role: string | null;
  provenance: string[];
  direct_system_observation: false;
  verified_source_record: false;
  causal_claim_established: false;
};

type FirstDeparture = {
  departure_id: string;
  asset_id: string;
  relationship_id: string;
  observed_at: string;
  expected_reference_id: string;
  configuration_version: string;
  clock_quality: string;
  reason_code: string;
  evidence_ids: string[];
  source_ids: string[];
};

type PersistedServiceCase = {
  schema_version: "linealert.service-case.v1";
  service_case_id: string;
  customer_id: string;
  site_id: string;
  asset_id: string;
  opened_at: string;
  opened_by: string;
  service_call_received_at: string;
  reported_symptom: string;
  reported_incident_at: string | null;
  service_call_reference: string | null;
  preincident_window_start: string;
  preincident_window_end: string;
  current_configuration_version: string | null;
  status: string;
  evidence_ids: string[];
  plant_reported_context_ids: string[];
  working_explanation_ids: string[];
  missing_evidence_request_ids: string[];
  first_detected_departure: FirstDeparture | null;
  authorized_action: false;
};

type StoredBundle = {
  schema_version: "linealert.service-case-store.v1";
  persistence: string;
  updated_at: string;
  service_case: PersistedServiceCase;
  plant_reported_contexts: PersistedPlantContext[];
  authority: {
    production_record: false;
    direct_cmms_record: false;
    equipment_authority: false;
    return_to_service_authority: false;
  };
};

const fallbackCase = {
  id: "svc-2026-0042",
  customerId: "customer-synthetic-01",
  siteId: "site-synthetic-01",
  asset: "Labeler 2",
  assetId: "LABELER-02",
  callReference: "CALL-0042",
  callReceived: "12:45",
  incident: "12:00",
  symptom: "Labels intermittently skewing and bottle flow backing up.",
  window: "09:00–12:00",
  configuration: "cfg-2026-09-01",
} as const;

const fallbackDeparture = {
  time: "10:00",
  relationship: "relationship:photoeye-to-label-feed",
  expectedReference: "baseline:labeler-02:v7",
  reason: "CONDITION.OUTSIDE_EXPECTED_ENVELOPE",
  clockQuality: "synchronized_cross_source_interval",
  evidence: ["ev-100", "ev-101"],
} as const;

const changedRelationships = [
  "Bottle presentation interval variability increased before the reported incident.",
  "Label application alignment became intermittently inconsistent.",
];

const heldRelationships = [
  "Line speed remained at the same synthetic operating point.",
  "Upstream filler cadence remained inside the retained synthetic envelope.",
  "No retained timing-change evidence precedes the first departure.",
];

const missingContext = [
  "CMMS work orders or maintenance notes around 09:40–10:20.",
  "Operator/shift notes for jams, guide adjustments, cleaning, or roll/material changes.",
  "Any intervention that could affect bottle presentation or guide spacing.",
];

const workingExplanations = [
  {
    title: "Presentation / guide relationship changed",
    standing: "Most supported",
    why: "Consistent with the first retained departure and current alignment symptoms.",
  },
  {
    title: "Material or roll-change interaction",
    standing: "Plausible",
    why: "The reported symptom followed a roll change, but current evidence does not isolate mechanism.",
  },
  {
    title: "Label timing / peel geometry",
    standing: "Lower priority",
    why: "Still possible; retained evidence currently points earlier toward presentation instability.",
  },
];

function timeLabel(value: string | null | undefined) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function dateTimeLabel(value: string | null | undefined) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function localInputToIso(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    throw new Error("Reported event time is invalid.");
  }
  return parsed.toISOString();
}

function reportedTimeLabel(context: PersistedPlantContext) {
  if (context.reported_time_kind === "unknown") return "unknown";
  if (context.reported_time_kind === "window") {
    return (
      dateTimeLabel(context.reported_event_start) +
      " – " +
      dateTimeLabel(context.reported_event_end)
    );
  }
  const prefix = context.reported_time_kind === "approximate" ? "approx. " : "";
  return prefix + dateTimeLabel(context.reported_event_start);
}

export default function SpeedwayServiceWorkspace() {
  const [historianConnected, setHistorianConnected] = useState<boolean | null>(null);
  const [bundle, setBundle] = useState<StoredBundle | null>(null);
  const [storeReady, setStoreReady] = useState<boolean | null>(null);
  const [storeError, setStoreError] = useState<string | null>(null);
  const [contextOpen, setContextOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sourceClass, setSourceClass] = useState("cmms");
  const [source, setSource] = useState("Plant CMMS");
  const [timeKind, setTimeKind] = useState<ReportedTimeKind>("window");
  const [eventStart, setEventStart] = useState("2026-09-27T09:40");
  const [eventEnd, setEventEnd] = useState("2026-09-27T10:20");
  const [clockQuality, setClockQuality] = useState("unknown");
  const [verification, setVerification] =
    useState<VerificationState>("plant_relay_only");
  const [enteredBy, setEnteredBy] = useState("speedway-technician-local");
  const [sourceRecordReference, setSourceRecordReference] = useState("");
  const [plantContactRole, setPlantContactRole] = useState("");
  const [summary, setSummary] = useState("");

  useEffect(() => {
    let active = true;
    const read = async () => {
      try {
        const [statusResponse, caseResponse] = await Promise.all([
          fetch("/api/service-cases/status", { cache: "no-store" }),
          fetch("/api/service-cases/" + encodeURIComponent(fallbackCase.id), {
            cache: "no-store",
          }),
        ]);
        const casePayload = await caseResponse.json();
        if (!active) return;
        if (statusResponse.ok && caseResponse.ok) {
          setBundle(casePayload as StoredBundle);
          setStoreReady(true);
          setStoreError(null);
        } else {
          setStoreReady(false);
          setStoreError("Local service-case persistence is unavailable; entry is disabled.");
        }
      } catch {
        if (!active) return;
        setStoreReady(false);
        setStoreError("Local service-case persistence is unavailable; entry is disabled.");
      }
    };
    void read();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    const read = async () => {
      try {
        const response = await fetch("/api/historian/status", { cache: "no-store" });
        if (!active) return;
        setHistorianConnected(response.ok);
      } catch {
        if (active) setHistorianConnected(false);
      }
    };
    void read();
    const timer = window.setInterval(() => void read(), 4000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);
  const persistedCase = bundle?.service_case;
  const firstDeparture = persistedCase?.first_detected_departure;
  const serviceCase = {
    id: persistedCase?.service_case_id ?? fallbackCase.id,
    customerId: persistedCase?.customer_id ?? fallbackCase.customerId,
    siteId: persistedCase?.site_id ?? fallbackCase.siteId,
    asset:
      (persistedCase?.asset_id ?? fallbackCase.assetId) === "LABELER-02"
        ? "Labeler 2"
        : persistedCase?.asset_id ?? fallbackCase.asset,
    assetId: persistedCase?.asset_id ?? fallbackCase.assetId,
    callReference: persistedCase?.service_call_reference ?? fallbackCase.callReference,
    callReceived: persistedCase
      ? timeLabel(persistedCase.service_call_received_at)
      : fallbackCase.callReceived,
    incident: persistedCase
      ? timeLabel(persistedCase.reported_incident_at)
      : fallbackCase.incident,
    symptom: persistedCase?.reported_symptom ?? fallbackCase.symptom,
    window: persistedCase
      ? timeLabel(persistedCase.preincident_window_start) +
        "–" +
        timeLabel(persistedCase.preincident_window_end)
      : fallbackCase.window,
    configuration:
      persistedCase?.current_configuration_version ?? fallbackCase.configuration,
  };

  const departure = {
    time: firstDeparture ? timeLabel(firstDeparture.observed_at) : fallbackDeparture.time,
    relationship: firstDeparture?.relationship_id ?? fallbackDeparture.relationship,
    expectedReference:
      firstDeparture?.expected_reference_id ?? fallbackDeparture.expectedReference,
    reason: firstDeparture?.reason_code ?? fallbackDeparture.reason,
    clockQuality: firstDeparture?.clock_quality ?? fallbackDeparture.clockQuality,
    evidence: firstDeparture?.evidence_ids ?? fallbackDeparture.evidence,
  };

  const contexts = bundle?.plant_reported_contexts ?? [];

  const historianLabel =
    historianConnected === null
      ? "CHECKING"
      : historianConnected
        ? "AVAILABLE"
        : "OFFLINE · FAIL CLOSED";

  const storeLabel =
    storeReady === null
      ? "CHECKING"
      : storeReady
        ? "PERSISTENT · LOCAL"
        : "OFFLINE · ENTRY DISABLED";

  const investigationCount = useMemo(
    () => changedRelationships.length + heldRelationships.length + contexts.length,
    [contexts.length],
  );

  const addContext = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStoreError(null);
    if (!storeReady) {
      setStoreError("Local persistence is unavailable; nothing was saved.");
      return;
    }
    if (!summary.trim() || !source.trim() || !clockQuality.trim() || !enteredBy.trim()) {
      setStoreError("Source, summary, clock quality, and entered-by identity are required.");
      return;
    }
    if (timeKind !== "unknown" && !eventStart) {
      setStoreError("A reported event time is required for this time kind.");
      return;
    }
    if (timeKind === "window" && !eventEnd) {
      setStoreError("A reported event end time is required for a window.");
      return;
    }

    let reportedEventStart: string | null = null;
    let reportedEventEnd: string | null = null;
    try {
      if (timeKind !== "unknown") {
        reportedEventStart = localInputToIso(eventStart);
      }
      if (timeKind === "window") {
        reportedEventEnd = localInputToIso(eventEnd);
      }
    } catch (error) {
      setStoreError(error instanceof Error ? error.message : "Reported event time is invalid.");
      return;
    }

    const contextId =
      "plant-context-" +
      (globalThis.crypto?.randomUUID?.() ?? String(Date.now()));
    const payload = {
      schema_version: "linealert.plant-reported-context.v1",
      context_id: contextId,
      service_case_id: serviceCase.id,
      asset_id: serviceCase.assetId,
      entered_at: new Date().toISOString(),
      entered_by: enteredBy.trim(),
      reported_source_class: sourceClass,
      reported_source: source.trim(),
      original_wording_or_bounded_summary: summary.trim(),
      source_verification_state: verification,
      reported_time_kind: timeKind,
      reported_clock_quality: clockQuality.trim(),
      reported_event_start: reportedEventStart,
      reported_event_end: reportedEventEnd,
      source_record_reference: sourceRecordReference.trim() || null,
      plant_contact_role: plantContactRole.trim() || null,
      provenance: [
        "speedway-service-workspace:manual-entry",
        "technician-entered-local-record",
      ],
      direct_system_observation: false,
      verified_source_record: false,
      causal_claim_established: false,
    };

    setSaving(true);
    try {
      const response = await fetch(
        "/api/service-cases/" +
          encodeURIComponent(serviceCase.id) +
          "/plant-context",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      const responsePayload = await response.json();
      if (!response.ok) {
        const detail =
          typeof responsePayload?.detail === "string"
            ? responsePayload.detail
            : "Local persistence rejected the entry.";
        setStoreError(detail);
        return;
      }
      setBundle(responsePayload as StoredBundle);
      setSummary("");
      setSourceRecordReference("");
      setPlantContactRole("");
      setContextOpen(false);
    } catch {
      setStoreReady(false);
      setStoreError("Local persistence became unavailable; nothing was saved.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>LINEALERT · SPEEDWAY SERVICE WORKSPACE · SYNTHETIC CASE</span>
          <h1>What changed before Speedway was called?</h1>
          <p>
            Reconstruct the pre-incident sequence, find the earliest defensible departure
            from expected behavior, identify missing plant context, and choose the next
            bounded technician check.
          </p>
          <small>
            First detected departure ≠ root cause · temporal precedence ≠ causation ·
            recommendation ≠ authorized action
          </small>
        </div>
        <nav className={styles.nav}>
          <Link className={styles.active} href="/">Service workspace</Link>
          <Link href="/reasoning">Reasoning inputs</Link>
          <Link href="/health">Evidence</Link>
          <Link href="/plant-canvas">Legacy Plant Canvas</Link>
        </nav>
      </header>

      <section className={styles.statusBar}>
        <div><span>SERVICE CASE</span><b>{serviceCase.id}</b></div>
        <div><span>ASSET</span><b>{serviceCase.asset}</b></div>
        <div><span>LOCAL CASE STORE</span><b>{storeLabel}</b></div>
        <div><span>HISTORIAN</span><b>{historianLabel}</b></div>
        <div><span>CASE ITEMS</span><b>{investigationCount}</b></div>
      </section>
      <section className={styles.caseHeader}>
        <div>
          <span className={styles.label}>WHY SPEEDWAY WAS CALLED</span>
          <h2>{serviceCase.symptom}</h2>
          <p>
            {serviceCase.customerId} · {serviceCase.siteId} · {serviceCase.assetId} ·
            {" "}configuration {serviceCase.configuration}
          </p>
        </div>
        <dl>
          <div><dt>Reported incident</dt><dd>{serviceCase.incident}</dd></div>
          <div><dt>Service call</dt><dd>{serviceCase.callReceived}</dd></div>
          <div><dt>Evidence window</dt><dd>{serviceCase.window}</dd></div>
          <div><dt>Reference</dt><dd>{serviceCase.callReference}</dd></div>
        </dl>
      </section>

      <section className={styles.timelineCard}>
        <div className={styles.sectionHeading}>
          <div>
            <span className={styles.label}>PRE-INCIDENT RECONSTRUCTION</span>
            <h2>Earliest retained move away from expected behavior</h2>
          </div>
          <b>NOT A ROOT-CAUSE CLAIM</b>
        </div>
        <div className={styles.timeline}>
          <div className={styles.timelinePoint}>
            <span>{timeLabel(persistedCase?.preincident_window_start) || "09:00"}</span>
            <strong>Expected behavior</strong>
            <small>Retained relationships inside the synthetic reference envelope.</small>
          </div>
          <div className={[styles.timelinePoint, styles.departure].join(" ")}>
            <span>{departure.time}</span><strong>First detected departure</strong>
            <small>{departure.reason}</small>
          </div>
          <div className={styles.timelinePoint}>
            <span>{serviceCase.incident}</span><strong>Reported incident</strong>
            <small>{serviceCase.symptom}</small>
          </div>
          <div className={styles.timelinePoint}>
            <span>{serviceCase.callReceived}</span><strong>Speedway called</strong>
            <small>Service case {serviceCase.callReference} opened.</small>
          </div>
        </div>
        <div className={styles.departureDetail}>
          <div><span>RELATIONSHIP</span><b>{departure.relationship}</b></div>
          <div><span>EXPECTED REFERENCE</span><b>{departure.expectedReference}</b></div>
          <div><span>CLOCK QUALITY</span><b>{departure.clockQuality}</b></div>
          <div><span>EVIDENCE</span><b>{departure.evidence.join(" · ")}</b></div>
        </div>
      </section>

      <section className={styles.twoColumn}>
        <article className={styles.card}>
          <span className={styles.label}>WHAT CHANGED</span>
          <h2>Relationships that moved</h2>
          <div className={styles.itemList}>
            {changedRelationships.map((item) => (
              <div className={styles.changedItem} key={item}>{item}</div>
            ))}
          </div>
        </article>

        <article className={styles.card}>
          <span className={styles.label}>WHAT HELD</span>
          <h2>Useful negative evidence</h2>
          <div className={styles.itemList}>
            {heldRelationships.map((item) => (
              <div className={styles.heldItem} key={item}>{item}</div>
            ))}
          </div>
        </article>
      </section>

      <section className={styles.contextCard}>
        <div className={styles.sectionHeading}>
          <div>
            <span className={styles.label}>MISSING DISCRIMINATING CONTEXT</span>
            <h2>Ask the plant about the window around {departure.time}</h2>
            <p>
              The first retained departure gives the technician a targeted historical
              question instead of a generic request for “anything unusual.”
            </p>
          </div>
          <button
            className={styles.primary}
            disabled={!storeReady || saving}
            onClick={() => setContextOpen((value) => !value)}
          >
            {contextOpen ? "Close entry" : "Record plant context"}
          </button>
        </div>

        <div className={styles.requestGrid}>
          {missingContext.map((item) => <div key={item}>{item}</div>)}
        </div>

        {storeError && <div className={styles.storeError}>{storeError}</div>}
        {bundle && (
          <div className={styles.storeNote}>
            LOCAL STORE · last write {dateTimeLabel(bundle.updated_at)} ·
            local persistence ≠ production CMMS/service record
          </div>
        )}

        {contextOpen && (
          <form className={styles.contextForm} onSubmit={addContext}>
            <label>
              Source class
              <select value={sourceClass} onChange={(event) => setSourceClass(event.target.value)}>
                <option value="cmms">CMMS</option>
                <option value="shift_log">Shift log</option>
                <option value="operator_statement">Operator statement</option>
                <option value="maintenance_statement">Maintenance statement</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label>
              Reported source
              <input value={source} onChange={(event) => setSource(event.target.value)} />
            </label>
            <label>
              Entered by
              <input value={enteredBy} onChange={(event) => setEnteredBy(event.target.value)} />
            </label>
            <label>
              Source verification
              <select
                value={verification}
                onChange={(event) => setVerification(event.target.value as VerificationState)}
              >
                <option value="plant_relay_only">Plant relay only</option>
                <option value="technician_viewed_source">Technician viewed source</option>
                <option value="technician_retained_copy">Technician retained copy</option>
              </select>
            </label>
            <label>
              Reported time kind
              <select
                value={timeKind}
                onChange={(event) => setTimeKind(event.target.value as ReportedTimeKind)}
              >
                <option value="window">Window</option>
                <option value="exact">Exact</option>
                <option value="approximate">Approximate</option>
                <option value="unknown">Unknown</option>
              </select>
            </label>
            <label>
              Reported clock quality
              <input value={clockQuality} onChange={(event) => setClockQuality(event.target.value)} />
            </label>
            {timeKind !== "unknown" && (
              <label>
                Reported event start
                <input
                  type="datetime-local"
                  value={eventStart}
                  onChange={(event) => setEventStart(event.target.value)}
                />
              </label>
            )}
            {timeKind === "window" && (
              <label>
                Reported event end
                <input
                  type="datetime-local"
                  value={eventEnd}
                  onChange={(event) => setEventEnd(event.target.value)}
                />
              </label>
            )}
            <label>
              Source record reference
              <input
                value={sourceRecordReference}
                onChange={(event) => setSourceRecordReference(event.target.value)}
                placeholder="Optional · e.g. WO-1842"
              />
            </label>
            <label>
              Plant contact role
              <input
                value={plantContactRole}
                onChange={(event) => setPlantContactRole(event.target.value)}
                placeholder="Optional · e.g. Plant maintenance"
              />
            </label>
            <label className={styles.fullWidth}>
              Original wording or bounded summary
              <textarea
                value={summary}
                onChange={(event) => setSummary(event.target.value)}
                placeholder="Example: Plant CMMS shows guide rail adjusted after intermittent bottle backup."
                rows={4}
              />
            </label>
            <div className={styles.formBoundary}>
              This record is persisted locally on the LineAlert host. It remains
              <b> plant_reported_context</b>; local persistence does not make it a
              verified source record, direct CMMS ingestion, or causal proof.
            </div>
            <button className={styles.primary} disabled={saving} type="submit">
              {saving ? "Saving…" : "Persist reported context"}
            </button>
          </form>
        )}
        {contexts.length > 0 && (
          <div className={styles.contextList}>
            {contexts.map((item) => (
              <article key={item.context_id}>
                <div>
                  <span>
                    {item.reported_source_class.toUpperCase()} ·
                    {" "}{item.source_verification_state.replaceAll("_", " ")}
                  </span>
                  <b>{item.reported_source}</b>
                </div>
                <p>{item.original_wording_or_bounded_summary}</p>
                <small>
                  Reported time {reportedTimeLabel(item)} · clock quality
                  {" "}{item.reported_clock_quality} · entered
                  {" "}{dateTimeLabel(item.entered_at)} by {item.entered_by}
                </small>
                {(item.source_record_reference || item.plant_contact_role) && (
                  <small>
                    {item.source_record_reference
                      ? "Source ref " + item.source_record_reference
                      : "No source record reference"}
                    {item.plant_contact_role
                      ? " · contact " + item.plant_contact_role
                      : ""}
                  </small>
                )}
              </article>
            ))}
          </div>
        )}
      </section>

      <section className={styles.twoColumn}>
        <article className={styles.card}>
          <span className={styles.label}>WORKING EXPLANATIONS</span>
          <h2>Keep alternatives visible</h2>
          <div className={styles.explanationList}>
            {workingExplanations.map((item) => (
              <div key={item.title}>
                <span>{item.standing}</span>
                <b>{item.title}</b>
                <p>{item.why}</p>
              </div>
            ))}
          </div>
          <small className={styles.boundaryText}>
            Investigation standing is qualitative. It is not a hidden causal probability.
          </small>
        </article>

        <article className={styles.nextCard}>
          <span className={styles.label}>NEXT BOUNDED TECHNICIAN CHECK</span>
          <h2>Verify bottle presentation / guide relationship before changing timing.</h2>
          <p>
            Inspect the presentation path and compare visible guide/spacing references with
            the applicable commissioned/OEM reference if one is available. Record the
            observation before making a material change.
          </p>
          <div className={styles.nextMeta}>
            <span>Observation first</span>
            <span>Low disturbance</span>
            <span>Reversible</span>
          </div>
          <b>
            This is a troubleshooting recommendation, not authorization to adjust the machine.
          </b>
        </article>
      </section>

      <section className={styles.boundary}>
        <div>
          <span className={styles.label}>V1 PRODUCT BOUNDARY</span>
          <b>
            Service evidence → first detected departure → targeted plant question →
            technician observation/test → bounded finding.
          </b>
        </div>
        <p>
          Service cases and technician-entered plant context are now retained in the
          desktop&apos;s local LineAlert store. That local record is not a plant CMMS record,
          verified machine truth, or production authority. This screen does not write to
          CMMS or historian systems, control equipment, establish root cause, approve safety,
          or authorize return to service.
        </p>
      </section>
    </main>
  );
}
