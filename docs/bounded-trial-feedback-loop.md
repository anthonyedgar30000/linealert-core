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

## Ranked next-option selection

Confirming the assembled evidence record does not close the response loop. It means the human accepts the evidence package as the basis for the next bounded decision.

After confirmation, LineAlert may rank only the **allowed next options** that are already admitted for the scenario, procedure, role, or commissioning context. The ranking should be deterministic and inspectable wherever practical.

The ranking semantics are:

**evidence alignment and information value != root-cause probability**

A higher rank means the current admitted evidence makes that option more relevant or more informative to try next. It does not mean LineAlert has proven the cause, that the option is safe, or that the user is authorized to perform it.

The UI should expose the factors that moved an option up or down, for example:

- operator observation supports;
- telemetry relationship supports;
- camera evidence supports;
- no direct evidence available;
- unchanged operating variable weakens a rate-change explanation;
- option preserves like-for-like comparison and one-variable discipline.

The human selects one option. Selection records workflow intent only. It does not authorize the intervention, execute a machine change, bypass a safety control, or replace a commissioned procedure.

For any material intervention, the next required state is a fresh bounded run before another material change is introduced.

The resulting loop is:

**Evidence → ranked allowed options → human selects → authorization / execution outside LineAlert authority → fresh bounded run → new evidence → rerank.**

An option may move down as new evidence arrives. A successful trial after an intervention may increase the information value of that intervention family, but improvement after a change still does not establish root cause.

## Trial isolation

The intended experiment discipline is **one material change per trial**. Purely observational checks may be grouped only when the commissioned procedure explicitly permits it and grouping does not obscure which intervention could have affected the result.

Any setting, mechanical, timing, speed, guide, control, firmware, or other material intervention requires its own authorized scope and a fresh run before another intervention is introduced.

## Current demo boundary

The current Plant Canvas implementation is browser-session synthetic feedback content. Its five-container trial size, camera classification, numeric source values, and evidence-ranked next options are demo parameters, not OEM requirements or commissioned plant truth.

No live camera, PLC/controller, historian, MES, quality system, CMMS, dispatch, safety-control, or equipment-control connection is created by this increment.

A displayed trial request or ranked option is a workflow recommendation, not production authorization. Trial execution and any intervention remain subject to site procedure, qualified human authority, safety controls, OEM requirements, and commissioned plant knowledge.
