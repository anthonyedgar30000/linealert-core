"use client";

import type { ReactNode } from "react";
import { useSyncExternalStore } from "react";

import styles from "./operator-mode-boundary.module.css";

const subscribeLocation = () => () => undefined;
const getPathname = () => window.location.pathname;
const getSearch = () => window.location.search;
const getServerLocation = () => "";

const numberParam = (params: URLSearchParams, name: string) => {
  const value = params.get(name);
  if (value === null) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

export default function OperatorModeBoundary({ children }: { children: ReactNode }) {
  const path = useSyncExternalStore(subscribeLocation, getPathname, getServerLocation);
  const search = useSyncExternalStore(subscribeLocation, getSearch, getServerLocation);

  if (path !== "/") return <>{children}</>;

  const params = new URLSearchParams(search);
  const healthInvestigation = params.get("source") === "health";

  if (!healthInvestigation) {
    return (
      <>
        <div className={styles.fixtureRibbon} role="status">
          <span>COMMISSIONING FAULT-INJECTION MODE</span>
          <b>Synthetic fixtures are test inputs · not machine diagnoses</b>
        </div>
        {children}
      </>
    );
  }

  const relationship = params.get("relationship") ?? "Measured machine relationship";
  const latest = numberParam(params, "latest");
  const min = numberParam(params, "min");
  const max = numberParam(params, "max");
  const unit = params.get("unit") ?? "";
  const status = params.get("status") ?? "CONDITION";
  const sourceMode = params.get("sourceMode") ?? "unknown";

  return (
    <main className={styles.conditionMode} aria-label="Condition-first operator investigation">
      <section className={styles.conditionHero}>
        <span className={styles.kicker}>OPERATOR VIEW · CONDITION INVESTIGATION</span>
        <h1>Investigate the measured relationship—not a canned fault.</h1>
        <p>
          This view was opened from Machine Health. Commissioning scenarios are deliberately
          excluded so an injected Arrival phase, pressure, slip, tension, or sensor fixture
          cannot be mistaken for the explanation of the retained condition evidence.
        </p>

        <div className={styles.conditionSummary}>
          <div><span>Status</span><b>{status}</b></div>
          <div><span>Relationship</span><b>{relationship}</b></div>
          <div>
            <span>Latest</span>
            <b>{latest === null ? "—" : `${latest.toFixed(0)} ${unit}`.trim()}</b>
          </div>
          <div>
            <span>Commissioned</span>
            <b>{min === null || max === null ? "—" : `${min}–${max} ${unit}`.trim()}</b>
          </div>
        </div>

        <div className={styles.investigationFlow} aria-label="Condition investigation flow">
          <span>Measured condition</span><i>→</i>
          <span>Retained episode</span><i>→</i>
          <span>Bounded investigation</span><i>→</i>
          <span>Verify same relationship</span>
        </div>

        <div className={styles.actions}>
          <a href="/health">← Machine Health</a>
          <a className={styles.secondaryAction} href="/?mode=commissioning">
            Open commissioning fault-injection lab
          </a>
        </div>
      </section>

      <section className={styles.separationCard}>
        <span>SEPARATE TEST PATH</span>
        <b>Fault-injection fixtures are not evidence for this investigation.</b>
        <p>
          The commissioning lab remains available as a controlled synthetic test environment.
          Its fixtures should enter LineAlert upstream as synthetic events and earn their own
          admitted condition evidence before appearing in an operator investigation. Until that
          path is wired, this condition-first mode keeps the fixture UI out of the evidence chain.
        </p>
        <small>Source mode: {sourceMode}</small>
      </section>
    </main>
  );
}
