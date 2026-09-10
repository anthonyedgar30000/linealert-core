# Synthetic plant operations context v1

This increment expands the public Plant Canvas outward without turning it into a full factory simulator.

## Scope

Packaging Line 1 remains the detailed LineAlert troubleshooting surface. Two additional synthetic production lines, a two-person maintenance crew, and a small CMMS-style work queue provide plant-level operating context.

The model is deterministic. Calendar date + shift seed the ambient maintenance workload. As the simulated clock advances, scheduled PM, corrective work, inspections, technician occupancy, queue state, and line status advance with it.

## Why this matters

Maintenance availability is no longer a fixed 32-minute demo constant. The displayed response estimate is derived from the current synthetic crew occupancy. A LineAlert concern can therefore have different operational significance depending on what maintenance is already doing.

The public demo can now show interactions such as:

- Packaging Line 2 already consuming a technician for scheduled work.
- Carton Line 1 carrying a queued corrective work order.
- An incoming work order becoming visible during the shift.
- A technician finishing work and reducing the estimated response time for the active LineAlert concern.
- Fast-forward advancing production, staffing, and work-order state together before returning to 1x near the next concern.

## Deliberate limit

This is still a bounded increment. Only Packaging Line 1 has the full interactive concern → bounded trial → rerank → production verification workflow. The other lines are ambient plant context and competing maintenance demand, not yet full incident-specific LineAlert workspaces.

That distinction prevents the static demo from pretending that generic synthetic scenarios are commissioned plant logic.

## Boundaries

- synthetic work order != CMMS truth
- staffing estimate != authorized dispatch
- maintenance ETA != guaranteed response time
- telemetry != diagnosis
- anomaly != fault
- recommendation != authorized action
- simulation outcome != verified physical state

LineAlert observes the synthetic operating plan and context. It does not silently alter technician dispatch, work priority, equipment state, or production authority.
