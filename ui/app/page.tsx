"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import styles from "./triage-board.module.css";

type PlanState = "HOLDS" | "WATCH" | "ADAPT";
type Owner = "Shift supervisor" | "Operator" | "Maintenance" | "Plant manager";
type AssetId = "filler" | "labeler" | "packer" | "palletizer";
type OperatorResult = "appears_clear" | "issue_observed" | "cannot_verify";
type ReviewState = "PENDING" | "ACCEPTED" | "CORRECTION NEEDED" | "ESCALATED";

type Asset = {
  id: AssetId;
  name: string;
  role: string;
  plan: PlanState;
  owner: Owner;
  next: string;
  concern?: string;
  latestObservation?: string;
  runway?: string;
  responseEta?: string;
};

type TrialRecord = {
  id: string;
  asset: string;
  requestedBy: string;
  triggerObservation: string;
  requestedRun: string;
  timestamp: string;
  visualEvidence: string;
  telemetryEvidence: string;
  provenance: string[];
  review: ReviewState;
};

const seedAssets: Asset[] = [
  { id: "filler", name: "Filler 1", role: "Upstream process", plan: "HOLDS", owner: "Shift supervisor", next: "No action requested." },
  { id: "labeler", name: "Labeler 2", role: "Application process", plan: "WATCH", owner: "Shift supervisor", next: "Assign one bounded visible check if it is within operator authority.", concern: "Operator reports label alignment is off after a roll change.", runway: "~70 min", responseEta: "32 min" },
  { id: "packer", name: "Case Packer 1", role: "Downstream dependency", plan: "HOLDS", owner: "Shift supervisor", next: "No action requested." },
  { id: "palletizer", name: "Palletizer 1", role: "Downstream process", plan: "HOLDS", owner: "Shift supervisor", next: "No action requested." },
];

