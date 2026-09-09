# Triage → Operator → Triage handoff v1

## Product question

Can LineAlert move one active concern from triage to one bounded operator observation and then return ownership to the correct workflow role without exposing the diagnostic model?

## Demo loop

1. A synthetic concern arrives in **TRIAGE**.
2. The shift supervisor may assign exactly one visible-condition check when the check is within operator authority.
3. The item moves to **ASSIGNED · Operator** and the operator sees one question, one reason, and three bounded responses.
4. The operator response is preserved as an **unverified operator observation**.
5. Ownership immediately returns to the workflow:
   - **appears clear** → back to **TRIAGE · Shift supervisor** for the next justified decision;
   - **issue observed** → **ASSIGNED · Maintenance** for qualified inspection;
   - **cannot verify safely** → **ASSIGNED · Maintenance** because operator evidence/authority is exhausted.

## UX contract

The operator surface must not expose a fault-domain dashboard, root-cause ranking, a menu of machine adjustments, or unrelated historical evidence merely because LineAlert has those concepts internally.

The operator interaction is:

> one question → one reason → one safe response

After the response, LineAlert changes workflow ownership rather than asking the operator to participate in the diagnostic model.

## Evidence and authority boundaries

- operator observation != verified physical state
- visible relationship appears clear != mechanism proven healthy
- visible issue observed != root cause established
- cannot verify safely != fault confirmed
- handoff record != dispatch delivery
- recommendation != authorized action
- synthetic demo check != commissioned OEM/site procedure

This increment does not add or change telemetry ingestion, PLC/controller communication, historian schemas, CMMS integration, dispatch delivery, safety controls, or equipment control.

## Persistence boundary

The triage feedback loop is browser-session demo state only. The runtime Operator Actions component may preserve admitted observations through the existing historian path when that runtime is available, but this triage demo does not claim durable workflow persistence or cross-system dispatch.

## Verification

Review the synthetic Labeler 2 item and confirm all three paths:

1. Assign one operator check → **Appears aligned** → item returns to TRIAGE with the observation visible.
2. Assign one operator check → **Appears out of alignment** → item remains ASSIGNED but ownership changes to Maintenance.
3. Assign one operator check → **Can’t verify safely** → item remains ASSIGNED and ownership changes to Maintenance.

In all paths, no machine adjustment is offered and no diagnosis is asserted.
