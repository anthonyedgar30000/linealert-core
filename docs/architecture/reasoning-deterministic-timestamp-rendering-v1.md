# Reasoning deterministic timestamp rendering v1

## Purpose

The Reasoning Inputs page server-renders historian evidence and then hydrates
the same tree in the browser. Timestamp display therefore must be deterministic
across the server and client environments.

A live LAN browser surfaced a recoverable React hydration error because the
same timestamp was formatted differently by the server locale and Chrome:

- client: 9/29/2026, 3:49:05 PM
- server: 2026-09-29, 3:49:05 p.m.

The underlying historian timestamp and evidence record were identical. The
failure was a presentation-format mismatch caused by Date.toLocaleString().

## Fix

Historian timestamps rendered by the Reasoning Inputs client now normalize a
valid source timestamp with Date.toISOString() and display:

`YYYY-MM-DD HH:MM:SS UTC`

For example:

`2026-09-29 19:49:05 UTC`

This format is independent of browser locale, server locale, and local timezone.

Invalid input is still displayed verbatim, and an absent timestamp remains
`No timestamp`.

## Evidence preservation

This increment does not rewrite the historian record or change its retained
timestamp. It only changes the human-readable presentation label.

Source identity, original ISO timestamp, clock model basis, clock quality,
asset identity, episode/cycle identity, and other retained evidence fields
remain unchanged.

## Hydration acceptance

The acceptance condition is that the same historian snapshot can be rendered
on the server and hydrated in the LAN browser without a timestamp text mismatch.

The Reasoning Inputs implementation contains no locale-dependent date/time
formatting calls for historian timestamps.

## Runtime acceptance

The LAN-facing `/reasoning` route returned HTTP 200 with live-emulation state and canonical UTC labels in its initial HTML. Headless Chrome then hydrated the same page; the resulting DOM contained live-emulation content and canonical UTC timestamp labels and did not contain either `Hydration failed` or `Recoverable Error`.

## Boundaries

- timestamp_display_normalization != timestamp_source_mutation
- canonical_utc_label != verified_clock_synchronization
- hydration_match != historian_truth
- rendered_timestamp != verified_physical_event_order
- presentation_fix != diagnosis

This increment adds no historian writes, equipment control, inference authority,
safety approval, or return-to-service authority.

## Rollback

Revert the deterministic display helper. No historian data, service-case data,
or equipment rollback is required.
