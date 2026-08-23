"use client";

import { useEffect, useState } from "react";

type Stage = "detected" | "inspection" | "guided" | "changed" | "validated" | "released";
type FaultKey = "alignment" | "folds" | "stretch" | "bubbles" | "multiple";
type Role = "operator" | "senior-operator" | "millwright" | "maintenance" | "technician" | "qa" | "engineering" | "plant-manager";
type Language = "EN" | "ES";
type ResponseMode = "automatic" | "confirm" | "guided" | "escalate";
type EvidenceSignal = { value:number | null; unit:string; quality:string; reason_code:string; provenance?:string; age_ms?:number };
type TelemetrySnapshot = { connected:boolean; source_id:string; asset_id:string; read_only:boolean; reason_code:string; proxy_warning?:string; observation_sequence?:number; bridge_timestamp?:string; signals:Record<string,EvidenceSignal> };

const rolePacks: Record<Role, { label:string; short:string; icon:string; headline:string; focus:string; contribution:string; authority:string; handoff:string; learns:string }> = {
  operator: { label:"Operator", short:"OPS", icon:"◎", headline:"One clear move. Five fresh bottles.", focus:"Safe recovery · current bottle outcome", contribution:"Physical nuance and current-event confirmation", authority:"Within operator scope", handoff:"Maintenance receives the symptom, checks and fresh outcomes—not a vague call.", learns:"Recognize when a pattern needs maintenance without taking maintenance authority." },
  "senior-operator": { label:"Senior operator", short:"SR OPS", icon:"◇", headline:"Recover the line—and preserve what the team learned.", focus:"Pattern comparison · coaching · validated overrides", contribution:"Experienced process judgment and shift-to-shift learning", authority:"Senior operator scope", handoff:"Validated field reasoning becomes reusable guidance for operators and maintenance.", learns:"See how maintenance and engineering evidence qualifies a familiar operating pattern." },
  millwright: { label:"Millwright", short:"MW", icon:"⚙", headline:"Localize the mechanical relationship before adjustment.", focus:"Contact · alignment · wear · load · motion", contribution:"Mechanical condition and physical-coupling evidence", authority:"Qualified mechanical scope", handoff:"Mechanical findings reach controls and engineering with test conditions intact.", learns:"Connect operator-observed behaviour with controller timing and product outcomes." },
  maintenance: { label:"Maintenance", short:"MAINT", icon:"◆", headline:"Machine relationships, work history and recovery evidence.", focus:"Fault domain · work history · bounded testing", contribution:"Repair context, intervention history and verification", authority:"Maintenance access", handoff:"Operators receive the verified recovery state; engineering receives recurring evidence.", learns:"Use frontline observations and QA outcomes to prioritize the next physical check." },
  technician: { label:"Controls technician", short:"TECH", icon:"⌁", headline:"Compare controller intent with physical response.", focus:"PLC sequence · I/O · drives · timing · networks", contribution:"Controller, electrical and communications evidence", authority:"Qualified technical scope", handoff:"Control-state evidence is translated into physical and product consequences.", learns:"See where operator and millwright evidence contradicts the controller’s reported state." },
  qa: { label:"Quality", short:"QA", icon:"✓", headline:"Connect machine events to verified product outcomes.", focus:"Defect pattern · sampling · traceability · release", contribution:"Inspection results and product-disposition evidence", authority:"Quality review scope", handoff:"Verified defects and accepted outcomes close the recovery evidence loop.", learns:"Relate defect patterns to machine timing, interventions and commissioned limits." },
  engineering: { label:"Engineering", short:"ENG", icon:"△", headline:"Improve the model without overstating the evidence.", focus:"Baselines · envelopes · experiments · model revisions", contribution:"Commissioned limits and approved model changes", authority:"Engineering review scope", handoff:"Approved model changes return to every pack with their evidence and limits.", learns:"Use field nuance, maintenance findings and QA outcomes to refine the system model." },
  "plant-manager": { label:"Plant manager", short:"MGR", icon:"↗", headline:"See the impact. Route the expertise. Keep the evidence chain intact.", focus:"Impact · progress · ownership · expert routing", contribution:"Priority, staffing and cross-functional coordination", authority:"Coordination and priority only", handoff:"The selected expert receives the current evidence package and decision boundary.", learns:"See how far the investigation has progressed without diagnosing the machine." },
};

const scenarios = {
  alignment: { short:"Arrival phase drift", symbol:"⏱", drift:"→ LATE", title:"Label alignment is off", injection:"Merge arrival phase late", observed:"Placement drift · 4.2 mm late", count:"4 of last 5 bottles outside visual tolerance", keyPoint:"Bottle arrival phase moved late after the merge. Feed-to-wrapper speed ratio and applicator pressure remain inside their commissioned envelopes.", bestMove:"Inspect Lane B release and merge spacing first", spanishMove:"Inspeccione primero la liberación del carril B y el espaciado", maintenanceMove:"Review Lane B release against the merge arrival window", checks:["Lane B release consistent?","Merge spacing inside window?","Bottle stable at wrapper entry?","Feed ratio still coordinated?"], actions:["Inspect Lane B release","Review merge spacing","Confirm wrapper entry sensor","Leave stable feed speed unchanged"], parameter:"Lane B release delay", path:"Product Handling → Lane B → Release Delay", direction:"Reduce one authorized increment", oldValue:"145 ms", newValue:"125 ms" },
  folds: { short:"Folded edge", symbol:"↻", drift:"SLIP HIGH", title:"Label has folds", injection:"Bottle surface slip", observed:"Folded edge · right side", count:"3 of last 5 bottles show folds", keyPoint:"Camera contact velocity and the drive encoder show bottle-surface slip outside its commissioned envelope.", bestMove:"Inspect belt contact before changing speed", spanishMove:"Inspeccione el contacto de la correa antes de cambiar la velocidad", maintenanceMove:"Verify wrap-belt coupling and rotational slip", checks:["Contact pressure in range?","Belt clean and unworn?","Slip equal on both sides?","Does one bounded contact change restore coupling?"], actions:["Inspect belt pressure","Inspect belt condition","Compare left/right contact","Run bounded contact check"], parameter:"Aligner speed", path:"Label Setup → Handling → Aligner Speed", direction:"Increase one OEM-approved step", oldValue:"118 RPM", newValue:"124 RPM" },
  stretch: { short:"Stretch lines", symbol:"⇆", drift:"↑ HIGH", title:"Label has stretch lines", injection:"Excessive web tension", observed:"Tension lines · 3 detected", count:"5 of last 5 labels show distortion", keyPoint:"Web tension is elevated and matches the repeated stretch pattern.", bestMove:"Decrease web tension one approved step", spanishMove:"Reduzca un paso la tensión de la banda", maintenanceMove:"Inspect feed rollers for unequal pull", checks:["Label tension too high?","Worse at higher speed?","Feed rollers pulling evenly?"], actions:["Decrease label speed","Inspect feed rollers","Verify web tension","Compare against recipe baseline"], parameter:"Web tension", path:"Label Setup → Web → Web Tension", direction:"Decrease one OEM-approved step", oldValue:"4.8 N", newValue:"3.2 N" },
  bubbles: { short:"Air bubbles", symbol:"⇥", drift:"↓ LOW", title:"Bubbles on labels", injection:"Low contact pressure", observed:"Air pockets · 4 detected", count:"4 of last 5 labels show bubbles", keyPoint:"Application pressure is below its commissioned envelope.", bestMove:"Increase applicator pressure to 45 psi", spanishMove:"Aumente la presión del aplicador a 45 psi", maintenanceMove:"Inspect regulator stability and wipe contact", checks:["Enough pressure time?","Bottle stable?","Contact pressure consistent?","Does slowing help?"], actions:["Increase aligner run-on","Review bottle pressure","Decrease label speed","Inspect wipe pressure"], parameter:"Applicator pressure", path:"Label Setup → Applicator → Pressure", direction:"Increase within 40–50 psi", oldValue:"32 psi", newValue:"45 psi" },
  multiple: { short:"Overlapping labels", symbol:"◉", drift:"↻ RETRIGGER", title:"Multiple labels applying", injection:"Gap-sensor retrigger", observed:"Overlapping labels · 2 detected", count:"2 double-label events in last 5 bottles", keyPoint:"S3 is retriggering. This condition requires local inspection.", bestMove:"Inspect S3 sensor and escalate if contaminated", spanishMove:"Inspeccione el sensor S3 y escale si está contaminado", maintenanceMove:"Clean, align and recalibrate S3 locally", checks:["Sensor detecting gaps?","Label spacing consistent?","Intermittent or repeatable?","Speed-specific pattern?"], actions:["Inspect sensor cleanliness","Review sensor sensitivity","Verify sensor position","Inspect feed timing"], parameter:"Gap sensor sensitivity", path:"Label Setup → Sensors → Gap Sensitivity", direction:"Review and recalibrate locally", oldValue:"72 %", newValue:"64 %" },
} satisfies Record<FaultKey, { short:string; symbol:string; drift:string; title:string; injection:string; observed:string; count:string; keyPoint:string; bestMove:string; spanishMove:string; maintenanceMove:string; checks:string[]; actions:string[]; parameter:string; path:string; direction:string; oldValue:string; newValue:string }>;

const automaticVisionResult = (fault: FaultKey): { findings:Record<string,string>; points:string[] } => fault === "alignment"
  ? { findings:{"Lane B release":"Bottle enters the gap late", "Guide path":"No visible contact or drag", "Merge sensor":"Detection appears synchronized"}, points:["Lane B release", "Guide path", "Merge sensor"] }
  : { findings:{"Product path":"Path appears clear", "Active component":"Motion appears repeatable", "Sensor condition":"Indication appears repeatable"}, points:["Product path", "Active component", "Sensor condition"] };

