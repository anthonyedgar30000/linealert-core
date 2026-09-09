# Dynamic bounded-action reranking

LineAlert treats the next-action recommendation as a repeatedly recalculated decision-support result, not a one-time diagnosis or fixed troubleshooting tree.

```text
current machine / sensor evidence
        +
latest bounded trial outcome
        +
matched historian windows
        +
CMMS maintenance history
        +
operator observation
        +
commissioned action catalog
        |
        v
rank next bounded actions
        |
        v
operator selects any allowed action
        |
        v
apply one material change
        |
        v
LineAlert arms bounded evidence window
        |
        v
operator executes from HMI
        |
        v
capture new machine / camera / quality evidence
        |
        v
human confirms evidence
        |
        v
recalculate rankings
        |
        +----> repeat or verify in production
```

## Runtime semantics

The highest-ranked action means: **the best-supported next bounded move given the evidence available now**.

It does not mean:
- highest root-cause probability;
- proof of diagnosis;
- automatic authorization;
- an equipment command;
- a guaranteed production fix.

The operator may select another allowed action. LineAlert records what was selected and uses the observed result to rerank the full action catalog after the next bounded evidence window.

## Deterministic branching demo

The synthetic Labeler 2 scenario includes multiple routine operator actions. Each action produces a deterministic synthetic five-container outcome so the demo can show how recommendations move up or down after evidence arrives.

Examples:
- guide / spacing restoration produces strong improvement, so a no-change repeat moves to the top to test repeatability;
- peel-angle adjustment improves visible outcome slightly but leaves presentation variability elevated, so guide / spacing remains highest priority;
- hold-down adjustment adds little useful improvement, so that action family loses priority;
- label-delay adjustment adds no useful improvement while timing evidence remains healthy, so timing-related actions are further deprioritized;
- temporary speed reduction suppresses visible rejects but leaves presentation variability abnormal, supporting rate sensitivity without displacing the presentation-focused action;
- a repeat with no additional change reproduces the improvement, so production verification becomes the next recommended step.

## Trial definition

Five containers is a scenario-specific commissioned trial definition, not a platform constant. A real LineAlert trial may instead be expressed in units, cycles, seconds, batches, or another process-appropriate bounded window.

## Boundaries

- telemetry != diagnosis
- anomaly != fault
- historical pattern != current root cause
- recommendation != authorized action
- intervention followed by improvement != causal proof
- LineAlert trial arm != HMI equipment execution
- successful bounded trial != safe production change
- production recovery requires separate production-condition evidence
