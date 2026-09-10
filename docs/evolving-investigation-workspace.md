# Evolving investigation workspace

The synthetic Plant Canvas can link an active Labeler 2 concern to a dedicated evolving investigation page at `docs/investigation/`.

The page keeps up to three working explanations visible and changes their investigation standing as the existing shared demo session and event journal record tests, interventions, recommendations, verification, and recovery. The purpose is to help choose the next bounded decision while preserving the path by which the working picture changed.

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
