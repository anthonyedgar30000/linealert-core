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

Example fields include asset identity, workflow owner, timestamp, trial identifier, triggering observation, run context, visual evidence, telemetry evidence, quality evidence, maintenance-history context, and authorization source when available.

Missing sources stay missing. LineAlert must not infer an unavailable value merely to complete a form.

## Product-design assumption: excellent CMMS history

For the current product-vision path, assume the plant's CMMS history is **rich, clean, correctly asset-linked, structured enough to interpret, and consistently maintained**.

This is a deliberate design assumption, not a claim about every real plant. It exists so LineAlert can be designed around the long-term value of accumulated maintenance history instead of treating CMMS context as a marginal optional feature.

Under that assumption, historical maintenance evidence is a first-class input alongside current telemetry, camera/quality evidence, operator observations, topology, and approved procedures.

Useful historical facts include:

- prior symptoms on the same asset;
- verified historical localization or repair domain;
- intervention performed;
- parts replaced;
- operating conditions during the event;
- whether the intervention held during documented verification;
- technician notes and structured closure information;
- recurrence after an earlier intervention.

The core boundary remains:

**historical_pattern != current_root_cause**

Strong history can move an allowed intervention sharply up or down in the ranking. It cannot silently become a diagnosis, current physical-state claim, safety approval, or authorization.

As the maintained CMMS record grows, its ranking influence may increase because the historical comparison set becomes richer. Current admitted evidence still matters: a historical pattern that contradicts current evidence should not override the current evidence merely because it is frequent.

## Evidence-arrival model

In a connected deployment, a completed-run event or admitted source update should trigger record assembly automatically. The operator should not have to re-enter camera findings, telemetry values, reject counts, timestamps, asset context, or maintenance history that LineAlert can already obtain.

The static and browser-session demos cannot receive a real machine/run event. Any demo control that advances the trial represents **receipt of synthetic admitted-source events**, not a human manually entering feedback and not LineAlert authorizing the run.

## Provenance

Every auto-populated field should retain source class and verification state. At minimum distinguish operator supplied/unverified, deterministic workflow-derived, system/session generated, telemetry/historian sourced, AI-camera classified, quality-system sourced, CMMS sourced, AI-extracted from human text, and human confirmed or corrected.

AI-camera output is classified visual evidence. CMMS history is historical evidence. Neither is verified current physical state, root-cause proof, or authorization to change equipment.

## Ranked next-option selection

Confirming the assembled evidence record does not close the response loop. It means the human accepts the evidence package as the basis for the next bounded decision.

After confirmation, LineAlert may rank only the **allowed next options** already admitted for the scenario, procedure, role, or commissioning context. The ranking should be deterministic and inspectable wherever practical.

The ranking semantics are:

**current evidence alignment + historical support + information value != root-cause probability**

A higher rank means the admitted evidence makes that option more relevant or informative to try next. It does not mean LineAlert has proven the cause, that the option is safe, or that the user is authorized to perform it.

The UI should expose the factors that moved an option up or down, including current operator/telemetry/camera/quality evidence, similar historical cases, historically effective interventions, historical contradictions, unchanged operating variables, and whether the option preserves like-for-like comparison and one-variable discipline.

The human selects one option. Selection records workflow intent only. It does not authorize the intervention, execute a machine change, bypass a safety control, or replace a commissioned procedure.

For any material intervention, the next required state is a fresh bounded run before another material change is introduced.

The resulting loop is:

**Current evidence + maintained CMMS history → ranked allowed options → human selects → authorization / execution outside LineAlert authority → fresh bounded run → new evidence → rerank.**

An option may move down as new evidence arrives. Historical success can increase relevance but improvement after a current change still does not establish root cause.

## Trial isolation

The intended experiment discipline is **one material change per trial**. Purely observational checks may be grouped only when the commissioned procedure explicitly permits it and grouping does not obscure which intervention could have affected the result.

Any setting, mechanical, timing, speed, guide, control, firmware, or other material intervention requires its own authorized scope and a fresh run before another intervention is introduced.

## Current demo boundary

The current Plant Canvas implementation is browser-session synthetic feedback content. Its five-container trial size, camera classification, numeric source values, synthetic CMMS work orders, and evidence-ranked next options are demo parameters, not OEM requirements or commissioned plant truth.

No live camera, PLC/controller, historian, MES, quality system, CMMS, dispatch, safety-control, or equipment-control connection is created by this increment.

A displayed trial request or ranked option is a workflow recommendation, not production authorization. Trial execution and any intervention remain subject to site procedure, qualified human authority, safety controls, OEM requirements, and commissioned plant knowledge.
