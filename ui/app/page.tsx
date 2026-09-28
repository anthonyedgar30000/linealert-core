"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import styles from "./service-workspace.module.css";

type VerificationState =
  | "plant_relay_only"
  | "technician_viewed_source"
  | "technician_retained_copy";

type PlantContext = {
  id: string;
  sourceClass: string;
  source: string;
  summary: string;
  verification: VerificationState;
  eventTime: string;
  clockQuality: string;
  enteredAt: string;
};

const serviceCase = {
  id: "svc-2026-0042",
  customer: "Synthetic customer",
  site: "Packaging Hall A",
  asset: "Labeler 2",
  assetId: "LABELER-02",
  callReference: "CALL-0042",
  callReceived: "12:45",
  incident: "12:00",
  symptom: "Labels intermittently skewing and bottle flow backing up.",
  window: "09:00–12:00",
  configuration: "cfg-2026-09-01",
} as const;

const departure = {
  time: "10:00",
  relationship: "Bottle presentation → label feed timing",
  expectedReference: "baseline:labeler-02:v7",
  reason: "Presentation variability moved outside the expected envelope.",
  clockQuality: "Synchronized cross-source interval",
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

function nowLabel() {
  return new Date().toLocaleString();
}

export default function SpeedwayServiceWorkspace() {
  const [historianConnected, setHistorianConnected] = useState<boolean | null>(null);
  const [contextOpen, setContextOpen] = useState(false);
  const [contexts, setContexts] = useState<PlantContext[]>([]);
  const [sourceClass, setSourceClass] = useState("cmms");
  const [source, setSource] = useState("Plant CMMS");
  const [eventTime, setEventTime] = useState("09:40–10:20");
  const [clockQuality, setClockQuality] = useState("unknown");
  const [verification, setVerification] =
    useState<VerificationState>("plant_relay_only");
  const [summary, setSummary] = useState("");

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

  const historianLabel =
    historianConnected === null
      ? "CHECKING"
      : historianConnected
        ? "AVAILABLE"
        : "OFFLINE · FAIL CLOSED";

  const investigationCount = useMemo(
    () => changedRelationships.length + heldRelationships.length + contexts.length,
    [contexts],
  );

  const addContext = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!summary.trim() || !source.trim() || !eventTime.trim() || !clockQuality.trim()) {
      return;
    }
    setContexts((current) => [
      ...current,
      {
        id: "plant-context-browser-" + (current.length + 1),
        sourceClass,
        source: source.trim(),
        summary: summary.trim(),
        verification,
        eventTime: eventTime.trim(),
        clockQuality: clockQuality.trim(),
        enteredAt: nowLabel(),
      },
    ]);
    setSummary("");
    setContextOpen(false);
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
        <div><span>HISTORIAN</span><b>{historianLabel}</b></div>
        <div><span>ADMITTED CASE ITEMS</span><b>{investigationCount}</b></div>
      </section>
      <section className={styles.caseHeader}>
        <div>
          <span className={styles.label}>WHY SPEEDWAY WAS CALLED</span>
          <h2>{serviceCase.symptom}</h2>
          <p>
            {serviceCase.customer} · {serviceCase.site} · {serviceCase.assetId} ·
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
            <span>09:00</span><strong>Expected behavior</strong>
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
            <h2>Ask the plant about the window around 10:00</h2>
            <p>
              The first retained departure gives the technician a targeted historical
              question instead of a generic request for “anything unusual.”
            </p>
          </div>
          <button className={styles.primary} onClick={() => setContextOpen((value) => !value)}>
            {contextOpen ? "Close entry" : "Record plant context"}
          </button>
        </div>

        <div className={styles.requestGrid}>
          {missingContext.map((item) => <div key={item}>{item}</div>)}
        </div>

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
              Reported event time / window
              <input value={eventTime} onChange={(event) => setEventTime(event.target.value)} />
            </label>
            <label>
              Reported clock quality
              <input value={clockQuality} onChange={(event) => setClockQuality(event.target.value)} />
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
              Browser-session entry only. It remains <b>plant_reported_context</b> and is
              not promoted to a verified source record or direct system observation.
            </div>
            <button className={styles.primary} type="submit">Add reported context</button>
          </form>
        )}

        {contexts.length > 0 && (
          <div className={styles.contextList}>
            {contexts.map((item) => (
              <article key={item.id}>
                <div>
                  <span>{item.sourceClass.toUpperCase()} · {item.verification.replaceAll("_", " ")}</span>
                  <b>{item.source}</b>
                </div>
                <p>{item.summary}</p>
                <small>
                  Reported time {item.eventTime} · clock quality {item.clockQuality} · entered {item.enteredAt}
                </small>
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
          Plant operators and internal maintenance are evidence/context sources, not required
          LineAlert users. This screen does not persist service cases, write to CMMS or
          historian systems, control equipment, establish root cause, approve safety, or
          authorize return to service. The preserved operator-oriented demo remains available
          under Legacy Plant Canvas.
        </p>
      </section>
    </main>
  );
}