export default function Home() {
  const [stage, setStage] = useState<Stage>("detected");
  const [clock, setClock] = useState("14:32:08");
  const [cycles, setCycles] = useState(0);
  const [signalTick, setSignalTick] = useState(0);
  const [bottleCount, setBottleCount] = useState(1842);
  const [activeFault, setActiveFault] = useState<FaultKey>("alignment");
  const [role, setRole] = useState<Role>("operator");
  const [routeTarget, setRouteTarget] = useState("");
  const [assignedTo, setAssignedTo] = useState("");
  const [language, setLanguage] = useState<Language>("EN");
  const [showWhy, setShowWhy] = useState(false);
  const [reasonDepth, setReasonDepth] = useState(0);
  const [academyInterest, setAcademyInterest] = useState(false);
  const [showMachineFlow, setShowMachineFlow] = useState(false);
  const [flowFocus, setFlowFocus] = useState<"process" | "aligner">("process");
  const [inspectionNote, setInspectionNote] = useState("");
  const [targetSetpointRecorded, setTargetSetpointRecorded] = useState(false);
  const [reviewedOemFields, setReviewedOemFields] = useState<string[]>([]);
  const [openOemField, setOpenOemField] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [showParameterHistory, setShowParameterHistory] = useState(false);
  const [virtualInspected, setVirtualInspected] = useState<string[]>(() => automaticVisionResult("alignment").points);
  const [activeInspectionPoint, setActiveInspectionPoint] = useState<string | null>(null);
  const [inspectionFindings, setInspectionFindings] = useState<Record<string,string>>(() => automaticVisionResult("alignment").findings);
  const [fastLaneAccepted, setFastLaneAccepted] = useState(false);
  const [visionSorted, setVisionSorted] = useState(true);
  const [telemetry, setTelemetry] = useState<TelemetrySnapshot | null>(null);
  const [telemetryReachable, setTelemetryReachable] = useState(false);
  const [showEvidenceConsole, setShowEvidenceConsole] = useState(true);

  useEffect(() => {
    const timer = setInterval(() => setClock(new Date().toLocaleTimeString("en-CA", { hour12: false })), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const signalTimer = setInterval(() => setSignalTick((value) => value + 1), 250);
    const bottleTimer = setInterval(() => setBottleCount((value) => value + 1), 1800);
    return () => { clearInterval(signalTimer); clearInterval(bottleTimer); };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || !["localhost", "127.0.0.1"].includes(window.location.hostname)) return;
    let active = true;
    const readTelemetry = async () => {
      try {
        const response = await fetch("/api/telemetry", { cache:"no-store" });
        if (!response.ok) throw new Error("bridge unavailable");
        const payload = await response.json() as TelemetrySnapshot;
        if (active) { setTelemetry(payload); setTelemetryReachable(true); }
      } catch {
        if (active) setTelemetryReachable(false);
      }
    };
    readTelemetry();
    const timer = setInterval(readTelemetry, 1000);
    return () => { active = false; clearInterval(timer); };
  }, []);

  useEffect(() => {
    if (stage !== "changed" || cycles >= 5) return;
    const timer = setTimeout(() => setCycles((value) => value + 1), 650);
    return () => clearTimeout(timer);
  }, [stage, cycles]);

  useEffect(() => {
    if (stage === "changed" && cycles === 5) {
      const timer = setTimeout(() => setStage("validated"), 450);
      return () => clearTimeout(timer);
    }
  }, [stage, cycles]);

  useEffect(() => {
    if (!showMachineFlow) return;
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setShowMachineFlow(false); };
    document.addEventListener("keydown", closeOnEscape);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      document.body.style.overflow = previousOverflow;
    };
  }, [showMachineFlow]);

  const advance = () => {
    if (stage === "detected") {
      setReviewedOemFields(requiredOemFields);
      setOpenOemField(null);
      setStage("guided");
    }
    if (stage === "inspection" && virtualInspectionComplete) {
      setReviewedOemFields(requiredOemFields);
      setOpenOemField(null);
      setStage("guided");
    }
    if (stage === "validated") setStage("released");
    if (stage === "released") { const result = automaticVisionResult(activeFault); setCycles(0); setStage("detected"); setInspectionNote(""); setTargetSetpointRecorded(false); setReviewedOemFields([]); setOpenOemField(null); setVirtualInspected(result.points); setActiveInspectionPoint(null); setInspectionFindings(result.findings); setVisionSorted(true); }
  };

  const scenario = scenarios[activeFault];
  const rolePack = rolePacks[role];
  const liveRpm = telemetry?.signals?.rpm?.value ?? 111.4 + Math.sin(signalTick / 7) * .7;
  const livePressure = telemetry?.signals?.pressure_psi?.value ?? 32.2 + Math.sin(signalTick / 10) * .25;
  const liveArrival = telemetry?.signals?.arrival_ms?.value ?? 2688 + Math.round(Math.sin(signalTick / 8) * 7);
  const liveRawTiming = telemetry?.signals?.raw_timing_proxy?.value ?? 886 + Math.round(Math.sin(signalTick / 11) * 4);
  const evidenceConnected = telemetryReachable && Boolean(telemetry?.connected);
  const evidenceStale = telemetryReachable && !telemetry?.connected;
  const isOperatorView = role === "operator";
  const isManagerView = role === "plant-manager";
  const isDecisionView = role === "operator" || role === "senior-operator" || role === "qa" || isManagerView;
  const isDiagnosticView = !isDecisionView;
  const roleMove = isManagerView
    ? "Review the recommended handoff and assign the next qualified owner"
    : role === "qa"
    ? `Verify ${scenario.observed.toLowerCase()} against the active sampling plan`
    : role === "engineering"
      ? `Review the ${scenario.parameter.toLowerCase()} envelope and current test evidence`
      : role === "senior-operator"
        ? `${scenario.bestMove}—capture any justified override`
        : role === "operator"
          ? language === "ES" ? scenario.spanishMove : scenario.bestMove
          : scenario.maintenanceMove;
  const selectFault = (fault: FaultKey) => { const result = automaticVisionResult(fault); setActiveFault(fault); setStage("detected"); setCycles(0); setShowWhy(false); setReasonDepth(0); setAcademyInterest(false); setInspectionNote(""); setTargetSetpointRecorded(false); setReviewedOemFields([]); setOpenOemField(null); setShowHistory(false); setShowParameterHistory(false); setVirtualInspected(result.points); setActiveInspectionPoint(null); setInspectionFindings(result.findings); setFastLaneAccepted(false); setVisionSorted(true); setRouteTarget(""); setAssignedTo(""); };
  const openMachineFlow = (focus: "process" | "aligner" = "process") => { setFlowFocus(focus); setShowMachineFlow(true); };

  const toggleReasoning = () => {
    if (showWhy) {
      setShowWhy(false);
      setReasonDepth(0);
      return;
    }
    setShowWhy(true);
    setReasonDepth(1);
  };

  const reasoningTrail = [
    { label:"WHY THIS MOVE", title:scenario.keyPoint, copy:"The recommendation changes the first relationship that moved outside its commissioned envelope while leaving the stable relationships alone." },
    { label:"WHAT SUPPORTS IT", title:`Camera outcome: ${scenario.observed}`, copy:`The camera shows ${scenario.title.toLowerCase()}. The live machine signals show the strongest matching drift at ${scenario.parameter.toLowerCase()}.` },
    { label:"HOW THE MACHINE RELATES", title:`${scenario.parameter} affects when and how the label meets the bottle`, copy:"Product arrival, label feed, rotation, pressure and geometry must remain coordinated. A disturbance in one relationship can appear later as a visible label defect." },
    { label:"WHY THIS IS THE LOWEST-RISK MOVE", title:"One bounded change, then five fresh outcomes", copy:"The move stays inside the OEM-approved range, is easily reversed and changes one meaningful factor at a time. The next five bottles show whether it helped." },
  ];

  const recovered = stage === "validated" || stage === "released";
  const requiredOemFields = activeFault === "alignment" ? [scenario.parameter, "Product speed", "Merge sensor offset"] : [scenario.parameter, "Product speed"];
  const requiredInspectionPoints = activeFault === "alignment" ? ["Lane B release", "Guide path", "Merge sensor"] : ["Product path", "Active component", "Sensor condition"];
  const virtualInspectionComplete = requiredInspectionPoints.every((point) => virtualInspected.includes(point));
  const recordVirtualFinding = (point: string, finding: string) => {
    setInspectionFindings((findings) => ({...findings, [point]: finding}));
    setVirtualInspected((points) => points.includes(point) ? points : [...points, point]);
  };
  const inspectionGuidance: Record<string,{watch:string; normal:string; abnormal:string; options:string[]}> = {
    "Lane B release": { watch:"Watch the orange Lane B bottle leave its held position and compare it with the dashed expected slot.", normal:"One clean release into the centre of the available moving gap.", abnormal:"Hesitation, double motion, or consistent arrival behind the expected slot.", options:["Release motion appears consistent", "Release appears delayed or intermittent", "Bottle enters the gap late", "Unable to determine"] },
    "Guide path": { watch:"Follow the bottle from release to the merge. Look for side contact, rotation, slowing or lateral wobble.", normal:"Bottle travels freely with stable orientation and no visible guide contact.", abnormal:"Bottle rubs a guide, changes orientation, slows, or oscillates before the merge.", options:["No visible contact or drag", "Guide contact or drag observed", "Bottle unstable in travel", "Unable to determine"] },
    "Merge sensor": { watch:"Watch the red photoeye beam across the merge throat. The DETECT pulse should occur as the bottle breaks the beam—not before or after it passes.", normal:"The beam breaks once per bottle and produces one green DETECT pulse at a repeatable crossing position.", abnormal:"The pulse is late, early, repeated, missing, or occurs at a different bottle position each cycle.", options:["Detection appears synchronized", "Detection appears late or inconsistent", "Possible obstruction or misalignment", "Unable to determine"] },
    "Product path": { watch:"Follow the bottle through the highlighted handling path.", normal:"Stable travel without visible obstruction or unexpected motion.", abnormal:"Drag, wobble, collision or delayed movement.", options:["Path appears clear", "Abnormal travel observed", "Unable to determine"] },
    "Active component": { watch:"Observe the highlighted component through several animation cycles.", normal:"Repeatable motion coordinated with bottle arrival.", abnormal:"Delayed, inconsistent or incomplete motion.", options:["Motion appears repeatable", "Motion appears inconsistent", "Unable to determine"] },
    "Sensor condition": { watch:"Compare the sensor indication with each passing bottle.", normal:"One repeatable indication at the expected position.", abnormal:"Missing, repeated or position-variable indication.", options:["Indication appears repeatable", "Indication appears inconsistent", "Unable to determine"] },
  };
  const activeGuidance = activeInspectionPoint ? inspectionGuidance[activeInspectionPoint] : null;
  const inspectionHeadline = requiredInspectionPoints.map((point) => {
    const finding = inspectionFindings[point] || "";
    if (point === "Lane B release" && /delayed|late/i.test(finding)) return "Lane B release late";
    if (point === "Guide path" && /no visible|clear/i.test(finding)) return "Guide path clear";
    if (point === "Merge sensor" && /synchronized/i.test(finding)) return "Sensor synchronized";
    return finding || `${point} pending`;
  }).join(" · ");
  const beltSurfaceSpeed = 1.24;
  const bottleContactSpeed = recovered ? 1.232 : activeFault === "folds" ? 1.18 : 1.23;
  const measuredSlip = Math.abs(beltSurfaceSpeed - bottleContactSpeed) / beltSurfaceSpeed * 100;
  const slipUncertainty = activeFault === "folds" && !recovered ? 0.6 : 0.4;
  const slipAlarm = measuredSlip > 2;
  const reviewOemField = (field: string) => {
    if (stage !== "guided") return;
    setOpenOemField(field);
  };
  const confirmOemEvidence = (field: string) => setReviewedOemFields((fields) => fields.includes(field) ? fields : [...fields, field]);
  const oemEvidence = (field: string) => {
    if (field === "Product speed") return { sourceA:`Drive encoder → belt surface · ${beltSurfaceSpeed.toFixed(2)} m/s`, sourceB:`Camera centroid → bottle translation · ${bottleContactSpeed.toFixed(2)} m/s`, reference:"Camera fiducial → bottle rotation · 7.8 rad/s", result:`Calculated contact-point velocity shows ${measuredSlip.toFixed(1)}% ±${slipUncertainty.toFixed(1)}% measured slip — ${slipAlarm ? "outside" : "inside"} the 0–2% commissioned envelope.`, limitation:slipAlarm ? "Slip is established, but its cause remains unresolved (pressure, wear, contamination or geometry). Inspect contact conditions before changing speed." : "Slippage check passed. No slip-related adjustment is needed—proceed to the five-bottle outcome test." };
    if (field === "Merge sensor offset") return { sourceA:"HMI configuration · 18 ms", sourceB:"Commissioned profile · 18 ms", reference:"Virtual timing trace · one repeatable edge", result:"Configuration matches the commissioned recipe and the current trace is repeatable.", limitation:"Configuration match is not proof of physical sensor position or calibration." };
    return { sourceA:`HMI readback · ${scenario.oldValue}`, sourceB:`Direct machine signal · ${activeFault === "bubbles" ? pressure.toFixed(1) + " psi" : scenario.oldValue}`, reference:`Commissioned guidance · ${scenario.direction}`, result:"Current readback is corroborated and identified under the active recipe.", limitation:"Readback agreement does not establish that the current setting is optimal or that the proposed change will help." };
  };
  const arrivalBase = recovered ? 12 : activeFault === "alignment" ? 43 : activeFault === "multiple" ? 56 : activeFault === "folds" ? 29 : 12;
  const arrival = arrivalBase + Math.sin(signalTick / 2.4) * 2.6;
  const pressureBase = recovered ? 45.2 : activeFault === "bubbles" ? 32.4 : 45.2;
  const pressure = pressureBase + Math.cos(signalTick / 3.7) * 0.7;
  const ratioBase = recovered ? 1.0 : activeFault === "stretch" ? 1.045 : activeFault === "folds" ? 0.965 : 1.0;
  const feedRatio = ratioBase + Math.sin(signalTick / 4.2) * 0.004;
  const marginBase = recovered ? 310 : activeFault === "multiple" ? 55 : activeFault === "folds" ? 132 : 310;
  const cycleMargin = marginBase + Math.cos(signalTick / 3.1) * 8;
  const evidenceAge = 110 + ((signalTick * 137) % 630);
  const metrics = [
    { name: "Feed / wrapper", value: feedRatio.toFixed(3), unit: "ratio", envelope: "0.980 – 1.020", alarm:feedRatio < .98 || feedRatio > 1.02, provenance:"Derived from two direct speeds" },
    { name: "Arrival phase", value: `${arrival >= 0 ? "+" : ""}${arrival.toFixed(0)}`, unit: "ms", envelope: "−20 – +20", alarm:Math.abs(arrival) > 20, provenance:"Wrapper-entry sensor timing" },
    { name: "Cycle margin", value: cycleMargin.toFixed(0), unit: "ms", envelope: "≥ 180", alarm:cycleMargin < 180, provenance:"Derived from bottle interval" },
    { name: "Applicator pressure", value: pressure.toFixed(1), unit: "psi", envelope: "40.0 – 50.0", alarm:pressure < 40 || pressure > 50, provenance:"Direct regulator signal" },
    { name: "Bottle surface slip", value: measuredSlip.toFixed(1), unit: "%", envelope: "0.0 – 2.0", alarm:slipAlarm, provenance:"Camera contact velocity + drive encoder" },
  ];
  const diagnosticResolution = ({
    alignment: { first:visionSorted ? "Command → physical Lane B release response" : "Lane B arrival phase at wrapper entry", established:visionSorted ? ["Lane B release 39–44 ms late · 4/5 cycles","Guide path stable · no measurable drag","Camera crossing and S1 edge agree within ±3 ms","Slippage check passed · 0.8% ±0.4%"] : ["Placement 4.2 mm late · 4/5 bottles","Arrival phase outside −20 to +20 ms","Feed ratio, pressure and bottle slip remain inside bounds"], excluded:visionSorted ? ["Guide-path obstruction","Merge-photoeye timing mismatch","Global feed/wrapper speed drift","Bottle-surface slippage"] : ["Global feed/wrapper speed drift","Low applicator pressure","Bottle-surface slippage"], unresolved:visionSorted ? ["Mechanical release response","Pneumatic or actuator condition","Whether the bounded timing change improves fresh outcomes"] : ["Physical Lane B release behaviour","Guide-path condition","Photoeye crossing agreement"], next:visionSorted ? "Select one bounded Lane B timing target, then proceed to the five-bottle outcome test" : "Run synchronized camera inspection to separate release delay from downstream travel or sensing" },
    folds: { first:"Aligner-belt → bottle contact velocity relationship", established:["Measured bottle-surface slip 4.8% ±0.6% · outside 0–2%","Folded right edge · 3/5 bottles","Outcome repeats at the wrapper"], excluded:["Low applicator pressure","Merge-arrival phase drift","Camera/encoder synchronization error"], unresolved:["Insufficient belt pressure","Belt wear or contamination","Unequal mechanical coupling"], next:"Inspect belt pressure and contact condition before changing the bounded aligner target" },
    stretch: { first:"Label-web presentation relationship", established:["Stretch pattern repeated · 5/5 labels","Feed/wrapper ratio above envelope","Arrival phase and pressure remain coordinated"], excluded:["Late bottle arrival","Low applicator pressure"], unresolved:["Actual web tension","Unequal roller pull","Label-stock contribution"], next:"Cross-check tension feedback against roller speeds and the active recipe baseline" },
    bubbles: { first:"Applicator contact-pressure relationship", established:["Applicator pressure below 40–50 psi envelope","Air pockets repeated · 4/5 labels","Independent pressure signals agree"], excluded:["Arrival-phase drift","Insufficient cycle margin"], unresolved:["Wipe contact condition","Regulator stability under load","Bottle-surface contamination"], next:"Apply only the pre-approved pressure target, then inspect five fresh camera outcomes" },
    multiple: { first:"Gap-sensor edge sequence", established:["Two label commands observed for one product cycle","Repeated S3 edges retained in the event sequence","S3 change signed · device readback matched"], excluded:["Unattributed configuration change","Single late label-feed event","Low contact pressure"], unresolved:["Sensor contamination or alignment","Electrical bounce or wiring","True double-gap presentation"], next:"Preserve the trace and inspect S3 locally; contradictory sensing blocks an automatic change" },
  } satisfies Record<FaultKey,{first:string; established:string[]; excluded:string[]; unresolved:string[]; next:string}>)[activeFault];
  const parameterHistory = ({
    alignment:{range:"120–150 ms", stable:"46 h", changes:"3", success:"82%", common:"125 ms", delay:"11 min", typical:"±5 ms", baseline:"1.8/mo", percentile:"88th", volatility:"1.7×"},
    folds:{range:"116–128 RPM", stable:"31 h", changes:"4", success:"79%", common:"124 RPM", delay:"18 min", typical:"±3 RPM", baseline:"2.0/mo", percentile:"91st", volatility:"2.0×"},
    stretch:{range:"2.8–3.6 N", stable:"22 h", changes:"2", success:"88%", common:"3.2 N", delay:"7 min", typical:"±0.2 N", baseline:"1.1/mo", percentile:"84th", volatility:"1.8×"},
    bubbles:{range:"40–50 psi", stable:"64 h", changes:"2", success:"91%", common:"45 psi", delay:"14 min", typical:"±3 psi", baseline:"1.4/mo", percentile:"79th", volatility:"1.4×"},
    multiple:{range:"58–68 %", stable:"19 h", changes:"5", success:"68%", common:"64 %", delay:"6 min", typical:"±2 points", baseline:"1.3/mo", percentile:"96th", volatility:"3.8×"},
  } satisfies Record<FaultKey,{range:string; stable:string; changes:string; success:string; common:string; delay:string; typical:string; baseline:string; percentile:string; volatility:string}>)[activeFault];
  const recentParameterChanges = [
    {time:"Today · 13:47", change:`${scenario.newValue} → ${scenario.oldValue}`, context:"Operator Station 02", integrity:"Signed · readback matched", outcome:`Active finding appeared ${parameterHistory.delay} later`, tone:"watch"},
    {time:"Aug 18 · 09:12", change:`${scenario.oldValue} → ${scenario.newValue}`, context:"Maintenance · bounded recovery", integrity:"WO-4817 · readback matched", outcome:"5/5 fresh outcomes accepted", tone:"helped"},
    {time:"Aug 12 · 15:34", change:`${scenario.newValue} → ${scenario.oldValue}`, context:"Recipe changeover", integrity:"Recipe signature verified", outcome:"No measurable degradation", tone:"neutral"},
    {time:"Aug 04 · 07:05", change:`${scenario.oldValue} → ${scenario.newValue}`, context:"Commissioning adjustment", integrity:"Engineer role · signed", outcome:"Stable for 84 production hours", tone:"helped"},
    {time:"Jul 14 · 11:26", change:`${scenario.oldValue} → ${scenario.newValue}`, context:"Guided troubleshooting", integrity:"Operator ID · readback matched", outcome:"Dependent envelopes returned to normal", tone:"helped"},
  ];
  const responseMode: ResponseMode = activeFault === "bubbles" ? "automatic" : activeFault === "alignment" ? "confirm" : activeFault === "multiple" ? "escalate" : "guided";
  const requiresEscalationHypotheses = responseMode === "escalate";
  const routingRecommendation = ({
    alignment:{target:"Controls technician", reason:"Controller command is known; physical Lane B release response still needs qualified verification."},
    folds:{target:"Millwright", reason:"Measured bottle-surface slip points first to contact pressure, wear, contamination or mechanical coupling."},
    stretch:{target:"Millwright", reason:"The remaining separation depends on web tension, roller pull and material handling."},
    bubbles:{target:"Maintenance", reason:"Pressure is outside its envelope; regulator stability and wipe contact need local verification."},
    multiple:{target:"Controls technician", reason:"Repeated S3 edges may reflect contamination, alignment, wiring or electrical bounce; the fast path is withdrawn."},
  } satisfies Record<FaultKey,{target:string;reason:string}>)[activeFault];
  const selectedRoute = routeTarget || routingRecommendation.target;
  const modeCopy = {
    automatic: { label:"AUTOMATIC · PRE-APPROVED", title:"Earned fast path available", detail:"Independent pressure signals agree, the active recipe matches, and 14 comparable bounded recoveries succeeded without rollback." },
    confirm: { label:"CAMERA COMPLETE · NO EXCEPTIONS", title:"Vision has already narrowed the investigation", detail:"Release motion, guide-path stability and photoeye crossing were classified automatically. No operator camera task is required; detailed evidence remains available to maintenance." },
    guided: { label:"GUIDED · MORE EVIDENCE NEEDED", title:"Keep the inspection gates", detail:"The current signature is useful, but physical coupling or tension still needs current-event inspection before a setting change." },
    escalate: { label:"ESCALATE · FAST PATH WITHDRAWN", title:"Contradictory sensing blocks intervention", detail:"Repeated sensor edges can hide contamination, alignment or wiring faults. Preserve state and route the evidence package." },
  }[responseMode];
  const qualificationChecks = responseMode === "automatic"
    ? ["Calibrated pressure transmitter agrees with regulator feedback", "Asset, recipe, units and firmware match the approved profile", "14/14 comparable recoveries succeeded; 0 rollbacks", "Target 45 psi is inside the approved 40–50 psi envelope"]
    : responseMode === "confirm"
      ? ["Camera and controller timing agree within ±3 ms", "Guide path and global speed drift filtered out", "94% closest-case similarity · 6 independent cases", "No visual contradiction or occlusion detected"]
      : responseMode === "guided"
        ? ["Candidate relationship identified", "Current physical condition is not yet established", "Historical precedent cannot satisfy the missing inspection", "Automatic authority is withheld"]
        : ["Signal behavior is contradictory", "Current sensor condition is unresolved", "Automatic and confirmation paths are vetoed", "Maintenance evidence package required"];
  const runEarnedPath = () => {
    if (responseMode === "automatic") { setFastLaneAccepted(true); setCycles(0); setStage("changed"); }
    if (responseMode === "confirm") { setFastLaneAccepted(true); setReviewedOemFields(requiredOemFields); setStage("guided"); }
  };
  const confirmOemChange = () => {
    setTargetSetpointRecorded(true);
    setOpenOemField(null);
    setCycles(0);
    setStage("changed");
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark"><i>LA</i></span><div><b>LineAlert</b><small>for packaging machinery</small></div></div>
        <div className="speedway-lockup"><span className="speed-stripes"><i/><i/><i/></span><div><b>SPEEDWAY</b><small>PACKAGING MACHINERY · CONCEPT</small></div></div>
        <div className="asset-binding"><span className="eyebrow">MACHINE PROFILE</span><b>LM-W150/200-SW · Wrap Labeler</b><small>Line 04 · 500 mL round bottle</small></div>
        <div className="view-controls">
          <label className="role-pack-select"><span>ACTIVE ROLE PACK</span><select value={role} onChange={(event) => setRole(event.target.value as Role)} aria-label="Active LineAlert role pack">{(Object.keys(rolePacks) as Role[]).map((roleKey) => <option value={roleKey} key={roleKey}>{rolePacks[roleKey].label}</option>)}</select></label>
          <button className="language" onClick={() => setLanguage(language === "EN" ? "ES" : "EN")}>{language} · {language === "EN" ? "Español" : "English"}</button>
          <div className="live-status"><span className="live-dot pulse"/><div><b>Live demo stream</b><small>{clock}</small></div></div>
        </div>
      </header>

      <section className="fault-lab" aria-label="Fault injection lab">
        <div className="fault-label"><span className="eyebrow">COMMISSIONING LAB</span><b>Inject a bounded fault</b><small>Demo only · no equipment writes</small></div>
        <div className="fault-buttons">
          {(Object.keys(scenarios) as FaultKey[]).map((fault) => <button className={activeFault === fault ? "selected" : ""} onClick={() => selectFault(fault)} key={fault}><span>{scenarios[fault].short}</span><small>{scenarios[fault].injection}</small></button>)}
        </div>
      </section>

      <section className="role-lens" aria-label={`${rolePack.label} role pack`}>
        <div className="role-lens-mark"><i>{rolePack.icon}</i><span><small>{rolePack.short} ROLE PACK</small><b>{rolePack.label}</b></span></div>
        <div><small>WHAT THIS PACK PRIORITIZES</small><b>{rolePack.focus}</b></div>
        <div><small>HUMAN VALUE ADDED</small><b>{rolePack.contribution}</b></div>
        <div className="shared-truth"><small>SHARED EVIDENCE CORE</small><b>Same observations · different lens and authority</b></div>
      </section>

      <section className="cross-role-bridge" aria-label="Cross-role reasoning handoff">
        <div><small>CROSS-ROLE SYSTEMS UNDERSTANDING</small><b>{rolePack.learns}</b></div>
        <i>→</i>
        <div><small>STRUCTURED HANDOFF</small><b>{rolePack.handoff}</b></div>
        <span>Predictive awareness under uncertainty—not expanded authority</span>
      </section>

      <section className={`evidence-console ${evidenceStale ? "evidence-stale" : ""}`} aria-label="Shared machine evidence console">
        <header>
          <div><span className="eyebrow">SHARED EVIDENCE CORE · READ ONLY</span><b>{evidenceConnected ? "Microsoft OPC PLC proxy connected" : evidenceStale ? "Live source unavailable—last samples retained as stale" : "Demonstration evidence stream"}</b><small>{evidenceConnected ? `${telemetry?.asset_id} · ${telemetry?.source_id}` : evidenceStale ? telemetry?.reason_code : "Run this interface locally beside the LineAlert bridge to bind live OPC UA evidence."}</small></div>
          <button onClick={() => setShowEvidenceConsole((open) => !open)}>{showEvidenceConsole ? "Collapse evidence" : "Open evidence"}</button>
          <strong className={evidenceConnected ? "source-live" : evidenceStale ? "source-stale" : "source-demo"}><i/>{evidenceConnected ? "LIVE OPC UA" : evidenceStale ? "STALE · FAIL CLOSED" : "SIMULATED"}</strong>
        </header>
        {showEvidenceConsole && <div className="evidence-console-body">
          <div className="evidence-gauges">
            <EvidenceGauge label="Motor speed proxy" value={liveRpm} unit="rpm" quality={telemetry?.signals?.rpm?.quality ?? "demo"}/>
            <EvidenceGauge label="Derived arrival proxy" value={liveArrival} unit="ms" quality={telemetry?.signals?.arrival_ms?.quality ?? "demo"}/>
            <EvidenceGauge label="Contact pressure proxy" value={livePressure} unit="psi" quality={telemetry?.signals?.pressure_psi?.quality ?? "demo"}/>
            <EvidenceGauge label="Unmapped timing proxy" value={liveRawTiming} unit="unit" quality={telemetry?.signals?.raw_timing_proxy?.quality ?? "demo"}/>
          </div>
          <div className="evidence-chain">
            <span><small>SOURCE</small><b>{evidenceConnected ? "Allow-listed OPC UA nodes" : "Scenario generator"}</b></span><i>→</i>
            <span><small>QUALIFICATION</small><b>{evidenceStale ? "Current use refused" : "Status · timestamp · identity"}</b></span><i>→</i>
            <span><small>SEMANTIC ADMISSION</small><b>{evidenceConnected ? "0 / 4 signals admitted to diagnostics" : "No live signals admitted"}</b></span><i>→</i>
            <span><small>ROLE LENS</small><b>{rolePack.label} receives decision-relevant evidence</b></span>
          </div>
          {evidenceConnected && <div className="semantic-boundary"><div><small>PROXY BOUNDARY</small><b>{telemetry?.proxy_warning ?? "Simulator evidence is not verified physical machine state."}</b></div><div className="binding-row"><span><b>rpm</b><small>Display only · physical drive mapping absent</small></span><span><b>pressure_psi</b><small>Display only · applicator sensor mapping absent</small></span><span><b>arrival_ms</b><small>Context only · derived proxy ≠ arrival phase</small></span><span><b>raw_timing_proxy</b><small>Unmapped · diagnostically inadmissible</small></span></div><strong>EVIDENCE.SEMANTIC_BINDING_REQUIRED · transport qualified, diagnostic use refused</strong></div>}<div className="evidence-provenance"><span><b>{telemetry?.reason_code ?? "LINEALERT.DEMO.EVIDENCE_STREAM"}</b><small>{telemetry?.observation_sequence ? `Observation ${telemetry.observation_sequence}` : "No claim of physical machine state"}</small></span><span><b>{telemetry?.read_only === false ? "WRITE CAPABILITY PRESENT" : "No writes · no browse expansion"}</b><small>{telemetry?.bridge_timestamp ? new Date(telemetry.bridge_timestamp).toLocaleTimeString() : "Demonstration clock only"}</small></span><span><b>Evidence ≠ root cause</b><small>Corroboration and a fresh outcome still control the next gate.</small></span></div>
        </div>}
      </section>

      <div className="scenario-boundary"><span>COMMISSIONING SCENARIO · SIMULATED DIAGNOSTIC MODEL</span><b>The cards below are generated scenario evidence—not measurements derived from the live OPC proxy above.</b></div>

      <section className="workspace">
        <aside className="sidebar">
          <div className="camera-card">
            <div className="camera-head"><span className="eyebrow">CAMERA OUTCOME</span><span className="recording">● LIVE</span></div>
            <div className={`camera-insight ${recovered ? "camera-insight-pass" : ""}`}>
              <span className="camera-insight-icon">{recovered ? "✓" : scenario.symbol}</span>
              <div><b>{recovered ? "Inspection pass" : scenario.title}</b><small>{recovered ? "Within commissioned tolerance" : scenario.observed}</small></div>
            </div>
            <div className={`bottle-frame live-line fault-${activeFault} ${recovered ? "fault-cleared" : ""}`}>
              <div className="machine-frame"><i/><i/><i/></div>
              <div className="machine-hmi"><span>LM-W200</span><b>RUN</b></div>
              <div className="label-roll"><span/><i/></div>
              <div className="applicator"><b>SPM</b><span/></div>
              <div className="wrap-station"><i/><i/></div>
              {[0,1,2,3].map((item) => <div className={`moving-bottle bottle-${item}`} key={item}><i/><div className="applied-label">SPRING</div></div>)}
              <div className="photoeye"/>
              <div className="belt"><i/><i/><i/><i/><i/><i/></div>
              <button className="expand-machine" onClick={() => openMachineFlow()} aria-label="Expand animated machine flow"><span>Inspect full machine flow</span><b>↗</b></button>
            </div>
            <div className={`defect-row ${recovered ? "pass-row" : ""}`}><span className="warning-icon">{recovered ? "✓" : "!"}</span><div><b>{recovered ? "Camera outcome recovered" : scenario.title}</b><small>{recovered ? "Last 5 bottles inside visual tolerance" : scenario.count}</small></div><strong>#{bottleCount}</strong></div>
          </div>

          <div className="recommendation v11-card">
            <div className="recommendation-top"><span className="eyebrow">{role.toUpperCase()} GUIDANCE · OEM-BOUNDED</span><span className="risk-pill">LOW RISK</span></div>
            <div className="factor-lockup"><span className="factor-symbol">{scenario.symbol}</span><div><small>{scenario.parameter}</small><b>{scenario.drift}</b></div></div>
            {scenario.parameter === "Aligner speed" && <button className="component-aid" onClick={() => openMachineFlow("aligner")}><span><small>COMPONENT VISUAL AID</small><b>Locate the bottle aligner</b></span><strong>View in full topology ↗</strong></button>}
            <span className="eyebrow">MOST PROMISING NEXT MOVE</span>
            <h2>{roleMove}</h2>
            <p className="verify-copy">{language === "ES" ? "Revise las próximas 5 botellas." : "Check the next 5 bottles."}</p>
            <button className="why-button" onClick={toggleReasoning}>{showWhy ? "Close explanation" : language === "ES" ? "¿Por qué este paso?" : "Why this move?"}</button>
            {showWhy && <div className="reasoning-path">
              <div className="reasoning-progress" aria-label={`Reasoning depth ${reasonDepth} of ${reasoningTrail.length}`}>
                {reasoningTrail.map((_, index) => <i className={index < reasonDepth ? "revealed" : ""} key={index}/>) }
              </div>
              {reasoningTrail.slice(0, reasonDepth).map((item, index) => <div className="reasoning-layer" key={item.label}>
                <small>{String(index + 1).padStart(2,"0")} · {item.label}</small>
                <b>{item.title}</b>
                <span>{item.copy}</span>
              </div>)}
              {reasonDepth < reasoningTrail.length && <button className="deeper-button" onClick={() => setReasonDepth((depth) => Math.min(depth + 1, reasoningTrail.length))}>Go one level deeper →</button>}
              {reasonDepth === reasoningTrail.length && <div className="academy-invite">
                <small>YOU KEPT EXPLORING</small>
                <b>You seem interested in how machines tell their story.</b>
                <span>LineAlert Academy turns live recovery moments into short, optional lessons on timing, relationships and disciplined troubleshooting.</span>
                <button onClick={() => setAcademyInterest(true)}>{academyInterest ? "Interest noted ✓" : "Explore LineAlert Academy"}</button>
                <em>Optional · never required to operate the machine</em>
              </div>}
            </div>}
            <div className="guardrail"><span>Authority</span><b>{rolePack.authority}</b></div>
          </div>
        </aside>

        <section className={`main-panel ${isOperatorView ? "operator-view" : "technical-view"}`}>
          <div className="section-title"><div><span className="eyebrow">{rolePack.short} LENS · RELATIONAL EVIDENCE · UPDATING 4 Hz</span><h1>{rolePack.headline}</h1></div><span className="age"><i className="stream-dot"/> Evidence age {evidenceAge} ms</span></div>
          {isManagerView && <section className="manager-console" aria-label="Plant manager incident coordination">
            <header><div><span className="eyebrow">FACILITY INCIDENT COORDINATION · LINE 04</span><h2>Wrap labeler recovery is active</h2><p>LineAlert has preserved the investigation so the next qualified role starts at the current decision boundary.</p></div><strong>{assignedTo ? "HANDOFF ASSIGNED" : "ROUTING DECISION READY"}</strong></header>
            <div className="manager-status-grid"><span><small>PRODUCTION IMPACT</small><b>Line stopped · 11 min</b></span><span><small>CURRENT OWNER</small><b>{assignedTo || "Senior Operator"}</b></span><span><small>INVESTIGATION STATE</small><b>Fault domain localized</b></span><span><small>NEXT GATE</small><b>{requiresEscalationHypotheses ? "Qualified escalation" : "Bounded test + fresh outcomes"}</b></span></div>
            <div className="manager-route"><div><small>LINEALERT RECOMMENDED HANDOFF</small><b>{routingRecommendation.target}</b><p>{routingRecommendation.reason}</p></div><label><span>Plant manager routing</span><select value={selectedRoute} onChange={(event) => { setRouteTarget(event.target.value); setAssignedTo(""); }}><option>Senior Operator</option><option>Millwright</option><option>Maintenance</option><option>Controls technician</option><option>Quality</option><option>Engineering</option><option>OEM support</option></select></label><button onClick={() => setAssignedTo(selectedRoute)}>{assignedTo ? `Assigned to ${assignedTo} ✓` : "Assign current evidence package"}</button></div>
            <footer><b>Boundary:</b><span>LineAlert recommends the destination. The plant manager controls priority and assignment. Qualified roles retain technical, safety and release authority.</span></footer>
          </section>}

          {!isManagerView && <div className="metric-grid">
            {metrics.map((metric) => (
              <article className="metric-card" key={metric.name}>
                <div className="metric-title"><div className="metric-name"><b>{metric.name}</b>{metric.name === "Aligner speed" && <button className="locate-component" onClick={() => openMachineFlow("aligner")}>What is the aligner? <span>↗</span></button>}</div><span className={metric.alarm && !recovered ? "bad-pill" : "good-pill"}><strong>{metric.name === "Bottle surface slip" ? (metric.alarm && !recovered ? "Slippage investigation required" : "Slippage check passed") : (metric.alarm && !recovered ? "Outside commissioned bound" : "Within commissioned bound")}</strong><small>{metric.envelope} {metric.unit}</small></span></div>
                <div className="metric-value">{metric.value}<small>{metric.unit}</small></div>
                <div className="metric-details"><span>Evidence source<b>{metric.provenance}</b></span><span>Commissioned envelope<b>{metric.envelope} {metric.unit}</b></span></div>
              </article>
            ))}
          </div>}

          <div className={`relationship-card ${!recovered ? "finding-alert" : ""} ${isOperatorView ? "operator-summary" : ""}`}>
            <div><span className="eyebrow">BOUNDED FINDING</span><h2>{recovered ? "Fresh evidence returned to the commissioned envelope" : `${scenario.injection} pattern detected`}</h2><p>{recovered ? "The adjustment was followed by five acceptable outcomes." : `Camera evidence and the highlighted relationship match the ${scenario.title.toLowerCase()} heuristic. This is a candidate troubleshooting route—not proof of root cause.`}</p></div>
            <div className="finding-actions"><div className={`finding-badge ${!recovered ? "alert-badge" : ""}`}><span>RELATIONSHIP</span><b>{recovered ? "COORDINATED" : "DRIFT"}</b><small>5 fresh cycles</small></div><button className="history-button" onClick={() => setShowHistory((visible) => !visible)}>{showHistory ? "Close history" : "Find similar outcomes"}</button></div>
          </div>

          <section className="diagnostic-resolution" aria-label="Deterministic diagnostic resolution">
            <header><div><span className="eyebrow">DETERMINISTIC DIAGNOSTIC RESOLUTION · {rolePack.label.toUpperCase()} PACK</span><h2>{isDecisionView ? "Next decision resolved—showing only what changes the current action" : "Full evidence narrows the work before anyone touches the machine"}</h2></div><strong>ANALYZED AUTOMATICALLY</strong></header>
            {(isDiagnosticView || requiresEscalationHypotheses) && <div className="resolution-grid">
              <article className="resolution-established"><span>ESTABLISHED</span>{diagnosticResolution.established.map((item) => <p key={item}><i>✓</i>{item}</p>)}</article>
              <article className="resolution-excluded"><span>EXCLUDED BY CURRENT EVIDENCE</span>{diagnosticResolution.excluded.map((item) => <p key={item}><i>×</i>{item}</p>)}</article>
              <article className="resolution-unresolved"><span>{requiresEscalationHypotheses ? "CAUSES TO SEPARATE DURING ESCALATION" : "WHAT THE NEXT TEST WILL SEPARATE"}</span>{diagnosticResolution.unresolved.map((item) => <p key={item}><i>?</i>{item}</p>)}</article>
            </div>}
            {isDecisionView && !requiresEscalationHypotheses && <div className="operator-resolution"><span><small>FAULT DOMAIN LOCALIZED</small><b>{diagnosticResolution.first}</b><em>{diagnosticResolution.excluded.length} explanations filtered out · no current contradiction</em></span><span><small>NEXT DECISION RESOLVED</small><b>{diagnosticResolution.next}</b></span><button onClick={() => openMachineFlow()}>Review supporting evidence</button></div>}
            {isDecisionView && !requiresEscalationHypotheses && <details className="deferred-uncertainty"><summary>What remains unproven? <span>Does not change the next step</span></summary><div>{diagnosticResolution.unresolved.map((item) => <p key={item}><i>?</i>{item}</p>)}</div></details>}
            {isDiagnosticView && <div className="resolution-localization"><span><small>FIRST DEMONSTRATED DEVIATION</small><b>{diagnosticResolution.first}</b><em>Localization—not root-cause proof</em></span><span><small>{rolePack.short} PRIORITY</small><b>{rolePack.focus}</b><em>Role-specific emphasis; shared evidence remains unchanged</em></span></div>}
            {requiresEscalationHypotheses && isDecisionView && <div className="resolution-localization escalation-boundary"><span><small>WHY THIS IS SURFACED NOW</small><b>Contradictory sensing changes the decision and withdraws the bounded fast path.</b><em>Preserve state and route the evidence package.</em></span><span><small>{rolePack.short} PRIORITY</small><b>{rolePack.focus}</b><em>Escalation reveals only the hypotheses relevant to the handoff.</em></span></div>}
          </section>

          {!isManagerView && <section className="parameter-intelligence" aria-label="Parameter operational history">
            <header><div><span className="eyebrow">PARAMETER INTELLIGENCE · SIMULATED OPERATIONS HISTORY</span><h2>{scenario.parameter}</h2></div><span className="temporal-boundary"><b>{activeFault === "multiple" ? "UNUSUAL CHANGE PATTERN" : "RELEVANT CHANGE FOUND"}</b><small>Fault-domain signal—not causal proof</small></span></header>
            <div className="parameter-stats">
              <span><small>Current</small><b>{scenario.oldValue}</b></span><span><small>Commissioned range</small><b>{parameterHistory.range}</b></span><span><small>Stable duration</small><b>{parameterHistory.stable}</b></span><span><small>Changes this month</small><b>{parameterHistory.changes}</b></span><span><small>Compatible-run success</small><b>{parameterHistory.success}</b></span><span><small>Common good value</small><b>{parameterHistory.common}</b></span>
            </div>
            <div className="change-summary"><span><small>WHAT MATTERS NOW</small><b>{scenario.parameter} changed {scenario.newValue} → {scenario.oldValue}; the active drift appeared {parameterHistory.delay} later.</b><em>Same asset, recipe and speed band · current setting corroborated automatically</em></span><button onClick={() => setShowParameterHistory((visible) => !visible)}>{showParameterHistory ? "Hide change history" : "Show last 5 changes"}</button></div>
            <div className={`configuration-integrity ${activeFault === "multiple" ? "integrity-focus" : ""}`}><div><small>CHANGE INTEGRITY</small><b>Verified, bounded and attributable</b><em>Current change event matches the device readback.</em></div><span><small>AUTHORITY</small><b>Operator Station 02 · signed</b></span><span><small>DEVICE STATE</small><b>{scenario.oldValue} · direct readback</b></span><span><small>LOCAL CONTROL</small><b>Digitally locked in production</b></span><strong>Any behaviour change without a matching authorized event becomes a configuration-integrity exception and blocks automatic intervention.</strong></div>
            <div className="change-unusualness"><span><small>TYPICAL ADJUSTMENT</small><b>{parameterHistory.typical}</b></span><span><small>CURRENT CHANGE RANK</small><b>{parameterHistory.percentile} percentile</b></span><span><small>NORMAL FREQUENCY</small><b>{parameterHistory.baseline}</b></span><span><small>CURRENT VOLATILITY</small><b>{parameterHistory.volatility} normal</b></span></div>
            {showParameterHistory && <div className="change-table" role="table" aria-label={`Last five ${scenario.parameter} changes`}><div className="change-row change-head" role="row"><span>Time</span><span>Change</span><span>Source</span><span>Authority / integrity</span><span>Subsequent outcome</span></div>{recentParameterChanges.map((item) => <div className="change-row" role="row" key={`${item.time}-${item.change}`}><span>{item.time}</span><b>{item.change}</b><span>{item.context}</span><span>{item.integrity}</span><strong className={`change-${item.tone}`}>{item.outcome}</strong></div>)}</div>}
          </section>}

          {showHistory && <section className="history-panel" aria-label="Contextualized historical outcomes">
            <header><div><span className="eyebrow">ON-DEMAND OEM CONTEXT · DETERMINISTIC COMPATIBILITY FILTER</span><h2>Closest recorded outcomes</h2><p>Compatible machine, recipe, units and topology were filtered first. Remaining cases are ranked by current-context overlap.</p></div><div className="history-boundary"><b>PRECEDENT ≠ PROOF</b><span>Current inspection and validation remain required.</span></div></header>
            <div className="history-context"><span><small>Asset</small><b>LM-W200 · Line 04</b></span><span><small>Recipe</small><b>500 mL Spring Water</b></span><span><small>Current signature</small><b>{scenario.injection}</b></span><span><small>Current setting</small><b>{scenario.parameter} · {scenario.oldValue}</b></span></div>
            <div className="history-support" aria-label="Historical support summary">
              <span><small>Closest case</small><b>94%</b><em>strong similarity</em></span>
              <span><small>Evidence coverage</small><b>87%</b><em>eligible for display</em></span>
              <span><small>Independent cases</small><b>6</b><em>distinct incidents</em></span>
              <span><small>Same verified outcome</small><b>5 / 6</b><em>83% consistency</em></span>
              <strong><small>CLASSIFICATION</small>Historically supported pattern</strong>
            </div>
            <details className="history-method">
              <summary>How similarity is classified</summary>
              <div><p><b>Eligibility gates first:</b> compatible asset and topology, firmware/configuration, operating mode, recipe, units, clock quality, calibration and evidence window. A critical mismatch refuses comparison.</p><p><b>Deterministic weighted score:</b> first envelope deviation 25% · event signature 20% · temporal sequence 20% · topology path 15% · operating context 10% · deviation magnitude/direction 10%.</p><p><b>Published separately:</b> similarity describes evidence-pattern resemblance; coverage measures available expected evidence; case count excludes duplicate alarms and repeated records from one incident; outcome consistency uses verified historical dispositions.</p></div>
            </details>
            <div className="history-cases">
              <HistoryCase score="94%" id="LA-2026-1471" date="Jul 14" action={activeFault === "alignment" ? "Release delay 145 → 125 ms" : `${scenario.parameter} adjusted one approved step`} result="HELPED" overlap="Same asset, recipe, fault signature, speed band and inspection result" difference="Earlier bottle lot · previous controller firmware"/>
              <HistoryCase score="82%" id="LA-2026-1188" date="May 03" action={activeFault === "alignment" ? "Cleaned merge sensor; no timing change" : "Physical condition corrected; setting unchanged"} result="HELPED" overlap="Same topology, symptom and operating speed" difference="Different inspection finding · alternate supplier lot"/>
              <HistoryCase score="67%" id="LA-2025-0894" date="Nov 22" action={activeFault === "alignment" ? "Release delay reduced 15 ms" : `${scenario.parameter} changed`} result="INCONCLUSIVE" overlap="Same machine family and visual outcome" difference="Different recipe, line and firmware · evidence window incomplete"/>
            </div>
            <footer><b>Boundary:</b><span>Similarity retrieves relevant experience. Case count and outcome consistency establish historical support. Fresh current-event evidence determines whether the present finding remains valid.</span></footer>
          </section>}

          <section className={`fast-lane mode-${responseMode}`} aria-label="Earned validation response mode">
            <header><div><span className="eyebrow">EARNED VALIDATION · CURRENT RESPONSE MODE</span><h2>{modeCopy.title}</h2><p>{modeCopy.detail}</p></div><strong>{modeCopy.label}</strong></header>
            <div className="fast-lane-grid">
              <div className="qualification-list"><b>Why this mode qualified</b>{qualificationChecks.map((check) => <span key={check}><i>✓</i>{check}</span>)}</div>
              <div className="bounded-action"><span><small>AUTHORIZED BOUND</small><b>{responseMode === "automatic" ? `${scenario.parameter}: ${scenario.oldValue} → ${scenario.newValue}` : responseMode === "confirm" ? "One approved timing increment" : "No automatic write authorized"}</b></span><span><small>MANDATORY OUTCOME CHECK</small><b>Five fresh bottles inside all dependent envelopes</b></span><span><small>ROLLBACK / STOP TRIGGER</small><b>Any worsening, contradiction, interlock or sensor-quality loss</b></span></div>
            </div>
            <footer><div><b>Validation was reused—not skipped.</b><span>Fast-path eligibility is withdrawn whenever context, evidence quality or authority changes.</span></div>{(responseMode === "automatic" || responseMode === "confirm") && stage === "detected" && <button onClick={runEarnedPath}>{responseMode === "automatic" ? "Run bounded recovery" : "Continue to bounded action"}</button>}{fastLaneAccepted && <strong className="fast-lane-status">{responseMode === "confirm" ? "No camera exceptions · local authorization required" : "Fast path admitted · post-change validation active"}</strong>}</footer>
          </section>

          <div className="workflow-card">
            <div className="workflow-head"><div><span className="eyebrow">{responseMode === "automatic" ? "PRE-APPROVED BOUNDED RESPONSE · CONTINUOUS VERIFICATION" : "GATED RESPONSE · HUMAN CONFIRMATION REQUIRED"}</span><h2>{responseMode === "automatic" ? "Qualify. Apply within bounds. Validate. Retain or roll back." : "Inspect. Record. Change locally. Validate. Release through site procedure."}</h2></div><span className="request-id">LA-2026-1842</span></div>
            <div className="steps">
              <Step active done label="Finding" detail={recovered ? "Recovery observed" : scenario.observed} number="01"/>
              <Step active={visionSorted} done={visionSorted} label="Vision analysis" detail="Complete · no exceptions" number="02"/>
              <Step active={["guided","changed","validated","released"].includes(stage)} done={["changed","validated","released"].includes(stage)} label="Local OEM action" detail={["changed","validated","released"].includes(stage) ? `${scenario.oldValue} → ${scenario.newValue}` : "Awaiting OEM confirmation"} number="03"/>
              <Step active={["changed","validated","released"].includes(stage)} done={["validated","released"].includes(stage)} label="Fresh evidence" detail={recovered ? "5 / 5 in envelope" : stage === "changed" ? `${cycles} / 5 observed` : "Blocked"} number="04"/>
              <Step active={["validated","released"].includes(stage)} done={stage === "released"} label="Factory release" detail={stage === "released" ? "Disposition recorded" : stage === "validated" ? "Site approval required" : "Not eligible"} number="05"/>
            </div>
            {stage === "inspection" && <div className="human-gate">
              <div><span className="gate-kicker">VISION GATE 01 · SYNCHRONIZED CAMERA EVIDENCE</span><b>{visionSorted ? "Visual conditions sorted automatically" : "Waiting for camera evidence"}</b><small>Camera-observed motion is compared with commissioned trajectories and PLC/photoeye timestamps. It does not establish hidden physical state, electrical integrity or release authority.</small><button className="virtual-review-button" onClick={() => openMachineFlow()}>{visionSorted ? "Review camera evidence & exceptions" : "Open degraded manual review"}</button></div>
              <div className="inspection-rollup vision-rollup"><span>CAMERA-CLASSIFIED FINDINGS · 3 / 3</span>{requiredInspectionPoints.map((point) => <p key={point}><b>{point}</b><small>{inspectionFindings[point] || "Evidence unavailable"}</small></p>)}{virtualInspectionComplete && <strong>{inspectionHeadline}</strong>}<em>Capture quality 96% · clock uncertainty ±3 ms · no occlusion</em></div>
              <label>Operator exception note<textarea value={inspectionNote} onChange={(event) => setInspectionNote(event.target.value)} placeholder="Record contradiction, occlusion, sound, contact or other non-visual evidence…"/></label>
            </div>}
            {stage === "guided" && <div className="human-gate local-gate">
              <div><span className="gate-kicker">OEM AUTHORITY HANDOFF · CONTROLLER GROUND TRUTH</span><b>Authoritative machine fields corroborated automatically</b><small>HMI commands, controller values, independent feedback and the commissioned profile agree. No repetitive field-opening task is required. LineAlert has not written to the controller.</small></div>
              <div className="setting-change"><span><small>Observed relationship</small><b>{scenario.injection} · {scenario.observed}</b></span><i>≠</i><span><small>Proposed OEM parameter</small><b>{scenario.parameter}: {scenario.oldValue} → {targetSetpointRecorded ? scenario.newValue : "not yet selected"}</b></span></div>
              <div className="ground-truth-progress auto-ground-truth"><b>Controller ground truth · {requiredOemFields.length}/{requiredOemFields.length} corroborated</b><span>{requiredOemFields.join(" · ")}</span><small>Automatic agreement is evidence of current readback and context—not proof that the proposed change will help.</small></div>
              <div className="direct-target"><span><small>AUTHORIZED LOCAL TARGET</small><b>{scenario.parameter}: {scenario.oldValue} → {scenario.newValue}</b><em>{scenario.direction}</em></span><button onClick={confirmOemChange}>Confirm OEM change & start 5-bottle test</button><small>The OEM console retains parameter authority, range enforcement and interlocks. Once its accepted change is detected, LineAlert starts fresh-outcome validation automatically.</small></div>
            </div>}
            {stage === "validated" && <div className="release-gate"><span className="gate-kicker">FACTORY PROCESS GATE</span><b>Technical recovery criteria satisfied—not yet released</b><small>OEM check passed · 5 fresh bottles within the commissioned envelope · camera outcome acceptable. Record the authorized disposition under the factory SOP, MES/QMS or supervisor workflow.</small></div>}
            {stage === "released" && <div className="release-gate released-gate"><span className="gate-kicker">FACTORY DISPOSITION RECORDED</span><b>Returned to production under site authority</b><small>LineAlert preserves the evidence package and approval record; it does not grant production authority.</small></div>}
            <div className="action-row">
              <div className="action-copy">
                {stage === "detected" && <><b>Camera analysis complete</b><span>Routine evidence was filtered automatically; only the bounded next action remains.</span></>}
                {stage === "inspection" && <><b>Review camera exceptions</b><span>Only contradictory, uncertain or non-visual observations require operator input.</span></>}
                {stage === "guided" && <><b>OEM-bounded intervention highlighted</b><span>{scenario.path} · local action only</span></>}
                {stage === "changed" && <><b>OEM diagnostic passed; local action logged</b><span>Validating the next five genuinely fresh outcomes…</span></>}
                {stage === "validated" && <><b className="helped">Technical recovery criteria satisfied</b><span>Awaiting the factory’s authorized release decision.</span></>}
                {stage === "released" && <><b className="helped">Factory disposition recorded</b><span>Evidence retained with source, operator input and fresh-cycle results.</span></>}
              </div>
              {stage !== "guided" && <button onClick={advance} disabled={stage === "changed" || (stage === "inspection" && !virtualInspectionComplete)}>
                {stage === "detected" && "Continue to bounded action"}
                {stage === "inspection" && "Accept camera findings & continue"}
                {stage === "changed" && `Observing ${cycles}/5`}
                {stage === "validated" && "Record factory disposition"}
                {stage === "released" && "Start new event"}
              </button>}
            </div>
          </div>
        </section>

        <aside className="oem-panel">
          <div className="oem-head"><div><span className="eyebrow">AUTHORITATIVE CONTROL</span><h2>LM-W200 HMI</h2></div><span className="readonly">LOCAL ACTION</span></div>
          <div className="machine-state"><span className="live-dot"/><div><b>Production running</b><small>Recipe 500 mL Spring Water</small></div></div>
          <div className="settings-list">
            {[{name:"Dispense position",value:"2.5 mm"},{name:"Peel plate position",value:"1.0 mm"},{name:"Product speed",value:"123 RPM"}].filter((item) => item.name !== scenario.parameter).map((item) => <Setting key={item.name} name={item.name} value={item.value} required={requiredOemFields.includes(item.name)} reviewed={(visionSorted && requiredOemFields.includes(item.name)) || reviewedOemFields.includes(item.name)} enabled={stage === "guided"} onOpen={reviewOemField}/>)}
            <Setting highlight={["guided","changed","validated","released"].includes(stage)} name={scenario.parameter} value={["changed","validated","released"].includes(stage) ? scenario.newValue : scenario.oldValue} required reviewed={visionSorted || reviewedOemFields.includes(scenario.parameter)} enabled={stage === "guided"} onOpen={reviewOemField}/>
            {[{name:"Merge sensor offset",value:"18 ms"},{name:"Vacuum level",value:"−12.0 inHg"},{name:"Rewind tension",value:"3.0 N"},{name:"Label feed delay",value:"145 ms"}].filter((item) => item.name !== scenario.parameter).map((item) => <Setting key={item.name} name={item.name} value={item.value} required={requiredOemFields.includes(item.name)} reviewed={(visionSorted && requiredOemFields.includes(item.name)) || reviewedOemFields.includes(item.name)} enabled={stage === "guided"} onOpen={reviewOemField}/>)}
          </div>
          {stage === "guided" && openOemField && <div className="oem-field-detail"><span>LOCAL FIELD EVIDENCE · {reviewedOemFields.includes(openOemField) ? "CORROBORATED" : "REVIEW REQUIRED"}</span><b>{openOemField}</b><small>Recipe 500 mL Spring Water · current controller context</small><div className="evidence-compare"><span><small>SOURCE A</small><b>{oemEvidence(openOemField).sourceA}</b></span><span><small>SOURCE B</small><b>{oemEvidence(openOemField).sourceB}</b></span><span><small>REFERENCE</small><b>{oemEvidence(openOemField).reference}</b></span></div><div className="bounded-evidence-result"><span><small>BOUNDED RESULT</small><b>{oemEvidence(openOemField).result}</b></span><span><small>DOES NOT ESTABLISH</small><b>{oemEvidence(openOemField).limitation}</b></span></div><button className={`corroborate-button ${reviewedOemFields.includes(openOemField) ? "recorded" : ""}`} onClick={() => confirmOemEvidence(openOemField)}>{reviewedOemFields.includes(openOemField) ? "Evidence result recorded ✓" : "Record corroborated ground truth"}</button>{openOemField === scenario.parameter && <div className="setpoint-review"><span><small>CURRENT READBACK</small><b>{scenario.oldValue}</b></span><span><small>COMMISSIONED RECIPE GUIDANCE</small><b>{scenario.direction}</b></span><span><small>HIGHEST-OVERLAP SUCCESS</small><b>{scenario.newValue} · precedent only</b></span><button disabled={!reviewedOemFields.includes(openOemField)} onClick={confirmOemChange}>Confirm OEM change & start 5-bottle test</button><em>The OEM console retains authority and interlocks; LineAlert begins validation after detecting the accepted change.</em></div>}</div>}
          {["guided","changed","validated","released"].includes(stage) && <div className="oem-callout"><b>{stage === "guided" ? "Field highlighted by advisory" : "OEM local diagnostic: PASS"}</b><span>{stage === "guided" ? "Operator must review and act locally." : "Interlocks satisfied · audit source: operator station 04"}</span></div>}
          <div className="machine-plate"><b>SPEEDWAY PACKAGING MACHINERY</b><span>LM-W150/200-SW · Canadian-built wrap labeler</span></div>
          <div className="authority-note"><b>LineAlert directs attention.</b><span>The Speedway machine interface retains parameter authority, range enforcement, interlocks, and operator confirmation.</span></div>
        </aside>
      </section>

      {showMachineFlow && <div className="flow-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) setShowMachineFlow(false); }}>
        <section className="flow-modal" role="dialog" aria-modal="true" aria-labelledby="machine-flow-title">
          <header className="flow-modal-head">
            <div><span className="eyebrow">EXPANDED MACHINE VIEW · CONCEPTUAL PROFILE</span><h2 id="machine-flow-title">{flowFocus === "aligner" ? "Where the bottle aligner sits" : "Two product lanes. One coordinated wrapper."}</h2><p>{flowFocus === "aligner" ? "The aligner guides and stabilizes each bottle at the wrapper approach." : "Follow the material path and see where the active relationship lives."}</p></div>
            <button className="flow-close" onClick={() => setShowMachineFlow(false)} aria-label="Close expanded machine flow">×</button>
          </header>

          <div className={`flow-canvas flow-fault-${activeFault} ${recovered ? "flow-recovered" : ""} ${flowFocus === "aligner" ? "focus-aligner" : ""} inspection-focus-${activeInspectionPoint ? requiredInspectionPoints.indexOf(activeInspectionPoint) + 1 : 0}`}>
            <div className="flow-legend"><span><i className="expected-key"/>Expected position</span><span><i className="observed-key"/>Observed bottle</span><span><i className="direct-dot"/>Direct signal</span><span><i className="inferred-dot"/>Inferred relationship</span><span><i className="drift-dot"/>Active drift</span></div>
            <div className="flow-lane flow-lane-a"><b>LANE A</b><small>Product handling</small><div className="flow-track"/>{[0,1,2].map((item) => <i className={`expected-bottle eb-a-${item}`} key={`ea-${item}`}/>) }{[0,1,2].map((item) => <i className={`flow-bottle fb-a-${item}`} key={`a-${item}`}/>)}</div>
            <div className="flow-lane flow-lane-b"><b>LANE B</b><small>Product handling</small><div className="flow-track"/>{[0,1,2].map((item) => <i className={`expected-bottle eb-b-${item}`} key={`eb-${item}`}/>) }{[0,1,2].map((item) => <i className={`flow-bottle fb-b-${item}`} key={`b-${item}`}/>)}{activeFault === "alignment" && !recovered && <div className="phase-delta-marker"><b>+42 ms</b><span>observed behind expected</span></div>}</div>
            <div className="flow-merge"><span>MERGE</span><b>Arrival coordination</b><small>Direct timing · commissioned spacing</small><i className="merge-light"/><div className="photoeye-sensor" aria-label="Merge photoeye detection"><span className="sensor-body"><i/><b>S1</b></span><span className="sensor-beam"/><span className="detection-zone"><i className="detection-bottle"/></span><strong>DETECT</strong><em>PHOTOEYE BEAM</em></div></div>
            <div className="flow-link merge-link"><i/></div>
            <div className="flow-station wrapper-station"><span>WRAPPER</span><b>Label application</b><small>Feed · alignment · contact</small><div className="aligner-assembly" aria-label="Bottle aligner and stabilizer belts"><em>ALIGNER</em><i className="aligner-belt aligner-top"/><i className="aligner-bottle"/><i className="aligner-belt aligner-bottom"/><span className="aligner-motion">BELT MOTION →</span></div></div>
            <div className="flow-link camera-link"><i/></div>
            <div className="flow-station camera-station"><span>CAMERA</span><b>{recovered ? "Outcome accepted" : scenario.title}</b><small>{recovered ? "5 bottles within tolerance" : scenario.observed}</small><i className="camera-eye">◉</i></div>
            <div className="flow-pulse-path"/>
            {stage === "inspection" && <div className="inspection-hotspots" aria-label="Virtual physical inspection points">
              {requiredInspectionPoints.map((point, index) => <button key={point} className={`inspection-hotspot hotspot-${index + 1} ${virtualInspected.includes(point) ? "inspected" : ""} ${activeInspectionPoint === point ? "active" : ""}`} onClick={() => setActiveInspectionPoint(point)}><i>{virtualInspected.includes(point) ? "✓" : index + 1}</i><span>{point}</span><small>{virtualInspected.includes(point) ? inspectionFindings[point] : "Open inspection"}</small></button>)}
              {activeInspectionPoint && <div className={`inspection-motion-cue cue-${requiredInspectionPoints.indexOf(activeInspectionPoint) + 1}`}><i>→</i><span>WATCH THIS MOTION</span></div>}
            </div>}
          </div>

          {stage === "inspection" && <div className="virtual-inspection-tray">
            <div className="inspection-guide"><span className="eyebrow">{visionSorted ? "SYNCHRONIZED VISION REVIEW · EXCEPTION HANDLING" : "DEGRADED MANUAL REVIEW · DEMO EVIDENCE"}</span>{activeGuidance && activeInspectionPoint ? <><b>{activeInspectionPoint}: what evidence was classified?</b><p>{activeGuidance.watch}</p><div className="normal-abnormal"><span><small>NORMAL LOOKS LIKE</small>{activeGuidance.normal}</span><span><small>ABNORMAL LOOKS LIKE</small>{activeGuidance.abnormal}</span></div><label>{visionSorted ? "Override only when current evidence contradicts the camera" : "Record what the animation supports"}<select value={inspectionFindings[activeInspectionPoint] || ""} onChange={(event) => recordVirtualFinding(activeInspectionPoint, event.target.value)}><option value="">Choose an observation…</option>{activeGuidance.options.map((option) => <option key={option}>{option}</option>)}</select></label></> : <><b>Select a numbered evidence point</b><p>{visionSorted ? "Review the camera classification, synchronized timing and any visible exception." : "The animation will isolate its motion and explain what evidence to look for."}</p></>}</div>
            <div className="inspection-checklist"><b>{virtualInspected.length} / {requiredInspectionPoints.length} findings recorded</b>{requiredInspectionPoints.map((point) => <button className={`${virtualInspected.includes(point) ? "reviewed" : ""} ${activeInspectionPoint === point ? "active" : ""}`} onClick={() => setActiveInspectionPoint(point)} key={point}>{virtualInspected.includes(point) ? "✓" : "○"} {point}<small>{inspectionFindings[point] || "No finding yet"}</small></button>)}</div>
            {virtualInspectionComplete && <div className="inspection-summary"><span><small>WHAT THIS SUPPORTS</small><b>{Object.values(inspectionFindings).some((value) => /delayed|drag|unstable|inconsistent|obstruction|abnormal/i.test(value)) ? "The virtual review identified a visible condition requiring current-event investigation." : "No visible mechanical obstruction was identified in the reviewed animation."}</b></span><span><small>WHAT THIS DOES NOT ESTABLISH</small><b>Physical machine condition, sensor calibration and actuator timing remain unverified.</b></span><span><small>NEXT GATE</small><b>Open the required OEM fields and establish controller ground truth.</b></span></div>}
          </div>}

          <div className="coordination-strip" aria-label="Coordinated process relationships">
            <div className={feedRatio < .98 || feedRatio > 1.02 ? "coord-alert" : ""}><span>01 · SPEED MATCH</span><b>Feed / wrapper {feedRatio.toFixed(3)}</b><small>{feedRatio < .98 || feedRatio > 1.02 ? "Outside bound: 0.980–1.020 ratio" : "Within bound: 0.980–1.020 ratio"}</small></div>
            <div className={Math.abs(arrival) > 20 && !recovered ? "coord-alert" : ""}><span>02 · ARRIVAL PHASE</span><b>{arrival >= 0 ? "+" : ""}{arrival.toFixed(0)} ms at wrapper entry</b><small>{Math.abs(arrival) > 20 && !recovered ? "Outside bound: −20 to +20 ms · first observed drift" : "Within bound: −20 to +20 ms"}</small></div>
            <div className={cycleMargin < 180 && !recovered ? "coord-alert" : ""}><span>03 · CYCLE MARGIN</span><b>{cycleMargin.toFixed(0)} ms between cycles</b><small>{cycleMargin < 180 && !recovered ? "Outside bound: at least 180 ms" : "Within bound: at least 180 ms to complete cycle"}</small></div>
          </div>

          {flowFocus === "aligner" && <div className="component-explainer">
            <div className="component-tag"><span>COMPONENT 04</span><b>Bottle aligner / stabilizer belts</b></div>
            <p><b>What it does:</b> Side belts or rollers guide and stabilize the bottle as it enters the label-application zone. Depending on the commissioned machine design, they may also control bottle rotation.</p>
            <p><b>Why speed matters:</b> Its surface speed must stay coordinated with conveyor movement, bottle presentation and the selected product recipe. The expected relationship is machine-specific—not automatically 1:1.</p>
            <div className="topology-path" aria-label="Machine topology path"><span>INFEED &amp; SPACING</span><i>→</i><span>MERGE</span><i>→</i><strong>ALIGNER</strong><i>→</i><span>LABEL CONTACT</span><i>→</i><span>CAMERA</span></div>
          </div>}

          <div className="flow-explanation">
            <div><span className="eyebrow">ACTIVE RELATIONSHIP</span><b>{recovered ? "Machine relationships returned to their commissioned envelopes" : scenario.keyPoint}</b><small>{recovered ? "Fresh camera evidence confirms five acceptable outcomes." : "The highlighted route is a bounded troubleshooting candidate—not proof of root cause."}</small></div>
            <div className="flow-source-card"><span>Signal binding</span><b>{scenario.parameter}</b><small>Machine-profile source · {activeFault === "alignment" || activeFault === "multiple" ? "timing relationship" : "wrapper station"}</small></div>
            <button onClick={() => { setShowMachineFlow(false); setShowWhy(true); setReasonDepth(Math.max(reasonDepth, 2)); }}>Continue into the reasoning →</button>
          </div>
        </section>
      </div>}

      <footer><span>Independent LineAlert concept visualization · Not an official Speedway product or endorsement</span><span>Read-only telemetry · Advisory integration · No autonomous equipment control</span></footer>
    </main>
  );
}

