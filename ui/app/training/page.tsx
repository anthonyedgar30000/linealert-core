"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import styles from "./training.module.css";

type PersonaId = "operator" | "maintenance" | "instrumentation" | "controls" | "ot" | "engineering";
type PlaybackSpeed = 1 | 3;

type Persona = {
  id: PersonaId;
  name: string;
  purpose: string;
  tools: string[];
  boundary: string;
};

type EvidenceTool = {
  id: string;
  name: string;
  state: "available" | "not_assumed";
  note: string;
  owner?: PersonaId;
  availableFromPhase?: number;
};

type EvidenceReadout = {
  status: string;
  detail: string;
};

const personas: Persona[] = [
  {
    id: "operator",
    name: "Operator",
    purpose: "Recognize the production symptom, establish recurrence, preserve the event history, and escalate with evidence.",
    tools: ["Product / label observation", "Jam recurrence", "Case event history", "Escalation package"],
    boundary: "No hidden-parameter edits, PLC changes, or unapproved mechanical adjustment.",
  },
  {
    id: "maintenance",
    name: "Maintenance",
    purpose: "Receive the operator evidence package and inspect the physical label path under site/OEM procedure.",
    tools: ["Web path", "Rollers and guides", "Mechanical drag / binding", "Authorized tension mechanism checks"],
    boundary: "Inspect the physical mechanism without inventing a controls or network cause.",
  },
  {
    id: "instrumentation",
    name: "Electrical / Instrumentation",
    purpose: "Verify sensors and signals that actually exist on the machine before relying on them.",
    tools: ["Installed sensor indication", "Wiring / signal integrity", "Calibration evidence", "I/O observation"],
    boundary: "This case does not assume a numeric web-tension sensor exists.",
  },
  {
    id: "controls",
    name: "Controls",
    purpose: "Inspect sequence, timing, and controller evidence only where the machine exposes it.",
    tools: ["PLC state", "Sequence timing", "Interlocks", "Configured speed / feed relationships"],
    boundary: "A controller value is not verified physical state; changes require authority and a test plan.",
  },
  {
    id: "ot",
    name: "OT / Industrial IT",
    purpose: "Protect evidence quality across gateways, historian paths, time sources, and industrial networks.",
    tools: ["Source identity", "Timestamps / clock quality", "Historian events", "Gateway / network path"],
    boundary: "Network correlation does not establish a physical fault.",
  },
  {
    id: "engineering",
    name: "Engineering",
    purpose: "Define a bounded test, compare expected and observed behavior, and decide what evidence is still missing.",
    tools: ["Expected relationship", "Test conditions", "Commissioned limits when known", "Verification / rollback criteria"],
    boundary: "A successful training test is not a safe-production authorization.",
  },
];

const evidenceTools: EvidenceTool[] = [
  {
    id: "jam-history",
    name: "Jam event history",
    state: "available",
    note: "Training timeline records each observed jam without asserting its cause.",
    owner: "operator",
    availableFromPhase: 0,
  },
  {
    id: "recurrence-watch",
    name: "Recurrence watch",
    state: "available",
    note: "Tracks whether a single symptom becomes a repeatable pattern at the same cycle point.",
    owner: "operator",
    availableFromPhase: 0,
  },
  {
    id: "web-path",
    name: "Physical web-path inspection",
    state: "available",
    note: "Maintenance-only physical inspection target after the evidence package is handed off.",
    owner: "maintenance",
    availableFromPhase: 3,
  },
  {
    id: "numeric-tension",
    name: "Numeric web-tension gauge",
    state: "not_assumed",
    note: "Locked until an actual machine/source establishes that instrumentation and its units.",
  },
  {
    id: "plc-tension",
    name: "PLC tension tag",
    state: "not_assumed",
    note: "Not invented for the exercise. A real tag must come from equipment documentation or integration evidence.",
  },
  {
    id: "oem-setpoint",
    name: "OEM adjustment setpoint",
    state: "not_assumed",
    note: "No training value is supplied without a machine-specific authoritative source.",
  },
];

