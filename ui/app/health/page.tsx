"use client";

import { useMemo, useState } from "react";
import styles from "./health.module.css";

type DemoState = {
  label: string;
  status: "HEALTHY" | "DRIFTING" | "ATTENTION";
  rollingAverage: number;
  trend: string;
  violations: number;
  note: string;
};

const baseline = { low: 120, high: 140, unit: "ms" };

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

export default function MachineHealthPage() {
  const [stateIndex, setStateIndex] = useState(3);
  const state = demoStates[stateIndex];

  const chart = useMemo(() => {
    const series = seriesByState[stateIndex];
    const width = 700;
    const height = 250;
    const paddingX = 34;
    const paddingY = 24;
    const min = 110;
    const max = 170;
    const x = (index: number) => paddingX + (index / (series.length - 1)) * (width - paddingX * 2);
    const y = (value: number) => paddingY + ((max - value) / (max - min)) * (height - paddingY * 2);
    return {
      width,
      height,
      points: series.map((value, index) => `${x(index)},${y(value)}`).join(" "),
      baselineTop: y(baseline.high),
      baselineBottom: y(baseline.low),
      currentX: x(series.length - 1),
      currentY: y(series[series.length - 1]),
    };
  }, [stateIndex]);

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
          <b>SIMULATED HISTORY</b>
          <span>No production failure prediction is claimed.</span>
        </div>
      </header>

      <section className={styles.statusRow} aria-label="Machine health summary">
        <article className={`${styles.healthCard} ${styles[state.status.toLowerCase()]}`}>
          <span>STATION HEALTH</span>
          <strong>{state.status}</strong>
          <small>{state.label} · simulated condition history</small>
        </article>
        <article className={styles.metricCard}>
          <span>MONITORED RELATIONSHIP</span>
          <strong>Photoeye → label-feed response</strong>
          <small>Commissioned envelope {baseline.low}–{baseline.high} {baseline.unit}</small>
        </article>
        <article className={styles.metricCard}>
          <span>CURRENT ROLLING AVERAGE</span>
          <strong>{state.rollingAverage} ms</strong>
          <small>{state.rollingAverage > baseline.high ? `${state.rollingAverage - baseline.high} ms above upper baseline` : "Inside commissioned baseline"}</small>
        </article>
        <article className={styles.metricCard}>
          <span>7-DAY TREND</span>
          <strong>{state.trend}</strong>
          <small>Direction matters before a hard alarm does</small>
        </article>
        <article className={styles.metricCard}>
          <span>ENVELOPE VIOLATIONS</span>
          <strong>{state.violations} today</strong>
          <small>Repeated observations, not a root-cause claim</small>
        </article>
        <article className={styles.metricCard}>
          <span>LAST MAINTENANCE EVENT</span>
          <strong>Feed roller cleaned</strong>
          <small>18 days ago · simulated work history</small>
        </article>
      </section>

      <section className={styles.mainGrid}>
        <article className={styles.panel}>
          <div className={styles.panelHeader}>
            <div>
              <p className={styles.eyebrow}>RELATIONSHIP DRIFT</p>
              <h2>Response time is moving away from baseline</h2>
            </div>
            <div className={styles.legend}>
              <span><i className={styles.baselineKey}/> Commissioned envelope</span>
              <span><i className={styles.trendKey}/> Rolling response time</span>
            </div>
          </div>

          <div className={styles.chartWrap}>
            <svg viewBox={`0 0 ${chart.width} ${chart.height}`} role="img" aria-label={`Simulated response-time trend through ${state.label}`}>
              <rect
                x="34"
                y={chart.baselineTop}
                width="632"
                height={chart.baselineBottom - chart.baselineTop}
                className={styles.baselineBand}
                rx="8"
              />
              {[120, 140, 160].map((value) => {
                const y = 24 + ((170 - value) / 60) * 202;
                return (
                  <g key={value}>
                    <line x1="34" y1={y} x2="666" y2={y} className={styles.gridLine}/>
                    <text x="2" y={y + 4} className={styles.axisText}>{value} ms</text>
                  </g>
                );
              })}
              <polyline points={chart.points} className={styles.trendLine}/>
              <circle cx={chart.currentX} cy={chart.currentY} r="7" className={styles.currentPoint}/>
              <text x={chart.currentX - 46} y={chart.currentY - 14} className={styles.currentLabel}>{state.rollingAverage} ms</text>
              <text x="34" y="244" className={styles.axisText}>Commissioned start</text>
              <text x="612" y="244" className={styles.axisText}>{state.label}</text>
            </svg>
          </div>

          <div className={styles.timelineControls}>
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
          </div>

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
              <div className={styles.gatePass}><span>01</span><b>Deviation detected</b><small>Observed relationship is outside the commissioned envelope.</small></div>
              <div className={styles.gatePass}><span>02</span><b>Condition degradation detected</b><small>Drift persists across repeated historical observations.</small></div>
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