function Step({ active, done, label, detail, number }: { active: boolean; done: boolean; label: string; detail: string; number: string }) {
  return <div className={`step ${active ? "active" : ""}`}><span className="step-num">{done ? "✓" : number}</span><div><b>{label}</b><small>{detail}</small></div></div>;
}
function Setting({ name, value, highlight = false, required = false, reviewed = false, enabled = false, onOpen }: { name: string; value: string; highlight?: boolean; required?: boolean; reviewed?: boolean; enabled?: boolean; onOpen?: (field: string) => void }) {
  return <button type="button" className={`setting ${highlight ? "highlight" : ""} ${required ? "required-setting" : ""} ${reviewed ? "reviewed-setting" : ""}`} disabled={!enabled} onClick={() => onOpen?.(name)}><span>{name}{required && <small>{reviewed ? "AUTO-CORROBORATED" : "EVIDENCE UNAVAILABLE"}</small>}</span><b>{value}</b>{highlight && <em>{reviewed ? "CORROBORATED" : "REVIEW"}</em>}</button>;
}
function HistoryCase({ score, id, date, action, result, overlap, difference }: { score:string; id:string; date:string; action:string; result:string; overlap:string; difference:string }) {
  return <article className="history-case"><div className="match-score"><b>{score}</b><small>case similarity</small></div><div className="case-main"><span>{id} · {date}</span><b>{action}</b><small>Historical outcome: <strong className={result === "HELPED" ? "helped" : "inconclusive"}>{result}</strong></small></div><div className="case-comparison"><span><i>✓</i><b>Overlap</b>{overlap}</span><span><i>△</i><b>Differences</b>{difference}</span></div></article>;
}
function EvidenceGauge({label,value,unit,quality}:{label:string;value:number;unit:string;quality:string}) {
  const display = Number.isFinite(value) ? (Math.abs(value) >= 1000 ? Math.round(value).toString() : value.toFixed(1)) : "—";
  return <div className="evidence-gauge"><div className="gauge-arc"><i style={{transform:`rotate(${Math.max(-115,Math.min(115,(Math.abs(value)%100)/100*230-115))}deg)`}}/></div><span><small>{label}</small><b>{display} <em>{unit}</em></b><i className={`quality-${quality}`}>{quality}</i></span></div>;
}
