"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import styles from "./training.module.css";

type PersonaId = "operator" | "maintenance" | "instrumentation" | "controls" | "ot" | "engineering";

type Persona = {
  id: PersonaId;
  name: string;
  purpose: string;
  tools: string[];
  boundary: string;
};

type EvidenceTool = {
  name: string;
  state: "available" | "not_assumed";
  note: string;
};

const personas: Persona[] = [
  {
    id: "operator",
    name: "Operator",
    purpose: "Recognize the production symptom, establish recurrence, perform allowed visual checks, and escalate.",
    tools: ["Product / label observation", "Jam recurrence", "Allowed visual web-path check", "Escalation record"],
    boundary: "No hidden-parameter edits, PLC changes, or unapproved mechanical adjustment.",
  },
  {
    id: "maintenance",
    name: "Maintenance",
    purpose: "Inspect the physical label path and mechanical contributors under site/OEM procedure.",
    tools: ["Web path", "Rollers and guides", "Mechanical drag / binding", "Authorized tension mechanism checks"],
    boundary: "Do not infer a controls or network cause from mechanical symptoms alone.",
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
    name: "Recurring jam observation",
    state: "available",
    note: "Source-backed symptom for this training pattern.",
  },
  {
    name: "Visual label-web condition",
    state: "available",
    note: "Used as an observation in the exercise without inventing a numeric threshold.",
  },
  {
    name: "Jam event history",
    state: "available",
    note: "Training timeline records when the recurring symptom appears.",
  },
  {
    name: "Numeric web-tension gauge",
    state: "not_assumed",
    note: "Locked until an actual machine/source establishes that instrumentation and its units.",
  },
  {
    name: "PLC tension tag",
    state: "not_assumed",
    note: "Not invented for the exercise. A real tag must come from equipment documentation or integration evidence.",
  },
  {
    name: "OEM adjustment setpoint",
    state: "not_assumed",
    note: "No training value is supplied without a machine-specific authoritative source.",
  },
];

const phases = [
  {
    short: "Baseline",
    title: "Establish normal operation",
    body: "The line is running. Observe the label path and production outcome before anything goes wrong. The training engine does not reveal a fault name.",
    observation: "No recurring jam is active. Establish what normal looks like with the evidence available to your current persona.",
  },
  {
    short: "Event 1",
    title: "A jam interrupts label feed",
    body: "A label-feed jam occurs. One event is a symptom, not a root cause. Record what happened and avoid changing unrelated settings.",
    observation: "One applicator jam has occurred. The cause remains unproven.",
  },
  {
    short: "Recurrence",
    title: "The same disturbance returns",
    body: "The jam recurs at the same point in the cycle. In this admitted training pattern, recurrence is the cue to investigate the web path and tension condition rather than treating the first reset as resolution.",
    observation: "Repeated jam at the same cycle point is now the strongest new evidence.",
  },
  {
    short: "Handoff",
    title: "Follow the evidence across roles",
    body: "The operator has enough evidence to escalate. Switch personas to see what the next role may inspect, while keeping each role inside its authority and instrumentation boundary.",
    observation: "The case now exposes the role handoff. Evidence travels forward; authority does not automatically travel with it.",
  },
  {
    short: "Debrief",
    title: "Reveal the documented training mechanism",
    body: "This exercise is based on a field-documented relationship between repeated applicator jams and inconsistent label-web tension. That explains this scripted case only; it does not prove the cause of a future real-machine jam.",
    observation: "Case mechanism revealed: label-web tension inconsistency. Historical pattern is not current root cause.",
  },
] as const;

