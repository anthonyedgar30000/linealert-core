# Bounded trial feedback loop

## Product rule

LineAlert should not advance through multiple material changes without a fresh bounded verification run between them.

**Observe → one bounded action → run → automatically collect admitted evidence → auto-assemble the record → human review → rank useful actions → apply plant-specific authority → perform one authorized action → verify.**

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

Useful historical facts include prior symptoms on the same asset, verified historical localization or repair domain, intervention performed, parts replaced, operating conditions, documented verification, technician notes, structured closure information, and recurrence.

The core boundary remains:

**historical_pattern != current_root_cause**

Strong history can move an allowed action sharply up or down in the ranking. It cannot silently become a diagnosis, current physical-state claim, safety approval, or authorization.

As the maintained CMMS record grows, its ranking influence may increase because the historical comparison set becomes richer. Current admitted evidence still matters: a historical pattern that contradicts current evidence should not override current evidence merely because it is frequent.

## Plant-specific action authority

LineAlert must not encode a universal rule such as `operator = observe only` or `maintenance = all machine changes`.

The design rule is:

**Authority belongs to the commissioned action in the current plant context, not to a universal LineAlert job-title assumption.**

The same action may be operator-authorized at one plant, supervisor-gated at another, maintenance-only at another, or prohibited in a particular operating state.

At minimum, the commissioned authority model should be able to bind:

- plant / site;
- asset or asset class;
- action identifier;
- eligible roles;
- operating-state prerequisites;
- authorization class, including standing authority or named approval requirement;
- bounded adjustment envelope when a material change is allowed;
- required tools or safe access conditions where applicable;
- verification requirement;
- rollback requirement;
- supersession / version of the authority rule.

An operator may therefore perform observations, bounded diagnostic checks, recovery actions, controlled trial execution, or bounded adjustments **when that exact action is commissioned to the operator role under the current conditions**.

Standing operator authority does not mean unrestricted discretion. The operator remains bounded by the specific action, asset, operating state, prerequisites, limits, and verification requirements.

The canonical boundaries are:

**role_eligibility != current_authorization**

**operator_authorized != universally_operator_authorized**

**recommendation != authorized_action**

## Rank first, authority second

Evidence ranking and authority evaluation are separate decisions.

LineAlert should first determine which commissioned actions are most useful given current and historical evidence. It should then evaluate the current plant authority profile and either:

1. present an action as immediately available to the current role;
2. route it for the required approval while preserving that the current role may execute after approval;
3. route it to a different qualified role; or
4. suppress it if the commissioned conditions are not satisfied.

This prevents job title from distorting the diagnostic ranking while still preventing unauthorized execution.

For example, the current synthetic Labeler 2 authority profile demonstrates:

- presentation observation: standing operator authority;
- guide / spacing verification against an approved visible reference: standing operator authority, verification only;
- same-condition bounded verification run: operator may execute after shift-supervisor run release;
- reduced-speed diagnostic trial: operator may execute after shift-supervisor approval and only inside a commissioned bounded envelope;
- timing / peel-geometry investigation: maintenance-only in this synthetic plant.

These are synthetic policy choices for the demo. They are not Speedway/OEM requirements or claims about a real plant.

## Evidence-arrival model

In a connected deployment, a completed-run event or admitted source update should trigger record assembly automatically. The operator should not have to re-enter camera findings, telemetry values, reject counts, timestamps, asset context, maintenance history, or authority context that LineAlert can already obtain.

The static and browser-session demos cannot receive a real machine/run event. Any demo control that advances the trial represents **receipt of synthetic admitted-source events**, not a human manually entering feedback and not LineAlert authorizing the run.

## Provenance

Every auto-populated field should retain source class and verification state. At minimum distinguish operator supplied/unverified, deterministic workflow-derived, system/session generated, telemetry/historian sourced, AI-camera classified, quality-system sourced, CMMS sourced, authority-profile sourced, AI-extracted from human text, and human confirmed or corrected.

AI-camera output is classified visual evidence. CMMS history is historical evidence. Authority-profile data is policy context. None by itself is verified current physical state or root-cause proof.

## Ranked next-action selection

Confirming the assembled evidence record does not close the response loop. It means the human accepts the evidence package as the basis for the next bounded decision.

After confirmation, LineAlert may rank only the next actions admitted for the scenario, procedure, or commissioning context. The ranking should be deterministic and inspectable wherever practical.

The ranking semantics are:

**current evidence alignment + historical support + information value != root-cause probability**

A higher rank means the admitted evidence makes that action more relevant or informative to try next. It does not mean LineAlert has proven the cause, that the action is safe, or that the current user is authorized to perform it.

The UI should expose both the ranking factors and the authority disposition, such as:

- current evidence supports;
- CMMS history supports or weakens;
- available to operator under standing authority;
- operator may execute after supervisor approval;
- route to maintenance;
- material change requires a fresh bounded verification run.

The resulting loop is:

**Current evidence + maintained CMMS history → ranked commissioned actions → authority filter / routing → authorized human performs one bounded action → fresh evidence → rerank.**

An action may move down as new evidence arrives. Historical success can increase relevance but improvement after a current change still does not establish root cause.

## Trial isolation

The intended experiment discipline is **one material change per trial**. Purely observational checks may be grouped only when the commissioned procedure explicitly permits it and grouping does not obscure which intervention could have affected the result.

Any setting, mechanical, timing, speed, guide, control, firmware, or other material intervention requires its own authorized scope and a fresh run before another material change is introduced.

## Current demo boundary

The current Plant Canvas implementation is browser-session synthetic feedback content. Its five-container trial size, camera classification, numeric source values, synthetic CMMS work orders, action rankings, and action-authority profile are demo parameters, not OEM requirements or commissioned plant truth.

No live camera, PLC/controller, historian, MES, quality system, CMMS, dispatch, safety-control, authorization system, or equipment-control connection is created by this increment.

A displayed trial request or ranked action is a workflow recommendation. Execution remains subject to the commissioned authority profile, site procedure, qualified human authority, safety controls, OEM requirements, and commissioned plant knowledge.
