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
type InterventionId = "inspect-presentation-stability" | "repeat-like-for-like" | "verify-guide-spacing" | "request-reduced-speed-trial" | "review-label-timing-geometry";

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
  scenarioId: string;
  asset: string;
  requestedBy: string;
  triggerObservation: string;
  requestedRun: string;
  timestamp: string;
  runContext: string;
  visualEvidence: string;
  telemetryEvidence: string;
  qualityEvidence: string;
  comparison: string;
  boundedFinding: string;
  provenance: string[];
  state: TrialState;
  review: ReviewState;
};

type RankedIntervention = {
  id: InterventionId;
  rank: number;
  title: string;
  alignment: string;
  owner: Owner;
  rationale: string;
  boundary: string;
  factors: string[];
};

const scenario = {
  id: "labeler-roll-change-stability-v1",
  baseline: {
    speed: 78,
    presentationStdDevMs: 7.8,
    aligned: 5,
    skew: 0,
    maxOffsetMm: 0.7,
    confidence: 0.97,
  },
  concern: {
    speed: 78,
    presentationStdDevMs: 21.6,
    aligned: 3,
    skew: 2,
    maxOffsetMm: 2.9,
    confidence: 0.95,
  },
  verification: {
    runId: "SYN-L2-VERIFY-001",
    speed: 78,
    presentationStdDevMs: 18.9,
    aligned: 4,
    skew: 1,
    maxOffsetMm: 2.4,
    confidence: 0.96,
  },
} as const;

