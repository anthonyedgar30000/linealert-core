"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import styles from "./triage-board.module.css";

type PlanState = "HOLDS" | "WATCH" | "ADAPT";
type Owner = "Shift supervisor" | "Operator" | "Maintenance" | "Plant manager";
type AssetId = "filler" | "labeler" | "packer" | "palletizer";
type OperatorResult = "appears_clear" | "issue_observed" | "cannot_verify";
type ReviewState = "PENDING" | "ACCEPTED" | "CORRECTION NEEDED" | "ESCALATED";
type TrialState = "AWAITING RUN EVIDENCE" | "READY FOR HUMAN REVIEW";

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
  runContext: string;
  visualEvidence: string;
  telemetryEvidence: string;
  qualityEvidence: string;
  provenance: string[];
  state: TrialState;
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
    const next = result === "cannot_verify"
      ? "Maintenance performs the check from an authorized safe position; any later intervention must be followed by a fresh bounded run."
      : "Await the approved bounded run. LineAlert should collect available evidence automatically when the completed-run event arrives.";

    setAssets((current) => current.map((asset) => asset.id === "labeler" ? { ...asset, owner, plan: "WATCH", next, latestObservation: observation } : asset));
    setTrial({
      id: `LA-TRIAL-${Date.now().toString().slice(-6)}`,
      asset: "Labeler 2",
      requestedBy: owner,
      triggerObservation: observation,
      requestedRun: "5-container bounded verification trial · synthetic demo parameter",
      timestamp: new Date().toLocaleString(),
      runContext: "Awaiting admitted completed-run source",
      visualEvidence: "Awaiting admitted camera/classifier evidence",
      telemetryEvidence: "No live telemetry source connected",
      qualityEvidence: "No live quality/reject-count source connected",
      provenance: [
        "Asset identity · Plant Canvas synthetic topology",
        "Trigger observation · Operator supplied · unverified",
        "Trial request · Deterministic workflow rule",
        "Timestamp · Browser session",
      ],
      state: "AWAITING RUN EVIDENCE",
      review: "PENDING",
    });
    setOperatorOpen(false);
  };

  const receiveSyntheticRunEvent = () => {
    setTrial((current) => current ? {
      ...current,
      runContext: "Synthetic completed-run event received · 5 containers observed",
      visualEvidence: "Synthetic camera classifier: 4/5 containers appear within demo visual alignment envelope; 1 apparent skew event.",
      telemetryEvidence: "No live telemetry source connected · field intentionally remains unpopulated",
      qualityEvidence: "Synthetic demo counter: 4 visually acceptable · 1 apparent reject candidate",
      provenance: [
        ...current.provenance,
        "Run context · Synthetic completed-run event",
        "Visual evidence · Synthetic AI-camera classification",
        "Quality evidence · Synthetic demo counter",
        "Telemetry evidence · Source unavailable; no value inferred",
      ],
      state: "READY FOR HUMAN REVIEW",
    } : current);
    setAssets((current) => current.map((asset) => asset.id === "labeler" ? { ...asset, next: "Review the auto-assembled trial record. Confirm, correct, or escalate; do not re-enter evidence LineAlert already has." } : asset));
  };

  const reviewTrial = (review: ReviewState) => {
    setTrial((current) => current ? { ...current, review } : current);
    if (review === "ACCEPTED") {
      setAssets((current) => current.map((asset) => asset.id === "labeler" ? { ...asset, owner: "Shift supervisor", next: "Review the accepted trial result and decide whether another single bounded action is justified." } : asset));
    }
    if (review === "ESCALATED") {
      setAssets((current) => current.map((asset) => asset.id === "labeler" ? { ...asset, owner: "Maintenance", next: "Review the auto-assembled trial evidence package before any further intervention." } : asset));
    }
  };

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>LINEALERT · PLANT CANVAS · SYNTHETIC DEMO</span>
          <h1>{posture}</h1>
          <p>Model the plant, locate the concern, assign one bounded action, run, let LineAlert assemble the evidence, then ask a human only for judgment, correction, or authorization.</p>
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
        <div><span>PRODUCT RULE</span><b>System populates the record. Human confirms, corrects, or escalates.</b></div>
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
          <small className={styles.operatorBoundary}>The operator records only the observation. After an authorized run, connected evidence should populate automatically. Operator observation ≠ verified physical state. No adjustment is authorized by this demo.</small>
        </section>
      )}

      {trial && (
        <section className={styles.trialCard} aria-label="Bounded verification trial">
          <div className={styles.trialHeading}>
            <div><span>BOUNDED TRIAL · AUTO-ASSEMBLED RECORD</span><h2>{trial.id}</h2></div>
            <b>{trial.state}</b>
          </div>
          <div className={styles.trialGrid}>
            <div><span>Asset</span><strong>{trial.asset}</strong><small>auto-populated · canvas context</small></div>
            <div><span>Requested by</span><strong>{trial.requestedBy}</strong><small>auto-populated · workflow owner</small></div>
            <div><span>Run</span><strong>{trial.requestedRun}</strong><small>workflow rule · not production authorization</small></div>
            <div><span>Timestamp</span><strong>{trial.timestamp}</strong><small>auto-populated · browser session</small></div>
          </div>
          <div className={styles.trialEvidence}>
            <div><span>Trigger observation</span><p>{trial.triggerObservation}</p></div>
            <div><span>Run context</span><p>{trial.runContext}</p></div>
            <div><span>Visual evidence</span><p>{trial.visualEvidence}</p></div>
            <div><span>Quality evidence</span><p>{trial.qualityEvidence}</p></div>
            <div><span>Telemetry</span><p>{trial.telemetryEvidence}</p></div>
          </div>
          <div className={styles.provenance}><span>PROVENANCE</span>{trial.provenance.map((item) => <small key={item}>{item}</small>)}</div>
          {trial.state === "AWAITING RUN EVIDENCE" ? (
            <button className={styles.primaryAction} onClick={receiveSyntheticRunEvent}>Demo only · receive completed-run event</button>
          ) : (
            <div className={styles.reviewActions}>
              <button onClick={() => reviewTrial("ACCEPTED")}>Confirm record</button>
              <button onClick={() => reviewTrial("CORRECTION NEEDED")}>Correct something</button>
              <button onClick={() => reviewTrial("ESCALATED")}>Escalate</button>
            </div>
          )}
          <small className={styles.operatorBoundary}>In a connected deployment the completed-run event and admitted camera, telemetry, MES, and quality sources would populate this record without human re-entry. The demo button represents that external event; it does not authorize or execute a machine run. AI-camera output remains classified evidence, not verified physical state or root-cause proof.</small>
        </section>
      )}

      <section className={styles.boundary}><div><span>V1 BOUNDARY</span><b>One bounded action → authorized run → automatic evidence assembly → human judgment.</b></div><p>No live telemetry, camera, PLC/controller, MES, quality system, CMMS, dispatch, safety-control or equipment-control connection is added here. Trial execution remains synthetic feedback content; recommendation is not authorized action.</p></section>
    </main>
  );
}