export default function PlantCanvas() {
  const [assets, setAssets] = useState(seedAssets);
  const [selectedId, setSelectedId] = useState<AssetId>("labeler");
  const [operatorOpen, setOperatorOpen] = useState(false);
  const [view, setView] = useState<"canvas" | "board">("canvas");
  const [trial, setTrial] = useState<TrialRecord | null>(null);

  const selected = assets.find((asset) => asset.id === selectedId) ?? assets[0];
  const activeCount = assets.filter((asset) => asset.concern).length;
  const posture = assets.some((asset) => asset.plan === "ADAPT") ? "ADAPTATION REQUIRED" : assets.some((asset) => asset.plan === "WATCH") ? "PLAN HOLDS · WATCHING" : "PLAN HOLDS";

  const boardGroups = useMemo(() => ({
    TRIAGE: assets.filter((asset) => asset.concern && asset.owner === "Shift supervisor"),
    ASSIGNED: assets.filter((asset) => asset.concern && (asset.owner === "Operator" || asset.owner === "Maintenance")),
    RESPONDING: assets.filter((asset) => asset.concern && asset.owner === "Plant manager"),
  }), [assets]);

  const assignOperator = () => {
    setAssets((current) => current.map((asset) => asset.id === "labeler" ? { ...asset, owner: "Operator", next: "Answer the single visible-condition check from the approved operating position." } : asset));
    setSelectedId("labeler");
    setOperatorOpen(true);
  };

  const recordResult = (result: OperatorResult) => {
    const observation = result === "appears_clear"
      ? "Operator reports the visible application relationship appears aligned."
      : result === "issue_observed"
        ? "Operator reports the visible application relationship appears out of alignment."
        : "Operator could not verify the visible application relationship safely.";

    const owner: Owner = result === "appears_clear" ? "Shift supervisor" : "Maintenance";
    const next = result === "appears_clear"
      ? "Request one approved bounded verification run before any additional check or change."
      : result === "issue_observed"
        ? "Maintenance reviews the observation, then requests one approved bounded verification run before any additional intervention."
        : "Maintenance performs the check from an authorized safe position; any later intervention must be followed by a fresh bounded run.";

    setAssets((current) => current.map((asset) => asset.id === "labeler" ? { ...asset, owner, plan: "WATCH", next, latestObservation: observation } : asset));
    setTrial({
      id: `LA-TRIAL-${Date.now().toString().slice(-6)}`,
      asset: "Labeler 2",
      requestedBy: owner,
      triggerObservation: observation,
      requestedRun: "5-container bounded verification trial · synthetic demo parameter",
      timestamp: new Date().toLocaleString(),
      visualEvidence: "Awaiting visual feedback",
      telemetryEvidence: "No live telemetry source connected",
      provenance: [
        "Asset identity · Plant Canvas synthetic topology",
        "Trigger observation · Operator supplied · unverified",
        "Trial request · Deterministic workflow rule",
        "Timestamp · Browser session",
      ],
      review: "PENDING",
    });
    setOperatorOpen(false);
  };

  const simulateEvidence = () => {
    setTrial((current) => current ? {
      ...current,
      visualEvidence: "Synthetic camera classifier: 4/5 containers appear within demo visual alignment envelope; 1 apparent skew event.",
      telemetryEvidence: "No live telemetry source connected · telemetry field intentionally unpopulated",
      provenance: [
        ...current.provenance.filter((item) => !item.startsWith("Visual evidence")),
        "Visual evidence · Synthetic AI-camera classification for feedback demo",
        "Telemetry evidence · Source unavailable; no value inferred",
      ],
    } : current);
  };

  const reviewTrial = (review: ReviewState) => {
    setTrial((current) => current ? { ...current, review } : current);
    if (review === "ACCEPTED") {
      setAssets((current) => current.map((asset) => asset.id === "labeler" ? { ...asset, owner: "Shift supervisor", next: "Review the accepted trial record and decide whether another single bounded action is justified." } : asset));
    }
    if (review === "ESCALATED") {
      setAssets((current) => current.map((asset) => asset.id === "labeler" ? { ...asset, owner: "Maintenance", next: "Review the trial evidence package before any further intervention." } : asset));
    }
  };

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>LINEALERT · PLANT CANVAS · SYNTHETIC DEMO</span>
          <h1>{posture}</h1>
          <p>Model the plant, locate the concern, assign one bounded action, run, collect evidence, and ask a human only for judgment or authorization.</p>
        </div>
        <nav className={styles.nav}>
          <button className={view === "canvas" ? styles.activeView : ""} onClick={() => setView("canvas")}>Plant canvas</button>
          <button className={view === "board" ? styles.activeView : ""} onClick={() => setView("board")}>Triage board</button>
          <Link href="/health">Evidence</Link>
        </nav>
      </header>

      <section className={styles.posture}>
        <div><span>ACTIVE CONCERNS</span><b>{activeCount}</b></div>
        <div><span>SELECTED ASSET</span><b>{selected.name}</b></div>
        <div><span>PLAN</span><b>{selected.plan}</b></div>
        <div><span>PRODUCT RULE</span><b>One material change per trial. Re-run before advancing.</b></div>
      </section>

      {view === "canvas" ? (
        <section className={styles.canvasLayout}>
          <section className={styles.canvas} aria-label="Synthetic packaging line topology">
            <div className={styles.canvasHeader}>
              <div><span>PACKAGING LINE 1</span><h2>Plant model</h2></div>
              <small>Synthetic topology · browser-session workflow state</small>
            </div>
            <div className={styles.flow}>
              {assets.map((asset, index) => (
                <div className={styles.flowItem} key={asset.id}>
                  <button className={`${styles.assetNode} ${styles[asset.plan.toLowerCase()]} ${selectedId === asset.id ? styles.selected : ""}`} onClick={() => setSelectedId(asset.id)}>
                    <span>{asset.role}</span><b>{asset.name}</b><small>{asset.concern ? asset.owner : "Stable"}</small>
                  </button>
                  {index < assets.length - 1 && <div className={styles.connector} aria-hidden="true">→</div>}
                </div>
              ))}
            </div>
            <div className={styles.dependencyNote}>Process flow is illustrative, not commissioned plant truth. Relationship display does not prove causation.</div>
          </section>

          <aside className={styles.assetPanel}>
            <span className={styles.sectionLabel}>ASSET</span>
            <h2>{selected.name}</h2>
            <p className={styles.assetRole}>{selected.role}</p>
            <dl>
              <div><dt>Posture</dt><dd>{selected.plan}</dd></div>
              <div><dt>Owner</dt><dd>{selected.owner}</dd></div>
              {selected.runway && <div><dt>Runway</dt><dd>{selected.runway}</dd></div>}
              {selected.responseEta && <div><dt>Response ETA</dt><dd>{selected.responseEta}</dd></div>}
            </dl>
            {selected.concern ? <div className={styles.concern}><span>CURRENT CONCERN</span><p>{selected.concern}</p></div> : <div className={styles.quiet}>No active concern on this synthetic asset.</div>}
            {selected.latestObservation && <div className={styles.observationNote}><span>LATEST OBSERVATION</span><p>{selected.latestObservation}</p></div>}
            <div className={styles.nextStep}><span>NEXT</span><p>{selected.next}</p></div>
            {selected.id === "labeler" && selected.owner === "Shift supervisor" && !trial && <button className={styles.primaryAction} onClick={assignOperator}>Assign one operator check</button>}
            {selected.id === "labeler" && selected.owner === "Operator" && <button className={styles.primaryAction} onClick={() => setOperatorOpen(true)}>Open operator check</button>}
          </aside>
        </section>
      ) : (
        <section className={styles.boardView}>
          {Object.entries(boardGroups).map(([stage, items]) => <section className={styles.boardColumn} key={stage}><header><span>{stage}</span><b>{items.length}</b></header>{items.length ? items.map((asset) => <button key={asset.id} onClick={() => { setSelectedId(asset.id); setView("canvas"); }}><strong>{asset.name}</strong><span>{asset.owner}</span><small>{asset.next}</small></button>) : <div className={styles.empty}>Nothing waiting here.</div>}</section>)}
        </section>
      )}

      {operatorOpen && (
        <section className={styles.operatorTask}>
          <div className={styles.operatorTaskHeading}><div><span>OPERATOR · ONE BOUNDED CHECK</span><small>Labeler 2</small></div><button onClick={() => setOperatorOpen(false)}>Close</button></div>
          <h2>From the approved operating position, does the visible label application relationship appear aligned?</h2>
          <p><b>Why this check:</b> It tells triage whether a qualified mechanical inspection is needed. It does not establish root cause.</p>
          <div className={styles.operatorAnswers}><button onClick={() => recordResult("appears_clear")}>Appears aligned</button><button onClick={() => recordResult("issue_observed")}>Appears out of alignment</button><button onClick={() => recordResult("cannot_verify")}>Can’t verify safely</button></div>
          <small className={styles.operatorBoundary}>Every answer records one observation and requests a fresh bounded run before another material change. Operator observation ≠ verified physical state. No adjustment is authorized by this demo.</small>
        </section>
      )}

      {trial && (
        <section className={styles.trialCard} aria-label="Bounded verification trial">
          <div className={styles.trialHeading}>
            <div><span>BOUNDED TRIAL · HUMAN IN THE LOOP</span><h2>{trial.id}</h2></div>
            <b>{trial.review}</b>
          </div>
          <div className={styles.trialGrid}>
            <div><span>Asset</span><strong>{trial.asset}</strong><small>auto-populated · canvas context</small></div>
            <div><span>Requested by</span><strong>{trial.requestedBy}</strong><small>auto-populated · workflow owner</small></div>
            <div><span>Run</span><strong>{trial.requestedRun}</strong><small>workflow rule · not production authorization</small></div>
            <div><span>Timestamp</span><strong>{trial.timestamp}</strong><small>auto-populated · browser session</small></div>
          </div>
          <div className={styles.trialEvidence}>
            <div><span>Trigger observation</span><p>{trial.triggerObservation}</p></div>
            <div><span>Visual evidence</span><p>{trial.visualEvidence}</p></div>
            <div><span>Telemetry</span><p>{trial.telemetryEvidence}</p></div>
          </div>
          <div className={styles.provenance}><span>PROVENANCE</span>{trial.provenance.map((item) => <small key={item}>{item}</small>)}</div>
          {trial.visualEvidence === "Awaiting visual feedback" ? (
            <button className={styles.primaryAction} onClick={simulateEvidence}>Simulate camera feedback</button>
          ) : (
            <div className={styles.reviewActions}>
              <button onClick={() => reviewTrial("ACCEPTED")}>Accept record</button>
              <button onClick={() => reviewTrial("CORRECTION NEEDED")}>Correction needed</button>
              <button onClick={() => reviewTrial("ESCALATED")}>Escalate</button>
            </div>
          )}
          <small className={styles.operatorBoundary}>Synthetic AI-camera output is classified evidence, not verified physical state or root-cause proof. Missing sources stay missing; LineAlert does not silently fill them.</small>
        </section>
      )}

      <section className={styles.boundary}><div><span>V1 BOUNDARY</span><b>Observe → one bounded action → run → collect evidence → human review.</b></div><p>No live telemetry, camera, PLC/controller, CMMS, dispatch, safety-control or equipment-control connection is added here. Trial execution remains synthetic feedback content; recommendation is not authorized action.</p></section>
    </main>
  );
}
