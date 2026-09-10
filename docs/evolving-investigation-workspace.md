# Evolving investigation workspace

The synthetic Plant Canvas exposes the active Labeler 2 investigation as an in-page drawer over the still-running Canvas. The same investigation document remains available as a full-page view at `docs/investigation/`, but normal troubleshooting should not require leaving the plant workflow.

The drawer and full-page view read the same shared synthetic demo session and event journal. As the Canvas records observations, tests, interventions, recommendations, verification, and recovery, the investigation view rerenders from that shared episode state. The purpose is to help choose the next bounded decision while preserving the path by which the working picture changed.

The first implementation is deliberately deterministic and synthetic. It does not use an LLM to generate or promote hypotheses, it does not write to equipment, and it does not create a new authority path.

## Decision model

```text
current admitted evidence
        ↓
multiple working explanations
        ↓
best next bounded / discriminating step
        ↓
observation, test, or authorized intervention
        ↓
new evidence
        ↓
reranked working explanations
        ↓
bounded verification or escalation
```

The investigation does not need to converge to one terminal causal verdict. An episode may close because operating behavior is stable under the configured verification conditions, or may escalate because the remaining uncertainty exceeds the current role or playbook boundary.

## Canvas integration

The Plant Canvas remains resident and continues advancing the synthetic simulator while the investigation drawer is open. The drawer hosts the same-origin investigation page in an iframe so both views observe the same browser-local session and journal. Closing the drawer returns directly to the same Canvas state; the full-page link remains available for a larger read-only investigation view.

This integration changes navigation and visibility only. It does not move the simulator into the investigation page, create an independent state engine, or grant the investigation view authority to operate equipment.

## Playbook-learning seam

This page is also the future evidence substrate for asynchronous playbook review. A later, separately governed learning increment can examine preserved episode histories and propose candidate lessons such as which observations changed expert judgment, which low-disturbance tests were most informative, and which interventions repeatedly produced only temporary recovery.

Candidate lessons must have no runtime authority until separately reviewed and commissioned.

## Boundaries

```text
working explanation != diagnosis
investigation priority != causal probability
test response != causal proof
intervention followed by improvement != proof of mechanism
episode closure = bounded operating disposition, not causal certainty
recommendation != authorized action
synthetic demo evidence != physical machine evidence
```
