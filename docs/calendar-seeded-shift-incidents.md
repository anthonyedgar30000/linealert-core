# Calendar-seeded shift incident simulation

The public Plant Canvas demo uses a deterministic synthetic calendar so the plant can run through clean shifts and occasional concern shifts without creating an unbounded ticket stream.

## Shift model

The demo rotates through three eight-hour shifts:

- Day: 06:00–14:00
- Evening: 14:00–22:00
- Night: 22:00–06:00

The displayed calendar date is initialized from the viewer's browser calendar date. The demo time starts at 14:00 for repeatable playback. Calendar arithmetic is synthetic and deterministic; it is not a plant timestamp source.

## Incident scheduling

Each shift is seeded from:

`calendar seed + shift-start calendar date + shift code`

The synthetic frequency profile is intentionally sparse:

- 80% clean shifts
- 10% alignment-after-roll-change concern
- 5% peel-edge instability concern
- 3% hold-down contact instability concern
- 2% rate-sensitive skew concern

At most one synthetic incident is scheduled in a shift. If an incident is scheduled, its time is also deterministic and is placed between 45 minutes after shift start and 45 minutes before that shift's hard operating window.

These percentages are demo parameters only. They are not observed reliability rates, OEM failure rates, plant forecasts, or predictive-maintenance claims.

## Playback

`Speed up to next incident` searches future shifts for the next scheduled synthetic concern. Fast-forward advances calendar time, shift state, counts, buffers, and telemetry together, then returns to 1x wall-clock playback 30 seconds before the concern is due to emerge.

The existing bounded workflow remains unchanged after a concern is active:

`concern -> ranked bounded action -> human choice -> diagnostic trial -> rerank -> production verification -> recovery observed`

The initial ranked action can differ by the synthetic incident family.

## Ticket-history bound

The browser demo does not append an unlimited history. It reconstructs a deterministic rolling 30-day shift history and renders no more than 12 detailed incident tickets. Older shift detail is represented by rolling counts of flagged and clean completed shifts.

Per-incident Decision History remains scoped to the current active or most recently recovered incident and is reset when a new scheduled concern begins.

Synthetic incident IDs use:

`INC-YYYYMMDD-SHIFT-01`

where the date is the calendar date on which that shift started.

## Boundaries

- synthetic frequency != plant failure rate
- scheduled synthetic incident != predicted real incident
- telemetry != diagnosis
- anomaly != fault
- historical pattern != current root cause
- recommendation != authorized action
- recovery observed != root-cause proof or future reliability guarantee