const phases = [
  {
    short: "Baseline",
    title: "Establish normal operation",
    body: "Watch the line before anything goes wrong. Learn what normal product flow and label feed look like before chasing a symptom.",
    observation: "No recurring jam is active. Build a baseline from what your current role can actually observe.",
  },
  {
    short: "Event 1",
    title: "A jam interrupts label feed",
    body: "A label-feed jam occurs and the line holds. One event is a symptom, not a root cause. Record it before changing anything.",
    observation: "One applicator jam has occurred. The mechanism remains hidden and unproven.",
  },
  {
    short: "Recurrence",
    title: "The same disturbance returns",
    body: "The jam recurs at the same point in the cycle. Your job is to recognize the pattern and package the evidence, not jump straight to a fault name.",
    observation: "Repeated jam at the same cycle point is now the strongest new evidence.",
  },
  {
    short: "Handoff",
    title: "Maintenance receives the evidence package",
    body: "The operator has reached an authority boundary. Maintenance inherits the established observations and inspects the physical web path without restarting the investigation from zero.",
    observation: "Evidence travels forward with the handoff. Authority remains role-specific.",
  },
  {
    short: "Debrief",
    title: "Reveal the documented training mechanism",
    body: "This scripted exercise is based on a field-documented relationship between repeated applicator jams and inconsistent label-web tension. That explains this case only.",
    observation: "Case mechanism revealed: label-web tension inconsistency. Historical pattern is not current root cause.",
  },
] as const;

const personaLabel = (id: PersonaId) => personas.find((persona) => persona.id === id)?.name ?? id;