export default function TrainingPage() {
  const [personaId, setPersonaId] = useState<PersonaId>("operator");
  const [started, setStarted] = useState(false);
  const [phase, setPhase] = useState(0);
  const [selectedEvidence, setSelectedEvidence] = useState<string[]>([]);

  const persona = useMemo(
    () => personas.find((candidate) => candidate.id === personaId) ?? personas[0],
    [personaId],
  );

  const currentPhase = phases[phase];
  const mechanismRevealed = started && phase === phases.length - 1;

  const advance = () => {
    if (!started) {
      setStarted(true);
      setPhase(0);
      return;
    }
    setPhase((current) => Math.min(current + 1, phases.length - 1));
  };

  const reset = () => {
    setStarted(false);
    setPhase(0);
    setPersonaId("operator");
    setSelectedEvidence([]);
  };

  const toggleEvidence = (name: string) => {
    setSelectedEvidence((current) => (
      current.includes(name)
        ? current.filter((item) => item !== name)
        : [...current, name]
    ));
  };

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>LINEALERT · PLANT TROUBLESHOOTING LAB</span>
          <h1>Learn the plant by following real failure patterns.</h1>
          <p>
            Training cases must earn admission from field evidence. No random fault generator, no
            invented PLC tags, and no synthetic commissioning fixture silently promoted into a real-world case.
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
          <span>SCENARIO RULE</span>
          <b>Only field-grounded failure patterns become playable.</b>
        </div>
        <div>
          <span>PLAYABLE CASES</span>
          <b>1 admitted pattern</b>
        </div>
        <div>
          <span>RANDOM INJECTION</span>
          <b>Disabled by design</b>
        </div>
      </section>

      <section className={styles.caseGrid}>
        <article className={styles.caseCard}>
          <div className={styles.cardTopline}>
            <span>LA-T01</span>
            <span className={styles.admitted}>FIELD-DOCUMENTED PATTERN</span>
          </div>
          <h2>Label web tension inconsistency</h2>
          <p>
            A pressure-sensitive label application case built from documented industry troubleshooting guidance.
            It is <strong>not</strong> presented as a specific plant incident.
          </p>
          <dl className={styles.caseFacts}>
            <div><dt>Documented symptom</dt><dd>Repeated applicator jams at the same cycle point</dd></div>
            <div><dt>Training mechanism</dt><dd>Loose or overtightened label web causing feed disruption</dd></div>
            <div><dt>Equipment scope</dt><dd>Pressure-sensitive label application / web handling</dd></div>
            <div><dt>Site validation</dt><dd>Not yet performed</dd></div>
          </dl>
          <div className={styles.sourceLinks}>
            <a href="https://www.packleaderusa.com/blog/how-to-diagnose-misapplied-pharma-labels-in-2026" target="_blank" rel="noreferrer">
              Primary field-pattern source ↗
            </a>
            <a href="https://www.videojet.com/us/homepage/products/labelers/videojet-9310.html" target="_blank" rel="noreferrer">
              Corroborating manufacturer source ↗
            </a>
          </div>
        </article>

        <article className={styles.boundaryCard}>
          <span>CASE CLASSIFICATION</span>
          <h2>{mechanismRevealed ? "Label web tension inconsistency" : "Hidden until debrief"}</h2>
          <p>
            The player starts from observable behavior. The simulator knows the scripted mechanism,
            but it does not hand the answer to the current persona before the evidence sequence earns it.
          </p>
          <div className={styles.driftNote}>
            <b>Dr. Drift</b>
            <p>
              {mechanismRevealed
                ? "That mechanism explains this case. On a real line, prove it again from current evidence."
                : "Treat the first symptom as a clue, not a diagnosis. Build the timeline first."}
            </p>
          </div>
        </article>
      </section>

      <section className={styles.simulator} aria-label="Interactive training case">
        <div className={styles.simulatorHeader}>
          <div>
            <span>LIVE TRAINING CASE</span>
            <h2>{started ? currentPhase.title : "Case ready — begin from normal operation"}</h2>
          </div>
          <div className={styles.actions}>
            <button type="button" onClick={advance}>
              {!started ? "Start case" : phase < phases.length - 1 ? "Next meaningful event" : "Case complete"}
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

        <div className={styles.scene} aria-live="polite">
          <div className={styles.lineGraphic} aria-label="Schematic label application line">
            <div className={styles.machine}>LABEL FEED</div>
            <div className={styles.flow}>→</div>
            <div className={styles.machine}>PEEL / APPLY</div>
            <div className={styles.flow}>→</div>
            <div className={styles.machine}>PRODUCT</div>
            <div className={styles.flow}>→</div>
            <div className={styles.machine}>INSPECTION</div>
          </div>
          <div className={styles.sceneText}>
            <span>{started ? currentPhase.short.toUpperCase() : "READY"}</span>
            <h3>{started ? currentPhase.title : "Normal operation comes first"}</h3>
            <p>{started ? currentPhase.body : "Start the case to establish the baseline before the first documented symptom unfolds."}</p>
            <div className={styles.observation}>
              <b>Current observation</b>
              <p>{started ? currentPhase.observation : "No event has been introduced."}</p>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.personaSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>ROLE HANDOFF</span>
            <h2>Same plant. Different evidence and authority.</h2>
          </div>
          <small>Switch roles to see the case through each discipline.</small>
        </div>

        <div className={styles.personaTabs} role="tablist" aria-label="Plant personas">
          {personas.map((candidate) => (
            <button
              aria-selected={personaId === candidate.id}
              className={personaId === candidate.id ? styles.personaSelected : ""}
              key={candidate.id}
              onClick={() => setPersonaId(candidate.id)}
              role="tab"
              type="button"
            >
              {candidate.name}
            </button>
          ))}
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
      </section>

      <section className={styles.evidenceSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span>EVIDENCE INVENTORY</span>
            <h2>Useful gauges are earned too.</h2>
          </div>
          <small>No instrumentation is invented just to make the dashboard look busy.</small>
        </div>

        <div className={styles.evidenceGrid}>
          {evidenceTools.map((tool) => {
            const selectable = tool.state === "available";
            const selected = selectedEvidence.includes(tool.name);
            return (
              <button
                className={`${styles.evidenceCard} ${selected ? styles.evidenceSelected : ""}`}
                disabled={!selectable}
                key={tool.name}
                onClick={() => toggleEvidence(tool.name)}
                type="button"
              >
                <span>{tool.state === "available" ? (selected ? "PINNED" : "AVAILABLE") : "NOT ASSUMED"}</span>
                <b>{tool.name}</b>
                <small>{tool.note}</small>
              </button>
            );
          })}
        </div>
      </section>

      {started && phase >= 2 && (
        <section className={styles.moverEvidence} aria-live="polite">
          <div>
            <span>MOST DISCRIMINATING EVIDENCE</span>
            <b>Recurrence at the same cycle point makes the web path / tension condition worth investigating.</b>
          </div>
          <p>
            In this scripted case, later evidence establishes the documented tension mechanism. In a real incident,
            recurrence would only narrow the investigation; it would not prove root cause by itself.
          </p>
        </section>
      )}

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
