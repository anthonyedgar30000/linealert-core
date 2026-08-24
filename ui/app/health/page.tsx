"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import coreEvidenceFixture from "./core-condition-evidence.json";
import styles from "./health.module.css";
import sourceStyles from "./source.module.css";

type HealthStatus = "HEALTHY" | "DRIFTING" | "ATTENTION";
type EvidenceSignal = { value: number | null; unit: string; quality: string };
type TelemetrySnapshot = {
  connected: boolean;
  source_id?: string;
  source_kind?: string;
  asset_id?: string;
  reason_code?: string;
  signals?: Record<string, EvidenceSignal>;
};
type HistoryPayload = {
  persistence: string;
  count: number;
  observations: TelemetrySnapshot[];
};
type HealthState = {
  label: string;
  status: HealthStatus;
  rollingAverage: number;
  trendPercent: number;
  violations: number;
  note: string;
};
type CoreEvidenceObservation = {
  signal: string;
  value: number;
  unit: string;
  min_value: number;
  max_value: number;
  asset_id: string;
  correlation_id: string;
  start_event_id: string | null;
  end_event_id: string | null;
  start_source_id: string | null;
  end_source_id: string | null;
  topology_from: string;
  topology_to: string;
  temporal_rule_status: string;
  semantic: string;
  quality: string;
  reason_code: string;
  provenance: string;
};
type ClockEvidence = {
  start_clock_quality: string;
  end_clock_quality: string;
  basis: string;
  retained_uncertainty: string;
};
type RuntimeConditionObservation = CoreEvidenceObservation & {
  observation_id: string;
  relationship_id: string;
  clock_evidence?: ClockEvidence;
};
type ConditionRuntimePayload = {
  configured: boolean;
  running: boolean;
  source_mode: string;
  measurement_count: number;
  refusal_count: number;
  reason_code?: string;
  condition?: {
    claim_boundary?: string;
    condition_signals?: {
      count: number;
      observations: RuntimeConditionObservation[];
    };
  } | null;
};

const coreEvidence = coreEvidenceFixture.observations[0] as CoreEvidenceObservation;
const conditionSignalName = coreEvidence.signal;

const demoStates: HealthState[] = [
  { label: "Day 1", status: "HEALTHY", rollingAverage: 250, trendPercent: 0, violations: 0, note: "Simulated timing is stable inside the commissioned presentation envelope." },
  { label: "Day 3", status: "HEALTHY", rollingAverage: 275, trendPercent: 10, violations: 0, note: "Small simulated movement is visible, but the relationship remains inside its commissioned envelope." },
  { label: "Day 7", status: "DRIFTING", rollingAverage: 360, trendPercent: 44, violations: 1, note: "The simulated relationship has crossed the upper envelope. This is a UI scenario, not runtime machine evidence." },
  { label: "Day 10", status: "DRIFTING", rollingAverage: 430, trendPercent: 72, violations: 3, note: "Repeated simulated violations illustrate condition degradation without claiming a root cause or future failure." },
  { label: "Day 12", status: "ATTENTION", rollingAverage: 550, trendPercent: 120, violations: 8, note: "The simulated relationship is repeatedly outside its commissioned envelope and would warrant investigation." },
];

const seriesByState = [
  [240, 245, 250],
  [240, 245, 250, 260, 275],
  [240, 245, 250, 260, 275, 300, 330, 360],
  [240, 245, 250, 260, 275, 300, 330, 360, 390, 430],
  [240, 245, 250, 260, 275, 300, 330, 360, 390, 430, 480, 520, 550],
];

const average = (values: number[]) =>
  values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;

const signalSeries = (history: HistoryPayload | null, name: string) =>
  history?.observations.flatMap((observation) => {
    const signal = observation.signals?.[name];
    if (
      !signal ||
      signal.quality !== "good" ||
      typeof signal.value !== "number" ||
      !Number.isFinite(signal.value)
    ) {
      return [];
    }
    return [signal.value];
  }) ?? [];