export default function TrainingPage() {
  const [personaId, setPersonaId] = useState<PersonaId>("operator");
  const [unlockedPersonas, setUnlockedPersonas] = useState<PersonaId[]>(["operator"]);
  const [started, setStarted] = useState(false);
  const [phase, setPhase] = useState(0);
  const [paused, setPaused] = useState(true);
  const [speed, setSpeed] = useState<PlaybackSpeed>(1);
  const [selectedEvidence, setSelectedEvidence] = useState<string[]>([]);

  const persona = useMemo(
    () => personas.find((candidate) => candidate.id === personaId) ?? personas[0],
    [personaId],
  );

  const currentPhase = phases[phase];
  const mechanismRevealed = started && phase === phases.length - 1;
  const jamActive = started && (phase === 1 || phase === 2);
  const handoffHold = started && phase === 3;
  const lineMoving = started && !paused && !jamActive && !handoffHold && !mechanismRevealed;
  const hasHistory = selectedEvidence.includes("jam-history");
  const hasRecurrence = selectedEvidence.includes("recurrence-watch");
  const hasWebPath = selectedEvidence.includes("web-path");
  const canHandoff = started && phase === 2 && personaId === "operator" && hasHistory && hasRecurrence;
  const canDebrief = started && phase === 3 && personaId === "maintenance" && hasWebPath;

  const lineStatus = !started
    ? "READY"
    : jamActive
      ? "JAM EVENT · LINE HOLD"
      : handoffHold
        ? "HANDOFF HOLD"
        : mechanismRevealed
          ? "CASE COMPLETE"
          : paused
            ? "PAUSED"
            : "RUNNING";

  const advanceLabel = !started
    ? "Start case"
    : phase < 2
      ? "Next meaningful event"
      : phase === 2
        ? "Handoff required"
        : phase === 3
          ? canDebrief ? "Open debrief" : "Inspect web path first"
          : "Case complete";

  const advanceDisabled = started && (phase === 2 || phase === phases.length - 1 || (phase === 3 && !canDebrief));

  const advance = () => {
    if (!started) {
      setStarted(true);
      setPaused(false);
      setPhase(0);
      return;
    }

    if (phase < 2) {
      setPhase((current) => current + 1);
      setPaused(true);
      return;
    }

    if (phase === 3 && canDebrief) {
      setPhase(4);
      setPaused(true);
    }
  };

  const reset = () => {
    setStarted(false);
    setPhase(0);
    setPaused(true);
    setSpeed(1);
    setPersonaId("operator");
    setUnlockedPersonas(["operator"]);
    setSelectedEvidence([]);
  };

  const handoffToMaintenance = () => {
    if (!canHandoff) return;
    setUnlockedPersonas((current) => current.includes("maintenance") ? current : [...current, "maintenance"]);
    setPersonaId("maintenance");
    setPhase(3);
    setPaused(true);
  };

  const evidenceAvailability = (tool: EvidenceTool) => {
    if (tool.state === "not_assumed") return { selectable: false, label: "NOT ASSUMED" };
    if (!started) return { selectable: false, label: "WAIT FOR CASE" };
    if ((tool.availableFromPhase ?? 0) > phase) return { selectable: false, label: "NOT YET AVAILABLE" };
    if (tool.owner && !unlockedPersonas.includes(tool.owner)) {
      return { selectable: false, label: `${personaLabel(tool.owner).toUpperCase()} VIEW` };
    }
    if (tool.owner && tool.owner !== personaId) {
      return { selectable: false, label: `${personaLabel(tool.owner).toUpperCase()} VIEW` };
    }
    if (selectedEvidence.includes(tool.id)) return { selectable: true, label: "PINNED" };
    return { selectable: true, label: "AVAILABLE" };
  };

  const toggleEvidence = (id: string) => {
    setSelectedEvidence((current) => (
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id]
    ));
  };

  const evidenceReadout = (id: string): EvidenceReadout => {
    if (id === "jam-history") {
      if (phase === 0) {
        return {
          status: "No jam events recorded",
          detail: "This training case is still at baseline. The history is useful because it gives later events context.",
        };
      }
      if (phase === 1) {
        return {
          status: "One jam event recorded",
          detail: "A single event is preserved, but there is not enough evidence yet to call it a recurring pattern.",
        };
      }
      return {
        status: "Repeat event preserved",
        detail: "The case history now shows the same symptom returning at the same cycle point.",
      };
    }

    if (id === "recurrence-watch") {
      if (phase === 0) {
        return {
          status: "No recurrence established",
          detail: "Normal operation is the reference state. Nothing has earned an abnormal pattern label yet.",
        };
      }
      if (phase === 1) {
        return {
          status: "Single event only",
          detail: "Keep watching. One jam does not tell you whether the disturbance will repeat.",
        };
      }
      return {
        status: "Recurrence established",
        detail: "The symptom repeats at the same cycle point. That narrows the investigation without proving root cause.",
      };
    }

    if (id === "web-path") {
      return {
        status: mechanismRevealed ? "Inspection linked in debrief" : "Physical inspection target",
        detail: mechanismRevealed
          ? "The case debrief links the recurring symptom to the documented web-tension mechanism. A real machine would still require current evidence."
          : "Maintenance can inspect the physical web path under site/OEM procedure. No numeric tension sensor or adjustment value is assumed.",
      };
    }

    return {
      status: "No readout",
      detail: "This instrument is not admitted for the current case.",
    };
  };

  const pinnedTools = evidenceTools.filter((tool) => selectedEvidence.includes(tool.id));

  const driftMessage = !started
    ? "Start with normal. If you do not know what healthy motion looks like, the first abnormal event has no context."
    : phase === 0
      ? "Pin the event history or recurrence watch before the first disturbance. Good troubleshooting starts before the alarm."
      : phase === 1
        ? "One jam is a clue. Preserve it, then ask whether the same thing happens again before you name a cause."
        : phase === 2 && !canHandoff
          ? "You have a recurring symptom. Pin the event history and recurrence watch so the next role receives evidence, not a hunch."
          : phase === 2
            ? "That is enough for an operator handoff: repeatable symptom, preserved history, and no unauthorized adjustment."
            : phase === 3 && !hasWebPath
              ? "Do not throw away the operator work. Maintenance inherits the timeline; now inspect the physical path that the current evidence justifies."
              : phase === 3
                ? "You have added the maintenance observation. The debrief can now reveal what this documented training pattern was built to teach."
                : "That mechanism explains this scripted case. On a real line, prove it again from current evidence.";

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>LINEALERT · PLANT TROUBLESHOOTING LAB</span>
          <h1>Watch the plant. Build the evidence. Earn the handoff.</h1>
          <p>
            LA-T01 is a field-grounded training pattern. The game hides the scripted mechanism until
            the evidence path earns a debrief; training success does not prove a future production diagnosis.
          </p>
        </div>
        <nav className={styles.nav} aria-label="Training navigation">
          <Link href="/">Operator View</Link>
          <Link href="/health">Machine Health</Link>
          <Link href="/commissioning">Commissioning Lab</Link>
        </nav>
      </header>

      <section className={styles.ruleStrip} aria-label="Scenario admission rule">
        <div>
          <span>CASE</span>
          <b>LA-T01 · Repeated label-feed jam</b>
        </div>
        <div>
          <span>PROVENANCE</span>
          <b>Field-documented pattern</b>
        </div>
        <div>
          <span>RANDOM INJECTION</span>
          <b>Disabled by design</b>
        </div>
      </section>

      <section className={styles.simulator} aria-label="Interactive training case">
        <div className={styles.simulatorHeader}>
          <div>
            <span>LIVE TRAINING CASE</span>
            <h2>{started ? currentPhase.title : "Case ready — begin from normal operation"}</h2>
          </div>
          <div className={styles.actions}>
            <button type="button" onClick={advance} disabled={advanceDisabled}>
              {advanceLabel}
            </button>
            <button
              className={styles.secondaryButton}
              type="button"
              disabled={!started || jamActive || handoffHold || mechanismRevealed}
              onClick={() => setPaused((current) => !current)}
            >
              {paused ? "Resume" : "Pause"}
            </button>
            <button
              className={styles.secondaryButton}
              type="button"
              disabled={!started || jamActive || handoffHold || mechanismRevealed}
              onClick={() => setSpeed((current) => current === 1 ? 3 : 1)}
            >
              {speed === 1 ? "Fast-forward 3×" : "Normal speed"}
            </button>
            <button className={styles.secondaryButton} type="button" onClick={reset}>Reset</button>
          </div>
        </div>

        <div className={styles.timeline} aria-label="Case timeline">
          {phases.map((item, index) => (
            <div
              className={`${styles.timelineStep} ${started && index <= phase ? styles.timelineActive : ""}`}
              key={item.short}
            >
              <span>{index + 1}</span>
              <b>{item.short}</b>
            </div>
          ))}
        </div>

        <div
          className={`${styles.plantViewport} ${lineMoving ? styles.plantRunning : ""} ${speed === 3 ? styles.plantFast : ""} ${jamActive ? styles.plantJam : ""}`}
          aria-live="polite"
        >
          <div className={styles.plantTopbar}>
            <div>
              <span>LINE STATE</span>
              <b>{lineStatus}</b>
            </div>
            <div>
              <span>ACTIVE ROLE</span>
              <b>{persona.name}</b>
            </div>
            <div>
              <span>PLAYBACK</span>
              <b>{speed}×</b>
            </div>
          </div>

          <div className={styles.machineStage} aria-label="Animated pressure-sensitive label application training line">
            <div className={styles.labelStation}>
              <div className={styles.stationLabel}>LABEL FEED</div>
              <div className={styles.webRoll} aria-hidden="true"><span /></div>
              <div className={styles.webPath} aria-hidden="true"><span /><span /><span /></div>
              <div className={styles.applyHead}>APPLY</div>
              {jamActive && <div className={styles.jamFlag}>JAM OBSERVED</div>}
            </div>

            <div className={styles.conveyor}>
              <div className={styles.conveyorLabel}>PRODUCT FLOW</div>
              <div className={styles.belt} />
              <div className={styles.bottleLane} aria-hidden="true">
                {[0, 1, 2, 3, 4].map((bottle) => (
                  <div
                    className={styles.bottle}
                    key={bottle}
                    style={{ animationDelay: `${bottle * -1.15}s` }}
                  >
                    <span />
                  </div>
                ))}
              </div>
              <div className={styles.inspectionGate}>
                <span>INSPECTION</span>
                <i />
              </div>
            </div>
          </div>

          <div className={styles.sceneText}>
            <div>
              <span>{started ? currentPhase.short.toUpperCase() : "READY"}</span>
              <h3>{started ? currentPhase.title : "Normal operation comes first"}</h3>
              <p>{started ? currentPhase.body : "Start the case and watch the line establish a healthy baseline."}</p>
            </div>
            <div className={styles.observation}>
              <b>Current observation</b>
              <p>{started ? currentPhase.observation : "No event has been introduced."}</p>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.evidenceSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>EVIDENCE WORKBENCH</span>
            <h2>Choose what deserves your attention.</h2>
          </div>
          <small>Available evidence produces a live training readout. Unestablished instrumentation stays greyed out.</small>
        </div>

        <div className={styles.evidenceGrid}>
          {evidenceTools.map((tool) => {
            const availability = evidenceAvailability(tool);
            const selected = selectedEvidence.includes(tool.id);
            return (
              <button
                className={`${styles.evidenceCard} ${selected ? styles.evidenceSelected : ""}`}
                disabled={!availability.selectable}
                key={tool.id}
                onClick={() => toggleEvidence(tool.id)}
                type="button"
              >
                <span>{availability.label}</span>
                <b>{tool.name}</b>
                <small>{tool.note}</small>
              </button>
            );
          })}
        </div>

        <div className={styles.readoutDeck} aria-live="polite">
          {pinnedTools.length === 0 ? (
            <div className={styles.emptyReadout}>
              <span>NO EVIDENCE PINNED</span>
              <b>Pick a useful observation before the next event.</b>
              <p>The game does not auto-fill a dashboard. Your evidence choices shape what stays in view.</p>
            </div>
          ) : pinnedTools.map((tool) => {
            const readout = evidenceReadout(tool.id);
            return (
              <article className={styles.readoutCard} key={tool.id}>
                <span>{tool.name}</span>
                <b>{readout.status}</b>
                <p>{readout.detail}</p>
              </article>
            );
          })}
        </div>
      </section>

      {started && phase >= 2 && phase < 4 && (
        <section className={styles.moverEvidence} aria-live="polite">
          <div>
            <span>MOST DISCRIMINATING EVIDENCE</span>
            <b>The symptom recurs at the same cycle point.</b>
          </div>
          <p>
            That recurrence earns a narrower investigation and a better handoff. It does not, by itself,
            establish the physical mechanism behind a real machine event.
          </p>
        </section>
      )}

      <section className={styles.personaSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>ROLE HANDOFF</span>
            <h2>Evidence moves forward. Roles unlock only when justified.</h2>
          </div>
          <small>LA-T01 does not force every discipline into the incident just because the simulator knows they exist.</small>
        </div>

        <div className={styles.personaTabs} role="tablist" aria-label="Plant personas">
          {personas.map((candidate) => {
            const unlocked = unlockedPersonas.includes(candidate.id);
            return (
              <button
                aria-selected={personaId === candidate.id}
                className={`${personaId === candidate.id ? styles.personaSelected : ""} ${!unlocked ? styles.personaLocked : ""}`}
                disabled={!unlocked}
                key={candidate.id}
                onClick={() => setPersonaId(candidate.id)}
                role="tab"
                type="button"
              >
                <span>{candidate.name}</span>
                <small>{unlocked ? "UNLOCKED" : "NOT JUSTIFIED"}</small>
              </button>
            );
          })}
        </div>

        <div className={styles.personaDetail}>
          <div>
            <span>CURRENT PERSONA</span>
            <h3>{persona.name}</h3>
            <p>{persona.purpose}</p>
          </div>
          <div>
            <span>AVAILABLE VIEW / TOOLS</span>
            <ul>
              {persona.tools.map((tool) => <li key={tool}>{tool}</li>)}
            </ul>
          </div>
          <div className={styles.authorityBoundary}>
            <span>AUTHORITY BOUNDARY</span>
            <p>{persona.boundary}</p>
          </div>
        </div>

        <div className={styles.handoffPanel}>
          <div>
            <span>{personaId === "operator" ? "OPERATOR HANDOFF PACKAGE" : "HANDOFF RECEIVED"}</span>
            <h3>{personaId === "operator" ? "Earn the maintenance escalation." : "Carry the evidence forward."}</h3>
            {personaId === "operator" ? (
              <ul className={styles.handoffChecklist}>
                <li className={hasHistory ? styles.checkComplete : ""}>Jam event history pinned</li>
                <li className={hasRecurrence ? styles.checkComplete : ""}>Recurrence watch pinned</li>
                <li className={phase >= 2 ? styles.checkComplete : ""}>Repeated event observed</li>
              </ul>
            ) : (
              <p>
                Maintenance inherits the operator timeline. The next useful move is a physical web-path inspection,
                not a fresh guess at controls, networking, or an invented sensor value.
              </p>
            )}
          </div>
          {personaId === "operator" ? (
            <button type="button" disabled={!canHandoff} onClick={handoffToMaintenance}>
              Handoff to Maintenance →
            </button>
          ) : (
            <div className={styles.handoffBadge}>Operator evidence retained</div>
          )}
        </div>
      </section>

      <section className={styles.driftCoach} aria-live="polite">
        <div>
          <span>DR. DRIFT · CONTEXT COACH</span>
          <b>Think about the next discriminating observation.</b>
        </div>
        <p>{driftMessage}</p>
      </section>

      <section className={styles.caseGrid}>
        <article className={styles.caseCard}>
          <div className={styles.cardTopline}>
            <span>LA-T01</span>
            <span className={styles.admitted}>FIELD-DOCUMENTED PATTERN</span>
          </div>
          <h2>{mechanismRevealed ? "Label web tension inconsistency" : "Repeated label-feed jam"}</h2>
          <p>
            {mechanismRevealed
              ? "The scripted mechanism is now visible for debrief. It remains a training pattern, not a claim about a specific plant incident."
              : "The player sees the symptom and evidence path first. The source-backed training mechanism stays hidden until debrief."}
          </p>
          <dl className={styles.caseFacts}>
            <div><dt>Documented symptom</dt><dd>Repeated applicator jams at the same cycle point</dd></div>
            <div><dt>Equipment scope</dt><dd>Pressure-sensitive label application / web handling</dd></div>
            <div><dt>Site validation</dt><dd>Not yet performed</dd></div>
            <div><dt>Mechanism</dt><dd>{mechanismRevealed ? "Inconsistent label-web tension" : "Hidden until debrief"}</dd></div>
          </dl>
          {mechanismRevealed ? (
            <div className={styles.sourceLinks}>
              <a href="https://www.packleaderusa.com/blog/how-to-diagnose-misapplied-pharma-labels-in-2026" target="_blank" rel="noreferrer">
                Primary field-pattern source ↗
              </a>
              <a href="https://www.videojet.com/us/homepage/products/labelers/videojet-9310.html" target="_blank" rel="noreferrer">
                Corroborating manufacturer source ↗
              </a>
            </div>
          ) : (
            <div className={styles.lockedSource}>Source detail is held until debrief so it does not spoil the exercise.</div>
          )}
        </article>

        <article className={styles.boundaryCard}>
          <span>CASE CLASSIFICATION</span>
          <h2>{mechanismRevealed ? "Mechanism revealed for this exercise" : "Diagnosis intentionally withheld"}</h2>
          <p>
            Training may script a known mechanism, but the player still has to earn the evidence path.
            A historical case never becomes automatic proof of a future machine root cause.
          </p>
          <div className={styles.driftNote}>
            <b>Case boundary</b>
            <p>Successful exercise ≠ safe production change. Recommendation ≠ authorized action.</p>
          </div>
        </article>
      </section>

      <section className={styles.provenanceBoundary}>
        <div>
          <span>PROVENANCE BOUNDARY</span>
          <h2>Historical pattern ≠ current root cause.</h2>
        </div>
        <p>
          The simulator may teach from documented field patterns. A future production LineAlert finding still has to
          earn its conclusion from current machine evidence, commissioned context, and the authority of the reviewing role.
        </p>
        <Link href="/commissioning">Synthetic engineering fixtures stay in Commissioning Lab →</Link>
      </section>
    </main>
  );
}
