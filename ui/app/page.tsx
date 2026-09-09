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
type InterventionId = "inspect-presentation-stability" | "verify-guide-spacing" | "repeat-like-for-like" | "request-reduced-speed-trial" | "review-label-timing-geometry";
type AuthorizationClass = "standing_operator_authority" | "shift_supervisor_run_release_required" | "shift_supervisor_approval_required" | "maintenance_scope_only";

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
  rationale: string;
  historicalSupport: string;
  boundary: string;
  factors: string[];
  eligibleRoles: Owner[];
  authorization: AuthorizationClass;
  changeClass: string;
  operatorScope: string;
};

const scenario = {
  id: "labeler-roll-change-stability-v1",
  baseline: { speed: 78, presentationStdDevMs: 7.8 },
  concern: { speed: 78, presentationStdDevMs: 21.6 },
  verification: { runId: "SYN-L2-VERIFY-001", speed: 78, presentationStdDevMs: 18.9, maxOffsetMm: 2.4, confidence: 0.96 },
} as const;

const cmmsHistory = {
  source: "synthetic-cmms/labeler2",
  historyId: "labeler2-maintenance-history-v1",
  similarClosedCases: 4,
  presentationLocalizations: 4,
  guidePresentationCorrections: 3,
  timingChanges: 0,
  cases: [
    "WO-SYN-1842 · intermittent skew after format change → verified presentation instability → approved guide correction → bounded verification",
    "WO-SYN-2197 · alignment drift → guide relationship out of approved setup → approved setup restored → documented no recurrence window",
    "WO-SYN-2644 · skew at normal speed → degraded presentation stability → worn presentation component corrected → returned to synthetic baseline pattern",
    "WO-SYN-2811 · alignment complaint after roll change → no timing fault established → approved presentation setup restored → two clean verification runs",
  ],
} as const;

const authorityProfile = {
  id: "synthetic-labeler2-action-authority-v1",
  currentActor: "Operator" as Owner,
  rule: "Evidence ranks useful actions. This plant's commissioned authority decides who may perform each action and under what conditions.",
} as const;

const rankedInterventions: RankedIntervention[] = [
  {
    id: "inspect-presentation-stability",
    rank: 1,
    title: "Inspect bottle presentation stability",
    alignment: "Highest current + historical support",
    rationale: "Current operator, telemetry, camera, and quality evidence converges on the presentation relationship, and four similar well-documented CMMS cases on this synthetic asset localized there.",
    historicalSupport: "Strong · 4/4 similar synthetic CMMS cases localized to presentation relationships.",
    boundary: "Observe and localize only. Historical recurrence is not proof of the current cause.",
    factors: ["+ Current operator evidence", "+ Current telemetry", "+ Current camera", "+ CMMS 4/4 similar cases"],
    eligibleRoles: ["Operator", "Maintenance"],
    authorization: "standing_operator_authority",
    changeClass: "Observation only",
    operatorScope: "Operator may inspect presentation stability from the approved operating position and record the result.",
  },
  {
    id: "verify-guide-spacing",
    rank: 2,
    title: "Verify guide / spacing relationship",
    alignment: "High historical support",
    rationale: "Current evidence does not directly isolate guide position, but three similar CMMS cases document approved guide/presentation correction after comparable symptoms.",
    historicalSupport: "Strong · 3 similar synthetic cases involved guide/presentation correction.",
    boundary: "Verification is not permission to adjust. If the reference is not met, LineAlert reranks before any correction.",
    factors: ["+ CMMS 3 similar corrections", "+ Compatible with current presentation evidence", "0 Guide position not currently measured"],
    eligibleRoles: ["Operator", "Maintenance"],
    authorization: "standing_operator_authority",
    changeClass: "Verification only",
    operatorScope: "Operator may compare the visible guide / spacing relationship with the commissioned marked or visual reference. No adjustment is included in this action.",
  },
  {
    id: "repeat-like-for-like",
    rank: 3,
    title: "Repeat the same-condition verification run",
    alignment: "High information value",
    rationale: "A repeat without material change still adds useful repeatability evidence, but the strong maintained CMMS history makes presentation-focused localization more informative first.",
    historicalSupport: "Neutral · history favors localization but does not remove the value of repeatability evidence.",
    boundary: "No material intervention is introduced. The run still requires the plant's run-release authority.",
    factors: ["+ Preserves one-variable discipline", "+ Tests repeatability", "0 History favors localization first"],
    eligibleRoles: ["Operator", "Shift supervisor"],
    authorization: "shift_supervisor_run_release_required",
    changeClass: "Controlled run · no material change",
    operatorScope: "Operator may execute the same-condition bounded run after the shift supervisor releases the trial conditions.",
  },
  {
    id: "request-reduced-speed-trial",
    rank: 4,
    title: "Run an approved reduced-speed diagnostic trial",
    alignment: "Lower-ranked diagnostic test",
    rationale: "A rate-sensitivity test may add information, but speed did not change when the concern appeared and three similar historical cases occurred at normal line speed.",
    historicalSupport: "Weakens rank · 3 similar synthetic cases occurred at normal line speed.",
    boundary: "The operator may execute this only after supervisor approval and only within the commissioned temporary diagnostic envelope. The demo defines no real speed value.",
    factors: ["+ Could test rate sensitivity", "− Current speed unchanged", "− CMMS 3 similar cases at normal speed"],
    eligibleRoles: ["Operator", "Shift supervisor"],
    authorization: "shift_supervisor_approval_required",
    changeClass: "Bounded material change",
    operatorScope: "Operator may apply the commissioned temporary diagnostic speed after supervisor approval, then a fresh verification run is mandatory.",
  },
  {
    id: "review-label-timing-geometry",
    rank: 5,
    title: "Review label timing / peel geometry evidence",
    alignment: "Deprioritized by current + historical evidence",
    rationale: "Current evidence points more strongly toward presentation stability, and none of the four similar synthetic CMMS cases required a timing change.",
    historicalSupport: "Deprioritizing · 0/4 similar synthetic cases required timing change.",
    boundary: "Maintenance-only in this synthetic plant. Deprioritized does not mean healthy and review does not authorize adjustment.",
    factors: ["0 No current timing evidence", "− CMMS 0/4 timing changes", "− Presentation evidence stronger"],
    eligibleRoles: ["Maintenance"],
    authorization: "maintenance_scope_only",
    changeClass: "Specialist investigation",
    operatorScope: "Not operator-authorized in this synthetic plant.",
  },
];

