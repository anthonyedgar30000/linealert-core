"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

import styles from "./triage-board.module.css";

type TriageStage = "INTAKE" | "TRIAGE" | "ASSIGNED" | "RESPONDING" | "VERIFY";

type TriageItem = {
  id: string;
  asset: string;
  summary: string;
  stage: TriageStage;
  owner: string;
  next: string;
  plan: "HOLDS" | "WATCH" | "ADAPT";
  runway?: string;
  responseEta?: string;
  source: string;
};

const seededItems: TriageItem[] = [
  {
    id: "LA-DEMO-104",
    asset: "Labeler 2",
    summary: "Operator reports intermittent hesitation after roll change.",
    stage: "ASSIGNED",
    owner: "Maintenance",
    next: "Observe until maintenance arrives; no additional operator action requested.",
    plan: "HOLDS",
    runway: "~70 min",
    responseEta: "32 min",
    source: "Synthetic demo observation",
  },
  {
    id: "LA-DEMO-105",
    asset: "CNC Cell A",
    summary: "Two updated controllers stopped reporting to the historian after a firmware change.",
    stage: "TRIAGE",
    owner: "Shift supervisor",
    next: "Confirm shared gateway path and maintenance availability before escalating.",
    plan: "WATCH",
    runway: "~95 min",
    responseEta: "44 min",
    source: "Synthetic dependency-risk demo",
  },
  {
    id: "LA-DEMO-106",
    asset: "Packaging Line 1",
    summary: "Downstream buffer is shrinking faster than the expected response window.",
    stage: "RESPONDING",
    owner: "Plant manager",
    next: "Choose an approved adaptation that preserves flow until qualified response arrives.",
    plan: "ADAPT",
    runway: "26 min",
    responseEta: "47 min",
    source: "Synthetic operational-context demo",
  },
];

const stageOrder: TriageStage[] = ["INTAKE", "TRIAGE", "ASSIGNED", "RESPONDING", "VERIFY"];

export default function TriageBoard() {
  const [items, setItems] = useState<TriageItem[]>(seededItems);
  const [quickUpdate, setQuickUpdate] = useState("");
  const [lastCaptured, setLastCaptured] = useState<string | null>(null);

  const adaptCount = items.filter((item) => item.plan === "ADAPT").length;
  const watchCount = items.filter((item) => item.plan === "WATCH").length;
  const plantPosture = adaptCount > 0 ? "ADAPTATION REQUIRED" : watchCount > 0 ? "PLAN HOLDS · WATCHING" : "PLAN HOLDS";

  const grouped = useMemo(() => {
    const result = new Map<TriageStage, TriageItem[]>();
    stageOrder.forEach((stage) => result.set(stage, []));
    items.forEach((item) => result.get(item.stage)?.push(item));
    return result;
  }, [items]);

  const captureUpdate = (event: FormEvent) => {
    event.preventDefault();
    const observation = quickUpdate.trim();
    if (!observation) return;

    const item: TriageItem = {
      id: `LA-DEMO-${107 + items.length}`,
      asset: "Unassigned asset",
      summary: observation,
      stage: "INTAKE",
      owner: "Triage queue",
      next: "Attach asset/run context and decide whether management attention is justified.",
      plan: "HOLDS",
      source: "Operator observation — unverified · browser-session demo only",
    };

    setItems((current) => [item, ...current]);
    setLastCaptured(observation);
    setQuickUpdate("");
  };

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>LINEALERT · TRIAGE BOARD · SYNTHETIC DEMO</span>
          <h1>{plantPosture}</h1>
          <p>
            Intake, triage, ownership, response and verification. The board shows what needs attention now;
            deeper evidence stays behind the workflow.
          </p>
        </div>
        <nav className={styles.nav} aria-label="LineAlert navigation">
          <Link href="/health">Evidence / history</Link>
          <Link href="/training">Training</Link>
          <Link href="/commissioning">Commissioning</Link>
        </nav>
      </header>

      <section className={styles.posture} aria-label="Plant triage posture">
        <div><span>ACTIVE ITEMS</span><b>{items.length}</b></div>
        <div><span>WATCHING</span><b>{watchCount}</b></div>
        <div><span>ADAPT</span><b>{adaptCount}</b></div>
        <div><span>BOARD RULE</span><b>Only interrupt when the plan may need attention.</b></div>
      </section>

      <section className={styles.intake}>
        <div>
          <span className={styles.sectionLabel}>QUICK UPDATE</span>
          <h2>Say it before you forget it.</h2>
          <p>
            Capture the observation now. LineAlert preserves the original wording and routes it into triage;
            this demo does not claim the observation is verified machine evidence.
          </p>
        </div>
        <form onSubmit={captureUpdate} className={styles.intakeForm}>
          <textarea
            aria-label="Quick update observation"
            value={quickUpdate}
            onChange={(event) => setQuickUpdate(event.target.value)}
            placeholder="It started sounding rough after the roll change…"
            rows={3}
          />
          <button type="submit">Record update</button>
        </form>
        {lastCaptured && (
          <div className={styles.receipt}>
            <b>Update received.</b>
            <span>Added to Intake as an unverified operator observation. No equipment action was authorized.</span>
          </div>
        )}
      </section>

      <section className={styles.board} aria-label="Triage workflow board">
        {stageOrder.map((stage) => (
          <section className={styles.column} key={stage}>
            <header>
              <span>{stage}</span>
              <b>{grouped.get(stage)?.length ?? 0}</b>
            </header>
            <div className={styles.cardStack}>
              {(grouped.get(stage) ?? []).map((item) => (
                <article className={`${styles.card} ${styles[item.plan.toLowerCase()]}`} key={item.id}>
                  <div className={styles.cardTopline}>
                    <span>{item.asset}</span>
                    <small>{item.id}</small>
                  </div>
                  <h3>{item.summary}</h3>
                  <dl>
                    <div><dt>Owner</dt><dd>{item.owner}</dd></div>
                    {item.runway && <div><dt>Runway</dt><dd>{item.runway}</dd></div>}
                    {item.responseEta && <div><dt>Response ETA</dt><dd>{item.responseEta}</dd></div>}
                    <div><dt>Plan</dt><dd>{item.plan}</dd></div>
                  </dl>
                  <div className={styles.nextStep}>
                    <span>NEXT</span>
                    <p>{item.next}</p>
                  </div>
                  <small className={styles.source}>{item.source}</small>
                </article>
              ))}
              {(grouped.get(stage)?.length ?? 0) === 0 && (
                <div className={styles.empty}>Nothing waiting here.</div>
              )}
            </div>
          </section>
        ))}
      </section>

      <section className={styles.boundary}>
        <div>
          <span>V1 BOUNDARY</span>
          <b>Make abnormal situations feel organized before they feel solved.</b>
        </div>
        <p>
          This surface performs demo intake and workflow orientation only. Triage is not diagnosis,
          recommendation is not authorized action, and historical evidence does not prove current root cause.
        </p>
      </section>
    </main>
  );
}
