"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import styles from "./triage-board.module.css";

type PlanState = "HOLDS" | "WATCH" | "ADAPT";
type Owner = "Shift supervisor" | "Operator" | "Maintenance" | "Plant manager";
type AssetId = "filler" | "labeler" | "packer" | "palletizer";
type OperatorResult = "appears_clear" | "issue_observed" | "cannot_verify";

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

    setAssets((current) => current.map((asset) => {
      if (asset.id !== "labeler") return asset;
      if (result === "appears_clear") {
        return { ...asset, owner: "Shift supervisor", plan: "WATCH", next: "Review the recorded visible check and decide whether another qualified check is justified.", latestObservation: observation };
      }
      return { ...asset, owner: "Maintenance", plan: "WATCH", next: result === "issue_observed" ? "Inspect the reported application relationship; operator stopped at the observation boundary." : "Perform the check from an authorized safe position; operator could not verify it.", latestObservation: observation };
    }));
    setOperatorOpen(false);
  };

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>LINEALERT · PLANT CANVAS · SYNTHETIC DEMO</span>
          <h1>{posture}</h1>
          <p>Model the plant, see where a concern lives, who owns it, what it affects, and the next bounded action.</p>
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
        <div><span>PRODUCT RULE</span><b>Canvas shows operational posture. Details appear only when needed.</b></div>
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
            <div className={styles.dependencyNote}>Process flow: Filler 1 → Labeler 2 → Case Packer 1 → Palletizer 1. Relationship is illustrative, not commissioned plant truth.</div>
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
            {selected.id === "labeler" && selected.owner === "Shift supervisor" && <button className={styles.primaryAction} onClick={assignOperator}>Assign one operator check</button>}
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
          <small className={styles.operatorBoundary}>Operator observation ≠ verified physical state. No adjustment is authorized by this demo.</small>
        </section>
      )}

      <section className={styles.boundary}><div><span>V1 BOUNDARY</span><b>Model the plant → locate the concern → assign the next bounded action.</b></div><p>No telemetry, PLC/controller, CMMS, dispatch, safety-control or equipment-control connection is added here. The topology and workflow are synthetic feedback content.</p></section>
    </main>
  );
}