const seedAssets: Asset[] = [
  { id: "filler", name: "Filler 1", role: "Upstream process", plan: "HOLDS", owner: "Shift supervisor", next: "No action requested." },
  { id: "labeler", name: "Labeler 2", role: "Application process", plan: "WATCH", owner: "Shift supervisor", next: "Assign one bounded action if it is commissioned for the current role and state.", concern: "Operator reports label alignment is off after a roll change.", runway: "~70 min", responseEta: "32 min" },
  { id: "packer", name: "Case Packer 1", role: "Downstream dependency", plan: "HOLDS", owner: "Shift supervisor", next: "No action requested." },
  { id: "palletizer", name: "Palletizer 1", role: "Downstream process", plan: "HOLDS", owner: "Shift supervisor", next: "No action requested." },
];

function authorizationText(option: RankedIntervention) {
  if (option.authorization === "standing_operator_authority") return "AVAILABLE TO OPERATOR · standing commissioned authority";
  if (option.authorization === "shift_supervisor_run_release_required") return "OPERATOR MAY EXECUTE · supervisor run release required";
  if (option.authorization === "shift_supervisor_approval_required") return "OPERATOR MAY EXECUTE · supervisor approval required";
  return "ROUTE TO MAINTENANCE · not operator-authorized here";
}