const formatSignal = (signal: EvidenceSignal | undefined) => {
  if (!signal || typeof signal.value !== "number" || !Number.isFinite(signal.value)) return "—";
  const digits = Math.abs(signal.value) >= 100 ? 0 : 1;
  return `${signal.value.toFixed(digits)} ${signal.unit}`;
};

const historyMode = (value: string | undefined) => {
  if (value === "jsonl_capture") return "JSONL capture + recent buffer";
  if (value === "deterministic_replay") return "Deterministic replay history";
  if (value === "memory_only") return "Recent memory buffer";
  return "History unavailable";
};

const sourceModeLabel = (value: string | undefined) => {
  if (value === "deterministic_event_replay") return "Deterministic event replay";
  if (value === "live_event_stream") return "Live admitted event stream";
  if (value === "unconfigured") return "Not configured";
  if (value === "unavailable") return "Unavailable";
  return value ? value.replaceAll("_", " ") : "Unavailable";
};

export default function MachineHealthPage() {
  const [demoIndex, setDemoIndex] = useState(3);
  const [telemetry, setTelemetry] = useState<TelemetrySnapshot | null>(null);
  const [history, setHistory] = useState<HistoryPayload | null>(null);
  const [conditionRuntime, setConditionRuntime] = useState<ConditionRuntimePayload | null>(null);
  const [telemetryReachable, setTelemetryReachable] = useState(false);
  const [historyReachable, setHistoryReachable] = useState(false);
  const [conditionReachable, setConditionReachable] = useState(false);

  useEffect(() => {
    let active = true;

    const readTelemetry = async () => {
      try {
        const response = await fetch("/api/telemetry", { cache: "no-store" });
        if (!response.ok) throw new Error("telemetry unavailable");
        const payload = (await response.json()) as TelemetrySnapshot;
        if (active) {
          setTelemetry(payload);
          setTelemetryReachable(true);
        }
      } catch {
        if (active) setTelemetryReachable(false);
      }
    };

    const readHistory = async () => {
      try {
        const response = await fetch("/api/history?limit=480", { cache: "no-store" });
        if (!response.ok) throw new Error("history unavailable");
        const payload = (await response.json()) as HistoryPayload;
        if (active) {
          setHistory(payload);
          setHistoryReachable(true);
        }
      } catch {
        if (active) setHistoryReachable(false);
      }
    };

    const readCondition = async () => {
      try {
        const response = await fetch("/api/condition", { cache: "no-store" });
        if (!response.ok) throw new Error("condition runtime unavailable");
        const payload = (await response.json()) as ConditionRuntimePayload;
        if (active) {
          setConditionRuntime(payload);
          setConditionReachable(true);
        }
      } catch {
        if (active) setConditionReachable(false);
      }
    };

    readTelemetry();
    readHistory();
    readCondition();
    const telemetryTimer = setInterval(readTelemetry, 1000);
    const historyTimer = setInterval(readHistory, 3000);
    const conditionTimer = setInterval(readCondition, 1000);
    return () => {
      active = false;
      clearInterval(telemetryTimer);
      clearInterval(historyTimer);
      clearInterval(conditionTimer);
    };
  }, []);

  const conditionObservations = useMemo(
    () =>
      conditionRuntime?.condition?.condition_signals?.observations.filter(
        (observation) =>
          observation.signal === conditionSignalName &&
          observation.quality === "good" &&
          Number.isFinite(observation.value),
      ) ?? [],
    [conditionRuntime],
  );
  const conditionSeries = useMemo(
    () => conditionObservations.map((observation) => observation.value),
    [conditionObservations],
  );
  const latestRuntimeEvidence = conditionObservations.at(-1);
  const displayEvidence = latestRuntimeEvidence ?? coreEvidence;
  const baselineLow = displayEvidence.min_value;
  const baselineHigh = displayEvidence.max_value;
  const baselineUnit = displayEvidence.unit;
  const relationshipLabel = `${displayEvidence.topology_from} → ${displayEvidence.topology_to}`;
  const conditionEvidenceAvailable = conditionSeries.length > 0;
  const conditionTrendAvailable = conditionSeries.length >= 5;
  const arrivalSeries = useMemo(() => signalSeries(history, "arrival_ms"), [history]);

  const runtimeState = useMemo<HealthState>(() => {
    const recent = conditionSeries.slice(-20);
    const first = conditionSeries.slice(0, Math.min(20, conditionSeries.length));
    const rollingAverage = average(recent);
    const startingAverage = average(first) || rollingAverage;
    const trendPercent = conditionSeries.length >= 2 && startingAverage
      ? ((rollingAverage - startingAverage) / startingAverage) * 100
      : 0;
    const violations = conditionSeries
      .slice(-120)
      .filter((value) => value < baselineLow || value > baselineHigh).length;
    const deviation = rollingAverage < baselineLow || rollingAverage > baselineHigh;
    const severe = rollingAverage > baselineHigh + 20 || rollingAverage < baselineLow - 20;
    const persistent = conditionTrendAvailable && violations >= 3;
    const status: HealthStatus = persistent && (severe || violations >= 10)
      ? "ATTENTION"
      : deviation
        ? "DRIFTING"
        : "HEALTHY";
    return {
      label: "Runtime condition evidence",
      status,
      rollingAverage,
      trendPercent,
      violations,
      note: conditionTrendAvailable
        ? status === "HEALTHY"
          ? "The admitted event relationship remains inside its commissioned envelope across the runtime history window."
          : "Repeated runtime measurements are outside the commissioned envelope. This establishes relationship degradation, not physical root cause or future failure."
        : deviation
          ? "A runtime event relationship is outside its commissioned envelope. More repeated measurements are required before calling the deviation persistent degradation."
          : "Runtime evidence is inside the commissioned envelope, but more repeated measurements are required before making a trend claim.",
    };
  }, [baselineHigh, baselineLow, conditionSeries, conditionTrendAvailable]);

  const state = conditionEvidenceAvailable ? runtimeState : demoStates[demoIndex];
  const chartSeries = useMemo(
    () => conditionEvidenceAvailable ? conditionSeries.slice(-80) : seriesByState[demoIndex],
    [conditionEvidenceAvailable, conditionSeries, demoIndex],
  );
  const bridgeConnected = Boolean(telemetryReachable && telemetry?.connected);
  const runtimeConfigured = Boolean(conditionReachable && conditionRuntime?.configured);

  const chart = useMemo(() => {
    const series = chartSeries.length ? chartSeries : [baselineLow, baselineHigh];
    const width = 700;
    const height = 250;
    const paddingX = 34;
    const paddingY = 24;
    const observedMin = Math.min(baselineLow, ...series);
    const observedMax = Math.max(baselineHigh, ...series);
    const span = Math.max(observedMax - observedMin, 40);
    const margin = Math.max(10, span * 0.12);
    const min = observedMin - margin;
    const max = observedMax + margin;
    const denominator = Math.max(series.length - 1, 1);
    const x = (index: number) => paddingX + (index / denominator) * (width - paddingX * 2);
    const y = (value: number) =>
      paddingY + ((max - value) / (max - min)) * (height - paddingY * 2);
    const ticks = Array.from(new Set([baselineLow, baselineHigh, Math.round(max)]))
      .sort((left, right) => left - right)
      .map((value) => ({ value, y: y(value) }));
    return {
      width,
      height,
      points: series.map((value, index) => `${x(index)},${y(value)}`).join(" "),
      baselineTop: y(baselineHigh),
      baselineBottom: y(baselineLow),
      currentX: x(series.length - 1),
      currentY: y(series[series.length - 1]),
      ticks,
    };
  }, [baselineHigh, baselineLow, chartSeries]);

  const deviationDetected =
    state.rollingAverage < baselineLow || state.rollingAverage > baselineHigh;
  const conditionDegradation = conditionEvidenceAvailable
    ? conditionTrendAvailable && runtimeState.violations >= 3
    : demoIndex >= 2;
  const trendLabel = conditionEvidenceAvailable && !conditionTrendAvailable
    ? "—"
    : `${state.trendPercent >= 0 ? "+" : ""}${state.trendPercent.toFixed(conditionEvidenceAvailable ? 1 : 0)}%`;
  const runtimeMode = sourceModeLabel(conditionRuntime?.source_mode);
  const runtimeIsReplay = conditionRuntime?.source_mode === "deterministic_event_replay";

  return (
    <main className={styles.shell}>
      <header className={styles.topbar}>
        <div>
          <Link className={styles.backLink} href="/">← Operator / troubleshooting view</Link>
          <p className={styles.eyebrow}>LINEALERT · CONDITION MONITORING PROTOTYPE</p>
          <h1>Machine Health — Label Application Station</h1>
          <p className={styles.subtitle}>
            Track coordinated machine relationships against a commissioned baseline and surface meaningful deviation before it becomes an obvious fault.
          </p>
        </div>
        <div className={styles.demoFlag}>
          <b>{conditionEvidenceAvailable ? (runtimeIsReplay ? "CONDITION REPLAY EVIDENCE" : "RUNTIME CONDITION EVIDENCE") : bridgeConnected ? "LIVE TELEMETRY + SIMULATED CONDITION" : "SIMULATED CONDITION HISTORY"}</b>
          <span>{conditionEvidenceAvailable ? `${runtimeMode} is driving the measured relationship view. No physical root cause or future failure is claimed.` : bridgeConnected ? "Raw telemetry is live context, but it is not promoted into the condition relationship without admitted correlated events." : "No production failure prediction is claimed."}</span>
        </div>
      </header>

      <section className={styles.statusRow} aria-label="Machine health summary">
        <article className={`${styles.healthCard} ${styles[state.status.toLowerCase()]}`}>
          <span>STATION HEALTH</span><strong>{state.status}</strong>
          <small>{conditionEvidenceAvailable ? `${conditionSeries.length} runtime measurement${conditionSeries.length === 1 ? "" : "s"}` : `${state.label} · simulated condition history`}</small>
        </article>
        <article className={styles.metricCard}>
          <span>MONITORED RELATIONSHIP</span><strong>{relationshipLabel}</strong>
          <small>Commissioned envelope {baselineLow}–{baselineHigh} {baselineUnit}</small>
        </article>
        <article className={styles.metricCard}>
          <span>CURRENT ROLLING AVERAGE</span><strong>{state.rollingAverage.toFixed(conditionEvidenceAvailable ? 1 : 0)} ms</strong>
          <small>{deviationDetected ? "Outside commissioned baseline" : "Inside commissioned baseline"}</small>
        </article>
        <article className={styles.metricCard}>
          <span>{conditionEvidenceAvailable ? "RUNTIME TREND" : "SIMULATED TREND"}</span><strong>{trendLabel}</strong>
          <small>{conditionEvidenceAvailable && !conditionTrendAvailable ? `${conditionSeries.length}/5 measurements collected before trend interpretation` : "Direction matters before a hard alarm does"}</small>
        </article>
        <article className={styles.metricCard}>
          <span>ENVELOPE VIOLATIONS</span><strong>{state.violations} {conditionEvidenceAvailable ? "runtime" : "simulated"}</strong>
          <small>Repeated observations, not a root-cause claim</small>
        </article>
        <article className={styles.metricCard}>
          <span>LAST MAINTENANCE CONTEXT</span><strong>{conditionEvidenceAvailable ? "Not connected" : "Feed roller cleaned"}</strong>
          <small>{conditionEvidenceAvailable ? "Maintenance outcomes remain the next evidence integration" : "18 days ago · simulated work history"}</small>
        </article>
      </section>

      <section className={sourceStyles.sourcePanel} aria-label="Telemetry, runtime condition evidence, and history context">
        <div className={sourceStyles.sourceHeader}>
          <div>
            <p className={sourceStyles.eyebrow}>EVIDENCE CONTEXT</p>
            <h2>Runtime condition evidence now sits beside raw bridge telemetry</h2>
            <p>{conditionEvidenceAvailable ? `The condition API has published ${conditionSeries.length} admitted measurement${conditionSeries.length === 1 ? "" : "s"} for ${relationshipLabel}. ${runtimeIsReplay ? "The source is explicitly deterministic event replay, not current physical-machine telemetry." : "The source mode is retained with the measurement evidence."}` : "The CI-verified replay evidence below demonstrates the exact event relationship contract. Raw OPC UA proxies remain context until admitted machine events complete that relationship at runtime."}</p>
          </div>
          <span className={`${sourceStyles.sourceState} ${conditionEvidenceAvailable || bridgeConnected ? sourceStyles.sourceLive : sourceStyles.sourceDemo}`}><i/>{conditionEvidenceAvailable ? "CONDITION API ACTIVE" : bridgeConnected ? "BRIDGE CONNECTED" : "DEMO FALLBACK"}</span>
        </div>

        <div className={sourceStyles.coreEvidenceCard}>
          <div className={sourceStyles.coreEvidenceIdentity}>
            <span>{conditionEvidenceAvailable ? "RUNTIME CONDITION EVIDENCE" : "CORE REPLAY EVIDENCE · CI-VERIFIED"}</span>
            <b>{displayEvidence.topology_from} → {displayEvidence.topology_to}</b>
            <small>{displayEvidence.semantic}</small>
          </div>
          <div className={sourceStyles.coreEvidenceMetric}>
            <span>MEASURED DELAY</span>
            <b>{displayEvidence.value.toFixed(0)} {displayEvidence.unit}</b>
            <small>{displayEvidence.correlation_id} · {displayEvidence.quality} evidence</small>
          </div>
          <div className={sourceStyles.coreEvidenceMetric}>
            <span>APPROVED ENVELOPE</span>
            <b>{displayEvidence.min_value.toFixed(0)}–{displayEvidence.max_value.toFixed(0)} {displayEvidence.unit}</b>
            <small>Temporal status: {displayEvidence.temporal_rule_status.toUpperCase()}</small>
          </div>
          <div className={sourceStyles.coreEvidenceMetric}>
            <span>TREND</span>
            <b>{conditionTrendAvailable ? `${conditionSeries.length} measurements` : "Not yet inferred"}</b>
            <small>{conditionTrendAvailable ? "Repeated runtime history is available for bounded trend interpretation." : "One or a few measured cycles establish deviation only, not persistent degradation."}</small>
          </div>
        </div>
        <div className={sourceStyles.coreEvidenceProvenance}>
          <b>Provenance:</b> {displayEvidence.start_event_id} ({displayEvidence.start_source_id}) → {displayEvidence.end_event_id} ({displayEvidence.end_source_id}) · {displayEvidence.provenance}.{latestRuntimeEvidence?.clock_evidence ? ` Clock basis: ${latestRuntimeEvidence.clock_evidence.basis}.` : " This checked-in replay evidence is not current physical-machine telemetry."}
        </div>

        <div className={sourceStyles.sourceGrid}>
          <div className={`${sourceStyles.sourceCard} ${bridgeConnected ? sourceStyles.sourceGood : sourceStyles.sourceWarn}`}>
            <span>TELEMETRY SOURCE</span><b>{bridgeConnected ? `${telemetry?.asset_id ?? "asset"} · ${telemetry?.source_kind ?? "source"}` : "Unavailable"}</b>
            <small>{telemetry?.reason_code ?? "The condition demo remains usable without the raw telemetry bridge."}</small>
          </div>
          <div className={`${sourceStyles.sourceCard} ${historyReachable ? sourceStyles.sourceGood : sourceStyles.sourceWarn}`}>
            <span>TELEMETRY HISTORY</span><b className={sourceStyles.historianStatus}><i className={sourceStyles.historianDot}/>{history?.count ?? 0} snapshots</b>
            <small>{historyMode(history?.persistence)}</small>
          </div>
          <div className={`${sourceStyles.sourceCard} ${runtimeConfigured ? sourceStyles.sourceGood : sourceStyles.sourceWarn}`}>
            <span>CONDITION EVENT STREAM</span><b>{runtimeConfigured ? runtimeMode : "Not configured"}</b>
            <small>{conditionRuntime?.reason_code ?? "No condition-event runtime is reachable."}</small>
            <em className={`${sourceStyles.bindingBadge} ${conditionEvidenceAvailable ? sourceStyles.liveBadge : sourceStyles.disabledBadge}`}>{conditionEvidenceAvailable ? "RUNTIME EVIDENCE AVAILABLE" : "NO CONDITION MEASUREMENT"}</em>
          </div>
          <div className={sourceStyles.sourceCard}>
            <span>CONDITION HISTORY</span><b>{conditionRuntime?.measurement_count ?? 0} measurements</b>
            <small>{conditionRuntime?.refusal_count ?? 0} timing promotion refusals · {conditionTrendAvailable ? "trend window available" : "trend not yet earned"}</small>
          </div>
        </div>

        <div className={sourceStyles.signalGrid}>
          <div className={sourceStyles.signalCard}><span>MOTOR SPEED PROXY</span><b className={sourceStyles.signalValue}>{formatSignal(telemetry?.signals?.rpm)}</b><small>{telemetry?.signals?.rpm?.quality ?? "no current sample"}</small></div>
          <div className={sourceStyles.signalCard}><span>DERIVED CONVEYOR ARRIVAL PROXY</span><b className={sourceStyles.signalValue}>{formatSignal(telemetry?.signals?.arrival_ms)}</b><small>{arrivalSeries.length} qualified samples retained</small></div>
          <div className={sourceStyles.signalCard}><span>CONTACT PRESSURE PROXY</span><b className={sourceStyles.signalValue}>{formatSignal(telemetry?.signals?.pressure_psi)}</b><small>{telemetry?.signals?.pressure_psi?.quality ?? "no current sample"}</small></div>
        </div>

        <div className={sourceStyles.sourceBoundary}>
          <b>Binding boundary:</b> simulator RPM, derived arrival timing, pressure, and other convenient proxies do not become {conditionSignalName}. The condition API publishes that relationship only after the deterministic core admits and correlates the configured machine events; replay sources remain labeled as replay.
        </div>
        <div className={sourceStyles.historyNote}>{history?.persistence === "jsonl_capture" ? "Durable JSONL telemetry capture is enabled; the dashboard exposes a bounded recent window from that observation stream." : "Recent raw telemetry history is memory-backed. Start the bridge with --capture-jsonl to retain those observations durably for replay and analysis."}</div>
      </section>

      <section className={styles.mainGrid}>
        <article className={styles.panel}>
          <div className={styles.panelHeader}>
            <div><p className={styles.eyebrow}>RELATIONSHIP CONDITION</p><h2>{conditionEvidenceAvailable ? "Runtime event relationship against commissioned envelope" : "Simulated relationship moving away from baseline"}</h2></div>
            <div className={styles.legend}><span><i className={styles.baselineKey}/> Commissioned envelope</span><span><i className={styles.trendKey}/> Measured delay</span></div>
          </div>
          <div className={styles.chartWrap}>
            <svg viewBox={`0 0 ${chart.width} ${chart.height}`} role="img" aria-label={conditionEvidenceAvailable ? "Runtime condition relationship measurements" : `Simulated response-time trend through ${state.label}`}>
              <rect x="34" y={chart.baselineTop} width="632" height={chart.baselineBottom - chart.baselineTop} className={styles.baselineBand} rx="8"/>
              {chart.ticks.map((tick) => <g key={tick.value}><line x1="34" y1={tick.y} x2="666" y2={tick.y} className={styles.gridLine}/><text x="2" y={tick.y + 4} className={styles.axisText}>{tick.value} ms</text></g>)}
              <polyline points={chart.points} className={styles.trendLine}/>
              <circle cx={chart.currentX} cy={chart.currentY} r="7" className={styles.currentPoint}/>
              <text x={Math.max(34, chart.currentX - 46)} y={chart.currentY - 14} className={styles.currentLabel}>{state.rollingAverage.toFixed(conditionEvidenceAvailable ? 1 : 0)} ms</text>
              <text x="34" y="244" className={styles.axisText}>{conditionEvidenceAvailable ? "First runtime measurement" : "Commissioned start"}</text>
              <text x="570" y="244" className={styles.axisText}>{conditionEvidenceAvailable ? "Latest runtime measurement" : state.label}</text>
            </svg>
          </div>
          {!conditionEvidenceAvailable && <div className={styles.timelineControls}>{demoStates.map((item, index) => <button key={item.label} className={index === demoIndex ? styles.activeTimelineButton : ""} onClick={() => setDemoIndex(index)}><span>{item.label}</span><b>{item.rollingAverage} ms</b></button>)}</div>}
          <div className={styles.interpretation}><span>WHAT LINEALERT CAN ESTABLISH AT THIS STAGE</span><b>{state.note}</b></div>
        </article>

        <aside className={styles.sideColumn}>
          <article className={styles.panel}>
            <p className={styles.eyebrow}>MEASURED RELATIONSHIP</p><h2>Where the timing evidence lives</h2>
            <div className={styles.processFlow}><div><span>CMD</span><b>Label feed command</b><small>Configured start event</small></div><i>→</i><div className={styles.activeNode}><span>Δt</span><b>Presentation window</b><small>{baselineLow}–{baselineHigh} ms expected</small></div><i>→</i><div><span>S2</span><b>Label at peel point</b><small>Configured end event</small></div><i>→</i><div><span>QA</span><b>Inspection</b><small>Outcome retained separately</small></div></div>
            <p className={styles.boundaryCopy}>LineAlert is measuring the relationship between admitted events. It is not claiming that the servo, web tension, peel plate, PLC logic, sensor, or another component is the physical root cause.</p>
          </article>
          <article className={styles.panel}>
            <p className={styles.eyebrow}>MATURITY GATES</p><h2>Earn the predictive claim</h2>
            <div className={styles.gates}>
              <div className={deviationDetected ? styles.gatePass : styles.gatePending}><span>01</span><b>Deviation detected</b><small>{deviationDetected ? "Observed relationship is outside the commissioned envelope." : "No current envelope violation is established."}</small></div>
              <div className={conditionDegradation ? styles.gatePass : styles.gatePending}><span>02</span><b>Condition degradation detected</b><small>{conditionDegradation ? "Deviation persists across repeated admitted relationship measurements." : "More repeated runtime history is required before calling this persistent degradation."}</small></div>
              <div className={styles.gatePending}><span>03</span><b>Failure prediction validated</b><small>Not yet established. Requires real maintenance outcomes and repeatable predictive value.</small></div>
            </div>
          </article>
        </aside>
      </section>

      <section className={styles.lowerGrid}>
        <article className={styles.panel}><p className={styles.eyebrow}>ECONOMIC ANCHOR</p><h2>Earlier intervention is the hypothesis to validate</h2><p>If production evidence shows that specific drift patterns reliably precede downtime, scrap, or emergency maintenance, the same relationship model can support planned intervention before the expensive event. Until that correlation exists, LineAlert should call this condition monitoring—not predictive maintenance.</p><div className={styles.roiTargets}><span><b>Downtime</b><small>Potential avoided interruption</small></span><span><b>Scrap / rework</b><small>Potential earlier quality intervention</small></span><span><b>Emergency work</b><small>Potential shift toward planned maintenance</small></span><span><b>OEM support</b><small>Potential better evidence before escalation</small></span></div></article>
        <article className={styles.panel}><p className={styles.eyebrow}>SECONDARY USE</p><h2>Learning stays attached, but it is not the economic core</h2><p>The same machine relationship can be replayed in an OEM or school lab to teach what normal coordination looks like and how degradation becomes visible. That is a useful sidecar market; production condition monitoring remains the primary product thesis.</p></article>
      </section>
    </main>
  );
}
