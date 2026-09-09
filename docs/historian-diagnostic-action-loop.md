# Historian-fed bounded action loop

LineAlert's operator workflow consumes two different forms of history and keeps them distinct:

1. **machine/sensor history** from the deterministic diagnostic projection and historian; and
2. **maintenance history** from the CMMS.

The synthetic Labeler 2 demonstration intentionally assumes both are rich enough to be useful.

```text
current machine evidence
        +
matched historical machine windows
        +
CMMS maintenance cases
        +
operator observation
        +
commissioned topology / action catalog
        |
        v
rank bounded actions
        |
        v
operator chooses one routine action
        |
        v
LineAlert arms five-bottle evidence window
        |
        v
operator executes from HMI
        |
        v
new machine / camera / quality evidence
        |
        v
human review -> rerank -> production verification
```

## Diagnostic ranking semantics

The older Diagnostic Projection Engine remains useful because it can promote checks aligned with abnormal measured relationships and deprioritize paths whose supplied relationships remain inside healthy envelopes. The operator workflow does not replace that engine; it turns its bounded findings into an understandable next-action loop.

CMMS history answers a different question: what did qualified people find and do in similar documented maintenance cases? A repeated CMMS correction can increase the information value of a standard action, but it does not turn the historical repair into the current diagnosis.

The synthetic demo therefore heavily ranks the standard guide/spacing restoration because current presentation evidence, matched machine-history episodes, and CMMS history converge on that action. The timing-first path moves down because supplied current and historical timing evidence remains healthy.

## Trial feedback

After the one standard change, the five-bottle trial creates a new bounded evidence window. In the fixture, presentation variability moves from 21.6 ms SD toward the matched healthy window of 7.8 ms, reaching 9.1 ms, while camera/quality evidence also improves. The action therefore gains support for production verification.

That is still an observed intervention-response association. It is not proof that the guide/spacing relationship was the physical root cause.

## Boundaries

- telemetry != diagnosis
- historical machine pattern != current root cause
- CMMS repair pattern != current root cause
- healthy evidence can deprioritize a path without proving physical health
- intervention followed by improvement != causal proof
- LineAlert trial arm != equipment execution
- successful five-bottle trial != safe production change
- production recovery requires separate production-condition evidence
