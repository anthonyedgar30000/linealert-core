"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import styles from "./health.module.css";
import sourceStyles from "./source.module.css";

type HealthStatus = "HEALTHY" | "DRIFTING" | "ATTENTION";
type EvidenceSignal = { value: number | null; unit: string; quality: string };
type SignalDecision = { admitted?: boolean; scope?: string };
type TelemetrySnapshot = {
  connected: boolean;
  source_id?: string;
  source_kind?: string;
  asset_id?: string;
  reason_code?: string;
  semantic_admission?: { signals?: Record<string, SignalDecision> };
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

const baseline = { low: 120, high: 140, unit: "ms" };
const conditionSignalName = "label_feed_response_ms";

const demoStates: HealthState[] = [
  { label: "Day 1", status: "HEALTHY", rollingAverage: 128, trendPercent: 0, violations: 0, note: "Commissioned timing is stable inside the expected envelope." },
  { label: "Day 3", status: "HEALTHY", rollingAverage: 133, trendPercent: 4, violations: 0, note: "Small movement is visible, but the relationship remains inside its commissioned envelope." },
  { label: "Day 7", status: "DRIFTING", rollingAverage: 145, trendPercent: 11, violations: 1, note: "The rolling average has crossed the upper baseline and the direction of travel is persistent." },
  { label: "Day 10", status: "DRIFTING", rollingAverage: 154, trendPercent: 18, violations: 3, note: "Condition degradation is visible before a hard stop. Maintenance review is warranted; no failure prediction is claimed." },
  { label: "Day 12", status: "ATTENTION", rollingAverage: 166, trendPercent: 27, violations: 12, note: "The simulated relationship is repeatedly outside its commissioned envelope and should be investigated." },
];

const seriesByState = [
  [126, 127, 128],
  [126, 127, 128, 130, 133],
  [126, 127, 128, 130, 132, 135, 139, 145],
  [126, 127, 128, 130, 132, 135, 139, 143, 148, 154],
  [126, 127, 128, 130, 132, 135, 139, 143, 148, 154, 160, 166],
];

const average = (values: number[]) =>
  values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;

const signalSeries = (history: HistoryPayload | null, name: string, admitted: boolean) =>
  history?.observations.flatMap((observation) => {
    const signal = observation.signals?.[name];
    const decision = observation.semantic_admission?.signals?.[name];
    if (
      !signal ||
      signal.quality !== "good" ||
      typeof signal.value !== "number" ||
      !Number.isFinite(signal.value) ||
      (admitted && !decision?.admitted)
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

export default function MachineHealthPage() {
  const [demoIndex, setDemoIndex] = useState(3);
  const [telemetry, setTelemetry] = useState<TelemetrySnapshot | null>(null);
  const [history, setHistory] = useState<HistoryPayload | null>(null);
  const [telemetryReachable, setTelemetryReachable] = useState(false);
  const [historyReachable, setHistoryReachable] = useState(false);

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

    readTelemetry();
    readHistory();
    const telemetryTimer = setInterval(readTelemetry, 1000);
    const historyTimer = setInterval(readHistory, 3000);
    return () => {
      active = false;
      clearInterval(telemetryTimer);
      clearInterval(historyTimer);
    };
  }, []);

  const conditionSignal = telemetry?.signals?.[conditionSignalName];
  const conditionDecision = telemetry?.semantic_admission?.signals?.[conditionSignalName];
  const conditionMapped = Boolean(
    telemetry?.connected && conditionSignal?.quality === "good" && conditionDecision?.admitted,
  );
  const conditionSeries = useMemo(
    () => signalSeries(history, conditionSignalName, true),
    [history],
  );
  const arrivalSeries = useMemo(() => signalSeries(history, "arrival_ms", false), [history]);
  const usingLiveCondition = conditionMapped && conditionSeries.length >= 5;

  const liveState = useMemo<HealthState>(() => {
    const recent = conditionSeries.slice(-20);
    const first = conditionSeries.slice(0, Math.min(20, conditionSeries.length));
    const rollingAverage = average(recent);
    const startingAverage = average(first) || rollingAverage;
    const trendPercent = startingAverage
      ? ((rollingAverage - startingAverage) / startingAverage) * 100
      : 0;
    const violations = conditionSeries
      .slice(-120)
      .filter((value) => value < baseline.low || value > baseline.high).length;
    const severe = rollingAverage > baseline.high + 20 || rollingAverage < baseline.low - 20;
    const drifting =
      rollingAverage > baseline.high ||
      rollingAverage < baseline.low ||
      Math.abs(trendPercent) >= 8;
    const status: HealthStatus = severe || violations >= 10
      ? "ATTENTION"
      : drifting
        ? "DRIFTING"
        : "HEALTHY";
    return {
      label: "Live history",
      status,
      rollingAverage,
      trendPercent,
      violations,
      note: status === "HEALTHY"
        ? "The admitted response-time signal remains inside its commissioned envelope across the recent history window."
        : "The admitted response-time signal shows persistent movement relative to its commissioned envelope. This establishes condition drift, not root cause or future failure.",
    };
  }, [conditionSeries]);

  const state = usingLiveCondition ? liveState : demoStates[demoIndex];
  const chartSeries = usingLiveCondition ? conditionSeries.slice(-80) : seriesByState[demoIndex];
  const bridgeConnected = Boolean(telemetryReachable && telemetry?.connected);

  const chart = useMemo(() => {
    const series = chartSeries.length ? chartSeries : [baseline.low, baseline.high];
    const width = 700;
    const height = 250;
    const paddingX = 34;
    const paddingY = 24;
    const observedMin = Math.min(baseline.low, ...series);
    const observedMax = Math.max(baseline.high, ...series);
    const min = Math.floor((observedMin - 10) / 10) * 10;
    const rawMax = Math.ceil((observedMax + 10) / 10) * 10;
    const max = Math.max(rawMax, min + 40);
    const denominator = Math.max(series.length - 1, 1);
    const x = (index: number) => paddingX + (index / denominator) * (width - paddingX * 2);
    const y = (value: number) =>
      paddingY + ((max - value) / (max - min)) * (height - paddingY * 2);
    const ticks = Array.from(new Set([baseline.low, baseline.high, max - 10]))
      .sort((left, right) => left - right)
      .map((value) => ({ value, y: y(value) }));
    return {
      width,
      height,
      points: series.map((value, index) => `${x(index)},${y(value)}`).join(" "),
      baselineTop: y(baseline.high),
      baselineBottom: y(baseline.low),
      currentX: x(series.length - 1),
      currentY: y(series[series.length - 1]),
      ticks,
    };
  }, [chartSeries]);

  const deviationDetected =
    state.rollingAverage < baseline.low || state.rollingAverage > baseline.high;
  const conditionDegradation = usingLiveCondition
    ? conditionSeries.length >= 20 && liveState.violations >= 3 && Math.abs(liveState.trendPercent) >= 5
    : demoIndex >= 2;
  const trendLabel = `${state.trendPercent >= 0 ? "+" : ""}${state.trendPercent.toFixed(usingLiveCondition ? 1 : 0)}%`;

  return (
    <main className={styles.shell}>
      <header className={styles.topbar}>
        <div>
          <Link className={styles.backLink} href="/">← Operator / troubleshooting view</Link>
          <p className={styles.eyebrow}>LINEALERT · CONDITION MONITORING PROTOTYPE</p>
          <h1>Machine Health — Label Application Station</h1>
          <p className={styles.subtitle}>
            Track coordinated machine relationships against a commissioned baseline and surface meaningful drift before it becomes an obvious fault.
          </p>
        </div>
        <div className={styles.demoFlag}>
          <b>{usingLiveCondition ? "LIVE CONDITION HISTORY" : bridgeConnected ? "LIVE EVIDENCE + SIMULATED CONDITION" : "SIMULATED CONDITION HISTORY"}</b>
          <span>{usingLiveCondition ? "Admitted response-time history is driving this condition view. No failure prediction is claimed." : bridgeConnected ? "The bridge is live, but the condition relationship remains simulated until its exact signal is semantically mapped." : "No production failure prediction is claimed."}</span>
        </div>
      </header>

      <section className={styles.statusRow} aria-label="Machine health summary">
        <article className={`${styles.healthCard} ${styles[state.status.toLowerCase()]}`}>
          <span>STATION HEALTH</span><strong>{state.status}</strong>
          <small>{usingLiveCondition ? "Admitted bridge history" : `${state.label} · simulated condition history`}</small>
        </article>
        <article className={styles.metricCard}>
          <span>MONITORED RELATIONSHIP</span><strong>Photoeye → label-feed response</strong>
          <small>Commissioned envelope {baseline.low}–{baseline.high} {baseline.unit}</small>
        </article>
        <article className={styles.metricCard}>
          <span>CURRENT ROLLING AVERAGE</span><strong>{state.rollingAverage.toFixed(usingLiveCondition ? 1 : 0)} ms</strong>
          <small>{deviationDetected ? "Outside commissioned baseline" : "Inside commissioned baseline"}</small>
        </article>
        <article className={styles.metricCard}>
          <span>{usingLiveCondition ? "HISTORY TREND" : "7-DAY TREND"}</span><strong>{trendLabel}</strong>
          <small>Direction matters before a hard alarm does</small>
        </article>
        <article className={styles.metricCard}>
          <span>ENVELOPE VIOLATIONS</span><strong>{state.violations} {usingLiveCondition ? "recent" : "today"}</strong>
          <small>Repeated observations, not a root-cause claim</small>
        </article>
        <article className={styles.metricCard}>
          <span>LAST MAINTENANCE CONTEXT</span><strong>{usingLiveCondition ? "Not connected" : "Feed roller cleaned"}</strong>
          <small>{usingLiveCondition ? "Maintenance outcomes are the next integration" : "18 days ago · simulated work history"}</small>
        </article>
      </section>

      <section className={sourceStyles.sourcePanel} aria-label="Live telemetry and history context">
        <div className={sourceStyles.sourceHeader}>
          <div>
            <p className={sourceStyles.eyebrow}>LIVE EVIDENCE CONTEXT</p>
            <h2>Bridge observations now sit beside the condition model</h2>
            <p>Live proxies remain context until the exact condition relationship is explicitly mapped and semantically admitted.</p>
          </div>
          <span className={`${sourceStyles.sourceState} ${bridgeConnected ? sourceStyles.sourceLive : sourceStyles.sourceDemo}`}><i/>{bridgeConnected ? "BRIDGE CONNECTED" : "DEMO FALLBACK"}</span>
        </div>

        <div className={sourceStyles.sourceGrid}>
          <div className={`${sourceStyles.sourceCard} ${bridgeConnected ? sourceStyles.sourceGood : sourceStyles.sourceWarn}`}>
            <span>TELEMETRY SOURCE</span><b>{bridgeConnected ? `${telemetry?.asset_id ?? "asset"} · ${telemetry?.source_kind ?? "source"}` : "Unavailable"}</b>
            <small>{telemetry?.reason_code ?? "The condition demo remains usable without the bridge."}</small>
          </div>
          <div className={`${sourceStyles.sourceCard} ${historyReachable ? sourceStyles.sourceGood : sourceStyles.sourceWarn}`}>
            <span>RECENT HISTORY</span><b className={sourceStyles.historianStatus}><i className={sourceStyles.historianDot}/>{history?.count ?? 0} snapshots</b>
            <small>{historyMode(history?.persistence)}</small>
          </div>
          <div className={`${sourceStyles.sourceCard} ${conditionMapped ? sourceStyles.sourceGood : sourceStyles.sourceWarn}`}>
            <span>CONDITION SIGNAL BINDING</span><b>{conditionMapped ? "Mapped and admitted" : "Not mapped"}</b>
            <small>{conditionSignalName}</small>
            <em className={`${sourceStyles.bindingBadge} ${conditionMapped ? sourceStyles.liveBadge : sourceStyles.disabledBadge}`}>{conditionMapped ? "ELIGIBLE FOR CONDITION MODEL" : "SIMULATION REMAINS AUTHORITATIVE"}</em>
          </div>
          <div className={sourceStyles.sourceCard}>
            <span>HISTORY MODE</span><b>{usingLiveCondition ? "Live condition view" : conditionMapped ? "Collecting history" : "Context only"}</b>
            <small>{conditionMapped && conditionSeries.length < 5 ? `${conditionSeries.length}/5 minimum samples collected` : "No implicit promotion from proxy evidence to machine truth."}</small>
          </div>
        </div>

        <div className={sourceStyles.signalGrid}>
          <div className={sourceStyles.signalCard}><span>MOTOR SPEED PROXY</span><b className={sourceStyles.signalValue}>{formatSignal(telemetry?.signals?.rpm)}</b><small>{telemetry?.signals?.rpm?.quality ?? "no current sample"}</small></div>
          <div className={sourceStyles.signalCard}><span>DERIVED CONVEYOR ARRIVAL PROXY</span><b className={sourceStyles.signalValue}>{formatSignal(telemetry?.signals?.arrival_ms)}</b><small>{arrivalSeries.length} qualified samples retained</small></div>
          <div className={sourceStyles.signalCard}><span>CONTACT PRESSURE PROXY</span><b className={sourceStyles.signalValue}>{formatSignal(telemetry?.signals?.pressure_psi)}</b><small>{telemetry?.signals?.pressure_psi?.quality ?? "no current sample"}</small></div>
        </div>

        <div className={sourceStyles.sourceBoundary}>
          <b>Binding boundary:</b> simulator RPM, derived arrival timing, and pressure do not become the 120–140 ms photoeye-to-label-feed relationship because the units or trend look convenient. A named qualified mapping must exist first.
        </div>
        <div className={sourceStyles.historyNote}>{history?.persistence === "jsonl_capture" ? "Durable JSONL capture is enabled; the dashboard exposes a bounded recent window from that observation stream." : "Recent history is memory-backed. Start the bridge with --capture-jsonl to retain the same observations durably for replay and analysis."}</div>
      </section>

      <section className={styles.mainGrid}>
        <article className={styles.panel}>
          <div className={styles.panelHeader}>
            <div><p className={styles.eyebrow}>RELATIONSHIP DRIFT</p><h2>{usingLiveCondition ? "Admitted response history against baseline" : "Response time is moving away from baseline"}</h2></div>
            <div className={styles.legend}><span><i className={styles.baselineKey}/> Commissioned envelope</span><span><i className={styles.trendKey}/> Rolling response time</span></div>
          </div>
          <div className={styles.chartWrap}>
            <svg viewBox={`0 0 ${chart.width} ${chart.height}`} role="img" aria-label={usingLiveCondition ? "Admitted live response-time history" : `Simulated response-time trend through ${state.label}`}>
              <rect x="34" y={chart.baselineTop} width="632" height={chart.baselineBottom - chart.baselineTop} className={styles.baselineBand} rx="8"/>
              {chart.ticks.map((tick) => <g key={tick.value}><line x1="34" y1={tick.y} x2="666" y2={tick.y} className={styles.gridLine}/><text x="2" y={tick.y + 4} className={styles.axisText}>{tick.value} ms</text></g>)}
              <polyline points={chart.points} className={styles.trendLine}/>
              <circle cx={chart.currentX} cy={chart.currentY} r="7" className={styles.currentPoint}/>
              <text x={Math.max(34, chart.currentX - 46)} y={chart.currentY - 14} className={styles.currentLabel}>{state.rollingAverage.toFixed(usingLiveCondition ? 1 : 0)} ms</text>
              <text x="34" y="244" className={styles.axisText}>{usingLiveCondition ? "Oldest retained" : "Commissioned start"}</text>
              <text x="590" y="244" className={styles.axisText}>{usingLiveCondition ? "Latest sample" : state.label}</text>
            </svg>
          </div>
          {!usingLiveCondition && <div className={styles.timelineControls}>{demoStates.map((item, index) => <button key={item.label} className={index === demoIndex ? styles.activeTimelineButton : ""} onClick={() => setDemoIndex(index)}><span>{item.label}</span><b>{item.rollingAverage} ms</b></button>)}</div>}
          <div className={styles.interpretation}><span>WHAT LINEALERT CAN ESTABLISH AT THIS STAGE</span><b>{state.note}</b></div>
        </article>

        <aside className={styles.sideColumn}>
          <article className={styles.panel}>
            <p className={styles.eyebrow}>PHYSICAL RELATIONSHIP</p><h2>Where the drift lives</h2>
            <div className={styles.processFlow}><div><span>S1</span><b>Photoeye</b><small>Bottle detected</small></div><i>→</i><div className={styles.activeNode}><span>Δt</span><b>Response window</b><small>120–140 ms expected</small></div><i>→</i><div><span>M1</span><b>Label feed</b><small>Feed command responds</small></div><i>→</i><div><span>QA</span><b>Inspection</b><small>Outcome retained</small></div></div>
            <p className={styles.boundaryCopy}>LineAlert is measuring the relationship between observed events. It is not claiming that the photoeye, drive, roller, PLC logic, or another component is the root cause.</p>
          </article>
          <article className={styles.panel}>
            <p className={styles.eyebrow}>MATURITY GATES</p><h2>Earn the predictive claim</h2>
            <div className={styles.gates}>
              <div className={deviationDetected ? styles.gatePass : styles.gatePending}><span>01</span><b>Deviation detected</b><small>{deviationDetected ? "Observed relationship is outside the commissioned envelope." : "No current envelope violation is established."}</small></div>
              <div className={conditionDegradation ? styles.gatePass : styles.gatePending}><span>02</span><b>Condition degradation detected</b><small>{conditionDegradation ? "Drift persists across repeated historical observations." : "More repeated history is required before calling this persistent degradation."}</small></div>
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
