"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "./health.module.css";
import sourceStyles from "./source.module.css";

type HealthStatus = "HEALTHY" | "DRIFTING" | "ATTENTION";

type DemoState = {
  label: string;
  status: HealthStatus;
  rollingAverage: number;
  trend: string;
  violations: number;
  note: string;
};

type EvidenceSignal = {
  value: number | null;
  unit: string;
  quality: string;
  reason_code?: string;
  provenance?: string;
};

type SignalDecision = {
  admitted?: boolean;
  scope?: string;
};

type TelemetrySnapshot = {
  connected: boolean;
  source_id?: string;
  source_kind?: string;
  asset_id?: string;
  reason_code?: string;
  bridge_timestamp?: string;
  observation_sequence?: number;
  proxy_warning?: string;
  semantic_admission?: {
    signals?: Record<string, SignalDecision>;
  };
  signals?: Record<string, EvidenceSignal>;
};

type HistoryPayload = {
  schema_version: string;
  persistence: string;
  count: number;
  observations: TelemetrySnapshot[];
  reason_code?: string;
};

const baseline = { low: 120, high: 140, unit: "ms" };
const conditionSignalName = "label_feed_response_ms";

const demoStates: DemoState[] = [
  {
    label: "Day 1",
    status: "HEALTHY",
    rollingAverage: 128,
    trend: "+0%",
    violations: 0,
    note: "Commissioned timing relationship is stable inside the expected envelope.",
  },
  {
    label: "Day 3",
    status: "HEALTHY",
    rollingAverage: 133,
    trend: "+4%",
    violations: 0,
    note: "Small movement is visible, but the relationship remains inside its commissioned envelope.",
  },
  {
    label: "Day 7",
    status: "DRIFTING",
    rollingAverage: 145,
    trend: "+11%",
    violations: 1,
    note: "The rolling average has crossed the upper baseline and the direction of travel is persistent.",
  },
  {
    label: "Day 10",
    status: "DRIFTING",
    rollingAverage: 154,
    trend: "+18%",
    violations: 3,
    note: "Condition degradation is visible before a hard stop. Maintenance review is warranted; no failure prediction is claimed.",
  },
  {
    label: "Day 12",
    status: "ATTENTION",
    rollingAverage: 166,
    trend: "+27%",
    violations: 12,
    note: "The simulated relationship is repeatedly outside its commissioned envelope and should be investigated before continued production.",
  },
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

const admittedSeries = (history: HistoryPayload | null, signalName: string) =>
  history?.observations.flatMap((observation) => {
    const signal = observation.signals?.[signalName];
    const decision = observation.semantic_admission?.signals?.[signalName];
    if (
      !signal ||
      signal.quality !== "good" ||
      typeof signal.value !== "number" ||
      !Number.isFinite(signal.value) ||
      !decision?.admitted
    ) {
      return [];
    }
    return [signal.value];
  }) ?? [];

const qualifiedSeries = (history: HistoryPayload | null, signalName: string) =>
  history?.observations.flatMap((observation) => {
    const signal = observation.signals?.[signalName];
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

const persistenceLabel = (value: string | undefined) => {
  if (value === "jsonl_capture") return "JSONL capture + recent buffer";
  if (value === "deterministic_replay") return "Deterministic replay history";
  if (value === "memory_only") return "Recent memory buffer";
  return "History unavailable";
};

export default function MachineHealthPage() {
  const [stateIndex, setStateIndex] = useState(3);
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

  const demoState = demoStates[stateIndex];
  const conditionSignal = telemetry?.signals?.[conditionSignalName];
  const conditionDecision = telemetry?.semantic_admission?.signals?.[conditionSignalName];
  const conditionMapped = Boolean(
    telemetry?.connected && conditionSignal?.quality === "good" && conditionDecision?.admitted,
  );

  const conditionSeries = useMemo(
    () => admittedSeries(history, conditionSignalName),
    [history],
  );
  const arrivalProxySeries = useMemo(
    () => qualifiedSeries(history, "arrival_ms"),
    [history],
  );
  const usingLiveCondition = conditionMapped && conditionSeries.length >= 5;

  const liveAnalysis = useMemo(() => {
    const recent = conditionSeries.slice(-20);
    const startWindow = conditionSeries.slice(0, Math.min(20, conditionSeries.length));
    const rollingAverage = average(recent);
    const startAverage = average(startWindow) || rollingAverage;
    const trendPercent = startAverage
      ? ((rollingAverage - startAverage) / startAverage) * 100
      : 0;
    const violations = conditionSeries
      .slice(-120)
      .filter((value) => value < baseline.low || value > baseline.high).length;
    const severeDeviation =
      rollingAverage > baseline.high + 20 || rollingAverage < baseline.low - 20;
    const status: HealthStatus = severeDeviation || violations >= 10
      ? "ATTENTION"
      : rollingAverage < baseline.low ||
          rollingAverage > baseline.high ||
          Math.abs(trendPercent) >= 8
        ? "DRIFTING"
        : "HEALTHY";
    return {
      label: "Live history",
      status,
      rollingAverage,
      trendPercent,
      trend: `${trendPercent >= 0 ? "+" : ""}${trendPercent.toFixed(1)}%`,
      violations,
      note:
        status === "HEALTHY"
          ? "The admitted response-time signal remains inside its commissioned envelope across the recent history window."
          : "The admitted response-time signal shows persistent movement relative to its commissioned envelope. This establishes condition drift, not a failure cause or future failure prediction.",
    };
  }, [conditionSeries]);

  const state: DemoState = usingLiveCondition
    ? {
        label: liveAnalysis.label,
        status: liveAnalysis.status,
        rollingAverage: liveAnalysis.rollingAverage,
        trend: liveAnalysis.trend,
        violations: liveAnalysis.violations,
        note: liveAnalysis.note,
      }
    : demoState;

  const activeSeries = usingLiveCondition
    ? conditionSeries.slice(-80)
    : seriesByState[stateIndex];

  const chart = useMemo(() => {
    const series = activeSeries.length ? activeSeries : [baseline.low, baseline.high];
    const width = 700;
    const height = 250;
    const paddingX = 34;
    const paddingY = 24;
    const observedMin = Math.min(baseline.low, ...series);
    const observedMax = Math.max(baseline.high, ...series);
    let min = Math.floor((observedMin - 10) / 10) * 10;
    let max = Math.ceil((observedMax + 10) / 10) * 10;
    if (max - min < 40) max = min + 40;
    const denominator = Math.max(series.length - 1, 1);
    const x = (index: number) =>
      paddingX + (index / denominator) * (width - paddingX * 2);
    const y = (value: number) =>
      paddingY + ((max - value) / (max - min)) * (height - paddingY * 2);
    const tickValues = Array.from(new Set([baseline.low, baseline.high, max - 10])).sort(
      (left, right) => left - right,
    );
    return {
      width,
      height,
      points: series.map((value, index) => `${x(index)},${y(value)}`).join(" "),
      baselineTop: y(baseline.high),
      baselineBottom: y(baseline.low),
      currentX: x(series.length - 1),
      currentY: y(series[series.length - 1]),
      ticks: tickValues.map((value) => ({ value, y: y(value) })),
    };
  }, [activeSeries]);

  const deviationDetected =
    state.rollingAverage < baseline.low || state.rollingAverage > baseline.high;
  const conditionDegradation = usingLiveCondition
    ? conditionSeries.length >= 20 &&
      liveAnalysis.violations >= 3 &&
      Math.abs(liveAnalysis.trendPercent) >= 5
    : stateIndex >= 2;

  const bridgeConnected = Boolean(telemetryReachable && telemetry?.connected);
  const historyCount = history?.count ?? 0;
  const currentRpm = telemetry?.signals?.rpm;
  const currentArrivalProxy = telemetry?.signals?.arrival_ms;
  const currentPressure = telemetry?.signals?.pressure_psi;

  const flagTitle = usingLiveCondition
    ? "LIVE CONDITION HISTORY"
    : bridgeConnected
      ? "LIVE EVIDENCE + SIMULATED CONDITION"
      : "SIMULATED CONDITION HISTORY";
  const flagCopy = usingLiveCondition
    ? "Admitted response-time history is driving the condition view. No failure prediction is claimed."
    : bridgeConnected
      ? "The bridge is live, but the condition model remains simulated until a semantically admitted response-time signal is mapped."
      : "No production failure prediction is claimed.";

  return (
    <main className={styles.shell}>
      <header className={styles.topbar}>
        <div>
          <a className={styles.backLink} href="/">← Operator / troubleshooting view</a>
          <p className={styles.eyebrow}>LINEALERT · CONDITION MONITORING PROTOTYPE</p>
          <h1>Machine Health — Label Application Station</h1>
          <p className={styles.subtitle}>
            Track coordinated machine relationships against a commissioned baseline and surface meaningful drift before it becomes an obvious fault.
          </p>
        </div>
        <div className={styles.demoFlag}>
          <b>{flagTitle}</b>
          <span>{flagCopy}</span>
        </div>
      </header>

      <section className={styles.statusRow} aria-label="Machine health summary">
        <article className={`${styles.healthCard} ${styles[state.status.toLowerCase()]}`}>
          <span>STATION HEALTH</span>
          <strong>{state.status}</strong>
          <small>
            {usingLiveCondition ? "Admitted bridge history" : `${state.label} · simulated condition history`}
          </small>
        </article>
        <article className={styles.metricCard}>
          <span>MONITORED RELATIONSHIP</span>
          <strong>Photoeye → label-feed response</strong>
          <small>Commissioned envelope {baseline.low}–{baseline.high} {baseline.unit}</small>
        </article>
        <article className={styles.metricCard}>
          <span>CURRENT ROLLING AVERAGE</span>
          <strong>{state.rollingAverage.toFixed(usingLiveCondition ? 1 : 0)} ms</strong>
          <small>
            {state.rollingAverage > baseline.high
              ? `${(state.rollingAverage - baseline.high).toFixed(1)} ms above upper baseline`
              : state.rollingAverage < baseline.low
                ? `${(baseline.low - state.rollingAverage).toFixed(1)} ms below lower baseline`
                : "Inside commissioned baseline"}
          </small>
        </article>
        <article className={styles.metricCard}>
          <span>{usingLiveCondition ? "HISTORY TREND" : "7-DAY TREND"}</span>
          <strong>{state.trend}</strong>
          <small>Direction matters before a hard alarm does</small>
        </article>
        <article className={styles.metricCard}>
          <span>ENVELOPE VIOLATIONS</span>
          <strong>{state.violations} {usingLiveCondition ? "recent" : "today"}</strong>
          <small>Repeated observations, not a root-cause claim</small>
        </article>
        <article className={styles.metricCard}>
          <span>LAST MAINTENANCE CONTEXT</span>
          <strong>{usingLiveCondition ? "Not connected" : "Feed roller cleaned"}</strong>
          <small>{usingLiveCondition ? "Maintenance outcome feed is the next integration" : "18 days ago · simulated work history"}</small>
        </article>
      </section>

      <section className={sourceStyles.sourcePanel} aria-label="Live telemetry and history context">
        <div className={sourceStyles.sourceHeader}>
          <div>
            <p className={sourceStyles.eyebrow}>LIVE EVIDENCE CONTEXT</p>
            <h2>The demo can now see the bridge and its recent observation history</h2>
            <p>
              Live proxy values stay separate from the condition claim until the exact machine relationship is explicitly mapped and semantically admitted.
            </p>
          </div>
          <span className={`${sourceStyles.sourceState} ${bridgeConnected ? sourceStyles.sourceLive : sourceStyles.sourceDemo}`}>
            <i/>{bridgeConnected ? "BRIDGE CONNECTED" : "DEMO FALLBACK"}
          </span>
        </div>

        <div className={sourceStyles.sourceGrid}>
          <div className={`${sourceStyles.sourceCard} ${bridgeConnected ? sourceStyles.sourceGood : sourceStyles.sourceWarn}`}>
            <span>TELEMETRY SOURCE</span>
            <b>{bridgeConnected ? `${telemetry?.asset_id ?? "asset"} · ${telemetry?.source_kind ?? "source"}` : "Unavailable"}</b>
            <small>{telemetry?.reason_code ?? "The condition demo remains usable without the local bridge."}</small>
          </div>
          <div className={`${sourceStyles.sourceCard} ${historyReachable ? sourceStyles.sourceGood : sourceStyles.sourceWarn}`}>
            <span>RECENT HISTORY</span>
            <b className={sourceStyles.historianStatus}><i className={sourceStyles.historianDot}/>{historyCount} snapshots</b>
            <small>{persistenceLabel(history?.persistence)}</small>
          </div>
          <div className={`${sourceStyles.sourceCard} ${conditionMapped ? sourceStyles.sourceGood : sourceStyles.sourceWarn}`}>
            <span>CONDITION SIGNAL BINDING</span>
            <b>{conditionMapped ? "Mapped and admitted" : "Not mapped"}</b>
            <small>{conditionSignalName}</small>
            <em className={`${sourceStyles.bindingBadge} ${conditionMapped ? sourceStyles.liveBadge : sourceStyles.disabledBadge}`}>
              {conditionMapped ? "ELIGIBLE FOR CONDITION MODEL" : "SIMULATION REMAINS AUTHORITATIVE"}
            </em>
          </div>
          <div className={sourceStyles.sourceCard}>
            <span>HISTORY MODE</span>
            <b>{usingLiveCondition ? "Live condition view" : conditionMapped ? "Collecting admitted history" : "Context only"}</b>
            <small>{conditionMapped && conditionSeries.length < 5 ? `${conditionSeries.length}/5 minimum samples collected` : "No implicit promotion from proxy evidence to machine truth."}</small>
          </div>
        </div>

        <div className={sourceStyles.signalGrid}>
          <div className={sourceStyles.signalCard}>
            <span>MOTOR SPEED PROXY</span>
            <b className={sourceStyles.signalValue}>{formatSignal(currentRpm)}</b>
            <small>{currentRpm?.quality ?? "no current sample"}</small>
          </div>
          <div className={sourceStyles.signalCard}>
            <span>DERIVED CONVEYOR ARRIVAL PROXY</span>
            <b className={sourceStyles.signalValue}>{formatSignal(currentArrivalProxy)}</b>
            <small>{arrivalProxySeries.length} qualified samples in recent history</small>
          </div>
          <div className={sourceStyles.signalCard}>
            <span>CONTACT PRESSURE PROXY</span>
            <b className={sourceStyles.signalValue}>{formatSignal(currentPressure)}</b>
            <small>{currentPressure?.quality ?? "no current sample"}</small>
          </div>
        </div>

        <div className={sourceStyles.sourceBoundary}>
          <b>Binding boundary:</b> the existing Microsoft OPC PLC stream exposes simulator proxies. Those values can provide live context and history, but they do not become the 120–140 ms photoeye-to-label-feed condition signal by resemblance or convenience. A named, qualified mapping must exist first.
        </div>
        <div className={sourceStyles.historyNote}>
          {history?.persistence === "jsonl_capture"
            ? "Durable JSONL capture is enabled; the dashboard API exposes a bounded recent window from the same observation stream."
            : "The bridge currently exposes a bounded recent-memory history. Start it with --capture-jsonl to retain the same observation snapshots durably for later replay and analysis."}
        </div>
      </section>

      <section className={styles.mainGrid}>
        <article className={styles.panel}>
          <div className={styles.panelHeader}>
            <div>
              <p className={styles.eyebrow}>RELATIONSHIP DRIFT</p>
              <h2>{usingLiveCondition ? "Admitted response history against baseline" : "Response time is moving away from baseline"}</h2>
            </div>
            <div className={styles.legend}>
              <span><i className={styles.baselineKey}/> Commissioned envelope</span>
              <span><i className={styles.trendKey}/> Rolling response time</span>
            </div>
          </div>

          <div className={styles.chartWrap}>
            <svg viewBox={`0 0 ${chart.width} ${chart.height}`} role="img" aria-label={usingLiveCondition ? "Admitted live response-time history" : `Simulated response-time trend through ${state.label}`}>
              <rect
                x="34"
                y={chart.baselineTop}
                width="632"
                height={chart.baselineBottom - chart.baselineTop}
                className={styles.baselineBand}
                rx="8"
              />
              {chart.ticks.map((tick) => (
                <g key={tick.value}>
                  <line x1="34" y1={tick.y} x2="666" y2={tick.y} className={styles.gridLine}/>
                  <text x="2" y={tick.y + 4} className={styles.axisText}>{tick.value} ms</text>
                </g>
              ))}
              <polyline points={chart.points} className={styles.trendLine}/>
              <circle cx={chart.currentX} cy={chart.currentY} r="7" className={styles.currentPoint}/>
              <text x={Math.max(34, chart.currentX - 46)} y={chart.currentY - 14} className={styles.currentLabel}>{state.rollingAverage.toFixed(usingLiveCondition ? 1 : 0)} ms</text>
              <text x="34" y="244" className={styles.axisText}>{usingLiveCondition ? "Oldest retained" : "Commissioned start"}</text>
              <text x="590" y="244" className={styles.axisText}>{usingLiveCondition ? "Latest sample" : state.label}</text>
            </svg>
          </div>

          {!usingLiveCondition && <div className={styles.timelineControls}>
            {demoStates.map((item, index) => (
              <button
                key={item.label}
                className={index === stateIndex ? styles.activeTimelineButton : ""}
                onClick={() => setStateIndex(index)}
              >
                <span>{item.label}</span>
                <b>{item.rollingAverage} ms</b>
              </button>
            ))}
          </div>}

          <div className={styles.interpretation}>
            <span>WHAT LINEALERT CAN ESTABLISH AT THIS STAGE</span>
            <b>{state.note}</b>
          </div>
        </article>

        <aside className={styles.sideColumn}>
          <article className={styles.panel}>
            <p className={styles.eyebrow}>PHYSICAL RELATIONSHIP</p>
            <h2>Where the drift lives</h2>
            <div className={styles.processFlow}>
              <div><span>S1</span><b>Photoeye</b><small>Bottle detected</small></div>
              <i>→</i>
              <div className={styles.activeNode}><span>Δt</span><b>Response window</b><small>120–140 ms expected</small></div>
              <i>→</i>
              <div><span>M1</span><b>Label feed</b><small>Feed command responds</small></div>
              <i>→</i>
              <div><span>QA</span><b>Inspection</b><small>Outcome retained</small></div>
            </div>
            <p className={styles.boundaryCopy}>
              LineAlert is measuring the relationship between observed events. It is not claiming that the photoeye, drive, roller, PLC logic, or any other component is the root cause.
            </p>
          </article>

          <article className={styles.panel}>
            <p className={styles.eyebrow}>MATURITY GATES</p>
            <h2>Earn the predictive claim</h2>
            <div className={styles.gates}>
              <div className={deviationDetected ? styles.gatePass : styles.gatePending}><span>01</span><b>Deviation detected</b><small>{deviationDetected ? "Observed relationship is outside the commissioned envelope." : "No current envelope violation is established."}</small></div>
              <div className={conditionDegradation ? styles.gatePass : styles.gatePending}><span>02</span><b>Condition degradation detected</b><small>{conditionDegradation ? "Drift persists across repeated historical observations." : "More repeated history is required before calling this persistent degradation."}</small></div>
              <div className={styles.gatePending}><span>03</span><b>Failure prediction validated</b><small>Not yet established. Requires real maintenance outcomes and repeatable predictive value.</small></div>
            </div>
          </article>
        </aside>
      </section>

      <section className={styles.lowerGrid}>
        <article className={styles.panel}>
          <p className={styles.eyebrow}>ECONOMIC ANCHOR</p>
          <h2>Earlier intervention is the hypothesis to validate</h2>
          <p>
            If production evidence shows that specific drift patterns reliably precede downtime, scrap, or emergency maintenance, the same relationship model can support planned intervention before the expensive event. Until that correlation exists, LineAlert should call this condition monitoring—not predictive maintenance.
          </p>
          <div className={styles.roiTargets}>
            <span><b>Downtime</b><small>Potential avoided interruption</small></span>
            <span><b>Scrap / rework</b><small>Potential earlier quality intervention</small></span>
            <span><b>Emergency work</b><small>Potential shift toward planned maintenance</small></span>
            <span><b>OEM support</b><small>Potential better evidence before escalation</small></span>
          </div>
        </article>

        <article className={styles.panel}>
          <p className={styles.eyebrow}>SECONDARY USE</p>
          <h2>Learning stays attached, but it is not the economic core</h2>
          <p>
            The exact same machine relationship can be replayed in an OEM or school lab to teach students what normal coordination looks like and how degradation becomes visible. That is a useful sidecar market; production condition monitoring remains the primary product thesis.
          </p>
        </article>
      </section>
    </main>
  );
}
