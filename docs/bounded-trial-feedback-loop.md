# Bounded trial feedback loop

## Product rule

LineAlert should not advance through multiple material changes without a fresh bounded verification run between them.

**Observe → one bounded action → run → automatically collect admitted evidence → auto-assemble the record → human review → continue, stop, escalate, or roll back.**

For this feedback increment, every operator answer on the synthetic Labeler 2 flow creates a requested verification trial before another material change is considered.

## Human-in-the-loop principle

The human should not manually fill out the feedback record after each run.

LineAlert should auto-populate every field that an admitted source can support, preserve where each value came from, and then ask a human primarily for judgment, correction, exceptions, or authorization.

The default interaction is therefore:

**System populates the record → human confirms, corrects, or escalates.**

Example fields include:

- asset identity from the commissioned or currently selected plant context;
- workflow owner from current routing state;
- timestamp and trial identifier from the system/session;
- triggering observation from the preserved operator response;
- run/batch/work-order context when an admitted MES or workflow source exists;
- visual evidence from an admitted camera/classifier source;
- telemetry evidence from an admitted telemetry/historian source;
- quality or reject counts from an admitted quality source;
- authorization source from the governed workflow when available.

Missing sources stay missing. LineAlert must not infer an unavailable telemetry, quality, or authorization value merely to complete a form.

## Evidence-arrival model

In a connected deployment, a completed-run event or admitted source update should trigger record assembly automatically. The operator should not have to re-enter camera findings, telemetry values, reject counts, timestamps, or asset context that LineAlert can already obtain.

The static and browser-session demos cannot receive a real machine/run event. Any demo control that advances the trial represents **receipt of a synthetic completed-run event**, not a human manually entering the feedback and not LineAlert authorizing the run.

## Provenance

Every auto-populated field should retain source class and verification state. At minimum distinguish:

- operator supplied / unverified;
- deterministic workflow-derived;
- system/session generated;
- telemetry/historian sourced;
- AI-camera classified;
- AI-extracted from human text;
- quality-system sourced;
- human confirmed or corrected.

AI-camera output is classified visual evidence. It is not verified physical state, root-cause proof, or authorization to change equipment.

## Trial isolation

The intended experiment discipline is **one material change per trial**. Purely observational checks may be grouped only when the commissioned procedure explicitly permits it and grouping does not obscure which intervention could have affected the result.

Any setting, mechanical, timing, speed, guide, control, firmware, or other material intervention requires its own authorized scope and a fresh run before another intervention is introduced.

## Current demo boundary

The current Plant Canvas implementation is browser-session synthetic feedback content. Its five-container trial size and camera classification are demo parameters, not OEM requirements or commissioned plant truth.

No live camera, PLC/controller, historian, MES, quality system, CMMS, dispatch, safety-control, or equipment-control connection is created by this increment.

A displayed trial request is a workflow recommendation, not production authorization. Trial execution remains subject to site procedure, qualified human authority, safety controls, and OEM requirements.