function nextOwner(option: RankedIntervention): Owner {
  if (option.authorization === "standing_operator_authority") return "Operator";
  if (option.authorization === "maintenance_scope_only") return "Maintenance";
  return "Shift supervisor";
}

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
    setAssets((current) => current.map((asset) => asset.id === "labeler" ? { ...asset, owner: "Operator", next: "Perform the commissioned visible-condition check from the approved operating position." } : asset));
    setSelectedId("labeler");
    setOperatorOpen(true);
  };

  const recordResult = (result: OperatorResult) => {
    const observation = result === "appears_clear"
      ? "Operator reports the visible application relationship appears aligned."
      : result === "issue_observed"
        ? "Operator reports the visible application relationship appears out of alignment."
        : "Operator could not verify the visible application relationship safely.";
    const owner: Owner = result === "cannot_verify" ? "Maintenance" : "Shift supervisor";
    const next = result === "cannot_verify"
      ? "Route to Maintenance because the operator could not safely complete the commissioned observation."
      : "Await the approved bounded run. LineAlert will assemble admitted evidence automatically when the completed-run event arrives.";

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
        "Scenario identity · deterministic synthetic fixture",
        "Trigger observation · operator supplied · unverified",
        "Trial request · deterministic workflow rule",
        "Authority context · synthetic-labeler2-action-authority-v1",
        "Timestamp · browser session",
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
      comparison: "Verification remains worse than the synthetic baseline but slightly better than the preceding concern window. Line speed is unchanged.",
      boundedFinding: "Alignment inconsistency persists while presentation variability remains elevated. Strong similar CMMS history supports presentation-focused localization; current root cause remains unestablished.",
      provenance: [
        ...current.provenance,
        "Run context · synthetic-mes/packaging-line-1",
        "Visual evidence · synthetic-camera/labeler2 · AI classification",
        "Telemetry evidence · synthetic-telemetry/labeler2 · deterministic fixture",
        "Quality evidence · synthetic-quality/labeler2",
        `Historical evidence · ${cmmsHistory.source} · excellent maintained synthetic fixture`,
        "Comparison and ranking inputs · deterministic rules over current + historical evidence",
      ],
      state: "READY FOR HUMAN REVIEW",
    } : current);
    setAssets((current) => current.map((asset) => asset.id === "labeler" ? { ...asset, next: "Review the auto-assembled current evidence and strong synthetic CMMS history. Confirm, correct, or escalate." } : asset));
  };

  const reviewTrial = (review: ReviewState) => {
    setTrial((current) => current ? { ...current, review } : current);
    if (review === "ACCEPTED") {
      setShowInterventions(true);
      setSelectedInterventionId(null);
      setAssets((current) => current.map((asset) => asset.id === "labeler" ? { ...asset, owner: authorityProfile.currentActor, next: "Choose the highest-value commissioned action you are permitted to take here; LineAlert routes any gated or specialist action to the required authority." } : asset));
    }
    if (review === "CORRECTION NEEDED") {
      setShowInterventions(false);
      setAssets((current) => current.map((asset) => asset.id === "labeler" ? { ...asset, next: "Correct the disputed field while preserving the original source value and provenance before selecting an action." } : asset));
    }
    if (review === "ESCALATED") {
      setShowInterventions(false);
      setAssets((current) => current.map((asset) => asset.id === "labeler" ? { ...asset, owner: "Maintenance", next: "Review the current and historical evidence package before any further action." } : asset));
    }
  };

  const chooseIntervention = (id: InterventionId) => {
    const option = rankedInterventions.find((item) => item.id === id);
    if (!option) return;
    const owner = nextOwner(option);
    const next = option.authorization === "standing_operator_authority"
      ? `${option.title} selected. Operator may perform this commissioned action now within the displayed scope. Record the result; rerank before any additional material change.`
      : option.authorization === "maintenance_scope_only"
        ? `${option.title} selected. Route to Maintenance; this action is outside operator authority in this synthetic plant.`
        : `${option.title} selected. Route to Shift supervisor for the required authorization; the operator may execute after approval within the commissioned scope.`;
    setSelectedInterventionId(id);
    setAssets((current) => current.map((asset) => asset.id === "labeler" ? { ...asset, owner, next } : asset));
  };

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>LINEALERT · PLANT CANVAS · SYNTHETIC DEMO</span>
          <h1>{posture}</h1>
          <p>Evidence ranks the useful next actions. Plant-specific commissioned authority determines which role may perform each action, under what conditions, and whether approval is required.</p>
          <p><small>Design assumption: synthetic CMMS history is excellent. Authority assumption: permissions are plant-specific and commissioned by asset + action + state. Historical pattern ≠ current root cause. Recommendation ≠ authorized action.</small></p>
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
        <div><span>CURRENT ROLE</span><b>{authorityProfile.currentActor}</b></div>
        <div><span>AUTHORITY PROFILE</span><b>{authorityProfile.id}</b></div>
      </section>

      {view === "canvas" ? (
        <section className={styles.canvasLayout}>
          <section className={styles.canvas} aria-label="Synthetic packaging line topology">
            <div className={styles.canvasHeader}><div><span>PACKAGING LINE 1</span><h2>Plant model</h2></div><small>Synthetic topology · browser-session workflow state</small></div>
            <div className={styles.flow}>{assets.map((asset, index) => <div className={styles.flowItem} key={asset.id}><button className={`${styles.assetNode} ${styles[asset.plan.toLowerCase()]} ${selectedId === asset.id ? styles.selected : ""}`} onClick={() => setSelectedId(asset.id)}><span>{asset.role}</span><b>{asset.name}</b><small>{asset.concern ? asset.owner : "Stable"}</small></button>{index < assets.length - 1 && <div className={styles.connector} aria-hidden="true">→</div>}</div>)}</div>
            <div className={styles.dependencyNote}>Process flow, authority assignments, and numeric values are synthetic demo parameters. Relationship display does not prove causation.</div>
          </section>
          <aside className={styles.assetPanel}>
            <span className={styles.sectionLabel}>ASSET</span><h2>{selected.name}</h2><p className={styles.assetRole}>{selected.role}</p>
            <dl><div><dt>Posture</dt><dd>{selected.plan}</dd></div><div><dt>Workflow owner</dt><dd>{selected.owner}</dd></div>{selected.runway && <div><dt>Runway</dt><dd>{selected.runway}</dd></div>}{selected.responseEta && <div><dt>Response ETA</dt><dd>{selected.responseEta}</dd></div>}</dl>
            {selected.concern ? <div className={styles.concern}><span>CURRENT CONCERN</span><p>{selected.concern}</p></div> : <div className={styles.quiet}>No active concern on this synthetic asset.</div>}
            {selected.latestObservation && <div className={styles.observationNote}><span>LATEST OBSERVATION</span><p>{selected.latestObservation}</p></div>}
            <div className={styles.nextStep}><span>NEXT</span><p>{selected.next}</p></div>
            {selected.id === "labeler" && selected.owner === "Shift supervisor" && !trial && <button className={styles.primaryAction} onClick={assignOperator}>Assign operator-authorized check</button>}
            {selected.id === "labeler" && selected.owner === "Operator" && !showInterventions && <button className={styles.primaryAction} onClick={() => setOperatorOpen(true)}>Open operator action</button>}
          </aside>
        </section>
      ) : <section className={styles.boardView}>{Object.entries(boardGroups).map(([stage, items]) => <section className={styles.boardColumn} key={stage}><header><span>{stage}</span><b>{items.length}</b></header>{items.length ? items.map((asset) => <button key={asset.id} onClick={() => { setSelectedId(asset.id); setView("canvas"); }}><strong>{asset.name}</strong><span>{asset.owner}</span><small>{asset.next}</small></button>) : <div className={styles.empty}>Nothing waiting here.</div>}</section>)}</section>}

      {operatorOpen && <section className={styles.operatorTask}><div className={styles.operatorTaskHeading}><div><span>OPERATOR · COMMISSIONED ACTION</span><small>Labeler 2 · standing operator authority</small></div><button onClick={() => setOperatorOpen(false)}>Close</button></div><h2>From the approved operating position, does the visible label application relationship appear aligned?</h2><p><b>Authority:</b> This synthetic plant commissions this observation to the operator role. Another plant could assign the same action differently.</p><div className={styles.operatorAnswers}><button onClick={() => recordResult("appears_clear")}>Appears aligned</button><button onClick={() => recordResult("issue_observed")}>Appears out of alignment</button><button onClick={() => recordResult("cannot_verify")}>Can’t verify safely</button></div><small className={styles.operatorBoundary}>Standing authority applies only to this commissioned action, asset, state, and scope. It is not unrestricted operator discretion.</small></section>}

      {trial && <section className={styles.trialCard} aria-label="Bounded verification trial"><div className={styles.trialHeading}><div><span>BOUNDED TRIAL · AUTO-ASSEMBLED RECORD</span><h2>{trial.id}</h2><small>Scenario {trial.scenarioId}</small></div><b>{trial.review === "PENDING" ? trial.state : trial.review}</b></div><div className={styles.trialGrid}><div><span>Asset</span><strong>{trial.asset}</strong><small>canvas context</small></div><div><span>Requested by</span><strong>{trial.requestedBy}</strong><small>workflow owner</small></div><div><span>Run</span><strong>{trial.requestedRun}</strong><small>not production authorization</small></div><div><span>Timestamp</span><strong>{trial.timestamp}</strong><small>browser session</small></div></div><div className={styles.trialEvidence}><div><span>Trigger observation</span><p>{trial.triggerObservation}</p></div><div><span>Run / MES context</span><p>{trial.runContext}</p></div><div><span>Visual evidence</span><p>{trial.visualEvidence}</p></div><div><span>Quality evidence</span><p>{trial.qualityEvidence}</p></div><div><span>Telemetry</span><p>{trial.telemetryEvidence}</p></div><div><span>Like-for-like comparison</span><p>{trial.comparison}</p></div><div><span>Bounded finding</span><p>{trial.boundedFinding}</p></div></div><div className={styles.provenance}><span>PROVENANCE</span>{trial.provenance.map((item) => <small key={item}>{item}</small>)}</div>{trial.state === "AWAITING RUN EVIDENCE" ? <button className={styles.primaryAction} onClick={receiveSyntheticRunEvent}>Demo only · receive coordinated source events</button> : trial.review === "PENDING" ? <div className={styles.reviewActions}><button onClick={() => reviewTrial("ACCEPTED")}>Confirm record</button><button onClick={() => reviewTrial("CORRECTION NEEDED")}>Correct something</button><button onClick={() => reviewTrial("ESCALATED")}>Escalate</button></div> : null}<small className={styles.operatorBoundary}>Current evidence and maintenance history are evidence inputs. Authority is evaluated separately from ranking.</small></section>}

      {showInterventions && trial?.review === "ACCEPTED" && <>
        <section className={styles.trialCard} aria-label="Synthetic CMMS history"><div className={styles.trialHeading}><div><span>MAINTENANCE HISTORY · SYNTHETIC CMMS</span><h2>Strong similar-case history</h2><small>{cmmsHistory.historyId}</small></div><b>EXCELLENT DATA ASSUMPTION</b></div><div className={styles.trialGrid}><div><span>Similar closed cases</span><strong>{cmmsHistory.similarClosedCases}</strong><small>well documented and correctly asset-linked</small></div><div><span>Presentation related</span><strong>{cmmsHistory.presentationLocalizations} / {cmmsHistory.similarClosedCases}</strong><small>verified historical localization</small></div><div><span>Guide / presentation corrections</span><strong>{cmmsHistory.guidePresentationCorrections}</strong><small>approved historical interventions</small></div><div><span>Timing changes</span><strong>{cmmsHistory.timingChanges}</strong><small>historical absence lowers rank; it does not prove timing healthy</small></div></div><div className={styles.trialEvidence}>{cmmsHistory.cases.map((historyCase) => <div key={historyCase}><span>HISTORICAL CASE</span><p>{historyCase}</p></div>)}</div><small className={styles.operatorBoundary}>Historical pattern ≠ current root cause.</small></section>

        <section className={styles.interventionPanel} aria-label="Evidence-ranked action options"><div className={styles.interventionHeading}><div><span>NEXT DECISION · CURRENT ROLE: {authorityProfile.currentActor.toUpperCase()}</span><h2>Choose one evidence-ranked commissioned action</h2></div><b>RANK FIRST · AUTHORITY SECOND</b></div><p className={styles.rankBoundary}>{authorityProfile.rule} Rank is not root-cause probability, and role eligibility alone is not authorization.</p><div className={styles.interventionList}>{rankedInterventions.map((option) => <button key={option.id} className={`${styles.interventionOption} ${selectedInterventionId === option.id ? styles.interventionSelected : ""}`} onClick={() => chooseIntervention(option.id)}><div className={styles.rankBadge}>{option.rank}</div><div className={styles.interventionBody}><div className={styles.interventionTitle}><strong>{option.title}</strong><span>{option.alignment}</span></div><p>{option.rationale}</p><p><b>Historical support:</b> {option.historicalSupport}</p><div className={styles.factorRow}>{option.factors.map((factor) => <small key={factor}>{factor}</small>)}</div><div className={styles.factorRow}><small>{authorizationText(option)}</small><small>{option.changeClass}</small><small>Eligible: {option.eligibleRoles.join(" / ")}</small></div><p><b>Operator scope here:</b> {option.operatorScope}</p></div></button>)}</div>{selectedIntervention && <div className={styles.selectedDecision}><span>SELECTED NEXT ACTION</span><h3>#{selectedIntervention.rank} · {selectedIntervention.title}</h3><p>{selectedIntervention.boundary}</p><p><b>{authorizationText(selectedIntervention)}</b></p><b>Selection records workflow intent. Execution is allowed only when the commissioned authority condition is satisfied.</b></div>}</section>
      </>}

      <section className={styles.boundary}><div><span>V1 BOUNDARY</span><b>Evidence ranks actions → plant authority filters/routes them → authorized person performs one bounded action → fresh evidence → rerank.</b></div><p>No live telemetry, camera, PLC/controller, MES, quality system, CMMS, dispatch, safety-control or equipment-control connection is added here. Operator-authorized action ≠ universal operator authority. Recommendation ≠ authorized action. Historical pattern ≠ current root cause.</p></section>
    </main>
  );
}