const rankedInterventions: RankedIntervention[] = [
  {
    id: "inspect-presentation-stability",
    rank: 1,
    title: "Inspect bottle presentation stability",
    alignment: "Highest evidence alignment",
    owner: "Maintenance",
    rationale: "The operator observation, elevated presentation variability, and remaining camera skew all point to the presentation relationship as the most useful place to localize next.",
    boundary: "Inspect and localize only. Any correction must come from commissioned procedure or qualified authority, then receive its own fresh bounded verification run.",
    factors: ["+ Operator observation supports", "+ Telemetry supports", "+ Camera supports", "0 Quality confirms persistence, not mechanism"],
  },
  {
    id: "repeat-like-for-like",
    rank: 2,
    title: "Repeat the same-condition verification run",
    alignment: "High information value · no material change",
    owner: "Shift supervisor",
    rationale: "The verification run improved slightly but still missed the synthetic baseline. Repeating the same conditions tests whether that improvement is repeatable before introducing another variable.",
    boundary: "No material intervention is introduced. The run still requires site authorization and the same controlled test conditions.",
    factors: ["+ Preserves one-variable discipline", "+ Tests repeatability", "+ Avoids premature adjustment", "0 Does not localize mechanism by itself"],
  },
  {
    id: "verify-guide-spacing",
    rank: 3,
    title: "Verify guide / spacing relationship",
    alignment: "Moderate evidence alignment",
    owner: "Maintenance",
    rationale: "Guide or spacing relationships could contribute to presentation instability, but the current evidence does not isolate either relationship.",
    boundary: "Verification is not permission to adjust. Any change requires commissioned procedure or qualified authority and a fresh trial.",
    factors: ["+ Compatible with presentation instability", "0 Not directly isolated", "0 No admitted guide-position evidence", "− Less supported than presentation-level inspection"],
  },
  {
    id: "request-reduced-speed-trial",
    rank: 4,
    title: "Request an authorized reduced-speed diagnostic trial",
    alignment: "Lower-ranked diagnostic intervention",
    owner: "Shift supervisor",
    rationale: "A rate-sensitivity test may add information, but line speed did not change when the synthetic concern appeared, so it ranks below presentation-focused options.",
    boundary: "This is a request for an authorized diagnostic trial, not an instruction to change speed.",
    factors: ["+ Could test rate sensitivity", "0 Requires a material change", "− Speed was unchanged across observed windows", "− Current evidence points elsewhere first"],
  },
  {
    id: "review-label-timing-geometry",
    rank: 5,
    title: "Review label timing / peel geometry evidence",
    alignment: "Currently deprioritized",
    owner: "Maintenance",
    rationale: "Current admitted evidence points more strongly toward presentation stability; nothing in this scenario currently elevates timing or peel geometry.",
    boundary: "Deprioritized does not mean healthy. Review does not authorize adjustment or establish root cause.",
    factors: ["0 No current timing evidence", "0 No current peel-geometry evidence", "− Presentation evidence is stronger", "− Do not infer healthy from lack of evidence"],
  },
];

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
  const [showInterventions, setShowInterventions] = useState(false);
  const [selectedInterventionId, setSelectedInterventionId] = useState<InterventionId | null>(null);

  const selected = assets.find((asset) => asset.id === selectedId) ?? assets[0];
  const activeCount = assets.filter((asset) => asset.concern).length;
  const posture = assets.some((asset) => asset.plan === "ADAPT") ? "ADAPTATION REQUIRED" : assets.some((asset) => asset.plan === "WATCH") ? "PLAN HOLDS · WATCHING" : "PLAN HOLDS";
  const selectedIntervention = rankedInterventions.find((item) => item.id === selectedInterventionId) ?? null;

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
      scenarioId: scenario.id,
      asset: "Labeler 2",
      requestedBy: owner,
      triggerObservation: observation,
      requestedRun: "5-container bounded verification trial · synthetic demo parameter",
      timestamp: new Date().toLocaleString(),
      runContext: "Awaiting admitted completed-run source",
      visualEvidence: "Awaiting admitted camera/classifier evidence",
      telemetryEvidence: "Awaiting synthetic telemetry source event",
      qualityEvidence: "Awaiting synthetic quality source event",
      comparison: "Awaiting verification-run evidence",
      boundedFinding: "No finding yet. The run evidence has not arrived.",
      provenance: [
        "Asset identity · Plant Canvas synthetic topology",
        "Scenario identity · Deterministic synthetic fixture",
        "Trigger observation · Operator supplied · unverified",
        "Trial request · Deterministic workflow rule",
        "Timestamp · Browser session",
      ],
      state: "AWAITING RUN EVIDENCE",
      review: "PENDING",
    });
    setShowInterventions(false);
    setSelectedInterventionId(null);
    setOperatorOpen(false);
  };

  const receiveSyntheticRunEvent = () => {
    const v = scenario.verification;
    setTrial((current) => current ? {
      ...current,
      runContext: `Synthetic MES event · ${v.runId} · ${v.speed} containers/min · 5 containers observed`,
      visualEvidence: `Synthetic camera · 4/5 within demo alignment envelope · 1 apparent skew · max |offset| ${v.maxOffsetMm.toFixed(1)} mm · classifier confidence ${(v.confidence * 100).toFixed(0)}%`,
      telemetryEvidence: `Synthetic telemetry · presentation-interval variability ${v.presentationStdDevMs.toFixed(1)} ms SD (baseline ${scenario.baseline.presentationStdDevMs.toFixed(1)} ms; concern window ${scenario.concern.presentationStdDevMs.toFixed(1)} ms)`,
      qualityEvidence: "Synthetic quality counter · 4 accepted · 1 apparent reject candidate",
      comparison: "Verification run is worse than the synthetic baseline, but slightly better than the immediately preceding concern window. Line speed is unchanged in all three windows.",
      boundedFinding: "Alignment inconsistency persists while presentation-interval variability remains elevated relative to the synthetic baseline. This supports continued attention to presentation stability; it does not establish root cause.",
      provenance: [
        ...current.provenance,
        "Run context · synthetic-mes/packaging-line-1",
        "Visual evidence · synthetic-camera/labeler2 · AI classification",
        "Telemetry evidence · synthetic-telemetry/labeler2 · deterministic fixture",
        "Quality evidence · synthetic-quality/labeler2",
        "Comparison · Deterministic rule over scenario windows",
      ],
      state: "READY FOR HUMAN REVIEW",
    } : current);
    setAssets((current) => current.map((asset) => asset.id === "labeler" ? { ...asset, next: "Review the auto-assembled synthetic evidence. Confirm, correct, or escalate; no causal conclusion has been established." } : asset));
  };

  const reviewTrial = (review: ReviewState) => {
    setTrial((current) => current ? { ...current, review } : current);
    if (review === "ACCEPTED") {
      setShowInterventions(true);
      setSelectedInterventionId(null);
      setAssets((current) => current.map((asset) => asset.id === "labeler" ? { ...asset, owner: "Shift supervisor", next: "Choose one evidence-ranked next option. Rank expresses evidence alignment and information value, not root-cause probability." } : asset));
    }
    if (review === "CORRECTION NEEDED") {
      setShowInterventions(false);
      setAssets((current) => current.map((asset) => asset.id === "labeler" ? { ...asset, next: "Correct the disputed field while preserving the original source value and provenance before selecting an intervention." } : asset));
    }
    if (review === "ESCALATED") {
      setShowInterventions(false);
      setAssets((current) => current.map((asset) => asset.id === "labeler" ? { ...asset, owner: "Maintenance", next: "Review the auto-assembled evidence package before any further intervention." } : asset));
    }
  };

  const chooseIntervention = (id: InterventionId) => {
    const option = rankedInterventions.find((item) => item.id === id);
    if (!option) return;
    setSelectedInterventionId(id);
    setAssets((current) => current.map((asset) => asset.id === "labeler" ? {
      ...asset,
      owner: option.owner,
      next: `${option.title} selected. Obtain required authorization, perform only that bounded option, then complete a fresh verification run before any other material change.`,
    } : asset));
  };

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>LINEALERT · PLANT CANVAS · SYNTHETIC DEMO</span>
          <h1>{posture}</h1>
          <p>Model the plant, locate the concern, assign one bounded action, run, let LineAlert assemble coordinated evidence, then rank the allowed next options for human selection.</p>
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
        <div><span>SCENARIO</span><b>{scenario.id} · deterministic synthetic fixture</b></div>
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
            <div className={styles.dependencyNote}>Process flow and numeric values are synthetic demo parameters, not commissioned plant truth or OEM operating limits. Relationship display does not prove causation.</div>
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
            <div><span>BOUNDED TRIAL · AUTO-ASSEMBLED RECORD</span><h2>{trial.id}</h2><small>Scenario {trial.scenarioId}</small></div>
            <b>{trial.review === "PENDING" ? trial.state : trial.review}</b>
          </div>
          <div className={styles.trialGrid}>
            <div><span>Asset</span><strong>{trial.asset}</strong><small>auto-populated · canvas context</small></div>
            <div><span>Requested by</span><strong>{trial.requestedBy}</strong><small>auto-populated · workflow owner</small></div>
            <div><span>Run</span><strong>{trial.requestedRun}</strong><small>workflow rule · not production authorization</small></div>
            <div><span>Timestamp</span><strong>{trial.timestamp}</strong><small>auto-populated · browser session</small></div>
          </div>
          <div className={styles.trialEvidence}>
            <div><span>Trigger observation</span><p>{trial.triggerObservation}</p></div>
            <div><span>Run / MES context</span><p>{trial.runContext}</p></div>
            <div><span>Visual evidence</span><p>{trial.visualEvidence}</p></div>
            <div><span>Quality evidence</span><p>{trial.qualityEvidence}</p></div>
            <div><span>Telemetry</span><p>{trial.telemetryEvidence}</p></div>
            <div><span>Like-for-like comparison</span><p>{trial.comparison}</p></div>
            <div><span>Bounded finding</span><p>{trial.boundedFinding}</p></div>
          </div>
          <div className={styles.provenance}><span>PROVENANCE</span>{trial.provenance.map((item) => <small key={item}>{item}</small>)}</div>
          {trial.state === "AWAITING RUN EVIDENCE" ? (
            <button className={styles.primaryAction} onClick={receiveSyntheticRunEvent}>Demo only · receive coordinated source events</button>
          ) : trial.review === "PENDING" ? (
            <div className={styles.reviewActions}>
              <button onClick={() => reviewTrial("ACCEPTED")}>Confirm record</button>
              <button onClick={() => reviewTrial("CORRECTION NEEDED")}>Correct something</button>
              <button onClick={() => reviewTrial("ESCALATED")}>Escalate</button>
            </div>
          ) : null}
          <small className={styles.operatorBoundary}>Synthetic MES, telemetry, camera, and quality outputs are coordinated by a deterministic demo fixture so the evidence behaves coherently. They are not measurements from a real machine, commissioned limits, root-cause proof, or authorization to run or change equipment.</small>
        </section>
      )}

      {showInterventions && trial?.review === "ACCEPTED" && (
        <section className={styles.interventionPanel} aria-label="Evidence-ranked next options">
          <div className={styles.interventionHeading}>
            <div><span>NEXT DECISION · HUMAN SELECTION</span><h2>Choose one bounded next option</h2></div>
            <b>RANKED BY EVIDENCE ALIGNMENT</b>
          </div>
          <p className={styles.rankBoundary}>Rank is deterministic evidence alignment and information value for this synthetic scenario. It is not root-cause probability, proof, authorization, or a safety determination.</p>
          <div className={styles.interventionList}>
            {rankedInterventions.map((option) => (
              <button key={option.id} className={`${styles.interventionOption} ${selectedInterventionId === option.id ? styles.interventionSelected : ""}`} onClick={() => chooseIntervention(option.id)}>
                <div className={styles.rankBadge}>{option.rank}</div>
                <div className={styles.interventionBody}>
                  <div className={styles.interventionTitle}><strong>{option.title}</strong><span>{option.alignment}</span></div>
                  <p>{option.rationale}</p>
                  <div className={styles.factorRow}>{option.factors.map((factor) => <small key={factor}>{factor}</small>)}</div>
                  <div className={styles.interventionMeta}><span>Owner: {option.owner}</span><span>Fresh bounded run required after any material change</span></div>
                </div>
              </button>
            ))}
          </div>
          {selectedIntervention && (
            <div className={styles.selectedDecision}>
              <span>SELECTED NEXT OPTION</span>
              <h3>#{selectedIntervention.rank} · {selectedIntervention.title}</h3>
              <p>{selectedIntervention.boundary}</p>
              <b>Selection records workflow intent only. It does not authorize the intervention or execute a machine change.</b>
            </div>
          )}
        </section>
      )}

      <section className={styles.boundary}><div><span>V1 BOUNDARY</span><b>Evidence → ranked allowed options → human selects → authorize elsewhere → one bounded action → fresh run.</b></div><p>No live telemetry, camera, PLC/controller, MES, quality system, CMMS, dispatch, safety-control or equipment-control connection is added here. Rank ≠ diagnosis. Selection ≠ authorization. Successful or improved synthetic evidence ≠ root-cause proof or a safe production change.</p></section>
    </main>
  );
}
