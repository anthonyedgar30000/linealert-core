# Plant Canvas v1

## Product role

The Plant Canvas is the primary synthetic feedback surface for LineAlert. It answers:

- where is the concern?
- what does it affect?
- who owns the next step?
- what is the next bounded action?
- does the current plan still hold?

The Triage Board remains an alternate workflow view of the same browser-session state.

## Synthetic topology

Packaging Line 1 is represented as:

Filler 1 -> Labeler 2 -> Case Packer 1 -> Palletizer 1

This topology is illustrative feedback content. It is not commissioned plant truth and is not sourced from OEM drawings, electrical documentation, controls code, or physical commissioning evidence.

## Interaction

Labeler 2 carries the existing synthetic alignment concern. Selecting the asset exposes owner, posture, runway, response ETA, latest observation, and one next action. The shift supervisor can assign one bounded operator check. The operator result changes ownership on the same canvas state:

- appears aligned -> returns to shift-supervisor triage
- appears out of alignment -> maintenance owns the next step
- cannot verify safely -> maintenance owns the next step

The result is an operator observation, not verified physical state or root-cause proof.

## Deliberately excluded

- drag/drop plant builder
- persistent topology storage
- live telemetry or historian binding
- PLC/controller communication
- CMMS or dispatch integration
- automatic topology inference
- AI-authored commissioned truth
- autonomous equipment action
- safety approval or adjustment authority

## Next validation question

Can a plant or OEM reviewer look at the canvas and quickly say whether the modeled assets, ownership, dependency direction, and next-step handoff resemble how work actually happens?
