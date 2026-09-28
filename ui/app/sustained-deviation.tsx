"use client";

import { useEffect, useState } from "react";

import styles from "./sustained-deviation.module.css";

type DependencyRelationshipState = {
  relationship_id: string;
  direction: "UPSTREAM" | "DOWNSTREAM";
  topology_from: string;
  topology_to: string;
  state:
    | "WITHIN_ENVELOPE"
    | "INTERMITTENT_OUTSIDE"
    | "PERSISTENT_OUTSIDE"
    | "UNRESOLVED"
    | "CONFLICT"
    | "NO_EVIDENCE";
  sample_count: number;
  good_count: number;
  outside_count: number;
  first_outside_at?: string | null;
  persistence_established_at?: string | null;
};

type DependencyLocalization = {
  asset_id: string;
  target_relationship_id: string;
  disposition:
    | "PERSISTENCE_ESTABLISHED"
    | "PERSISTENCE_NOT_ESTABLISHED"
    | "INSUFFICIENT_EVIDENCE"
    | "EVIDENCE_CONFLICT";
  persistence_rule: {
    required_outside: number;
    window_size: number;
  };
  first_outside_at?: string | null;
  onset?: {
    relationship_id: string;
    first_outside_at: string;
    candidate_start_at: string;
    persistence_established_at: string;
    window_start_at: string;
    window_end_at: string;
    outside_count: number;
    window_count: number;
    observation_ids: string[];
    cycle_ids: string[];
  } | null;
  analysis_window_start?: string | null;
  analysis_window_end?: string | null;
  upstream: DependencyRelationshipState[];
  downstream: DependencyRelationshipState[];
  reasons: string[];
  claim_boundary: string;
};

type PersistencePolicyBinding = {
  policy: {
    policy_id: string;
    policy_revision: string;
    relationship_id: string;
    required_outside: number;
    window_size: number;
    authority_class: string;
    metadata?: Record<string, string>;
  };
  asset_id: string;
  profile_id: string;
  source_name: string;
  source_sha256: string;
};

type PolicyApplication = {
  mode: string;
  historical_policy_equivalence: string;
  reason_code?: string;
  detail: string;
  evidence_basis?: string;
  authority_boundary?: string;
};

type ConfiguredLocalizationPayload = {
  schema_version: string;
  disposition: string;
  reason_code?: string | null;
  detail?: string | null;
  selection_request?: {
    label: string;
    asset_id: string;
    episode_id?: string | null;
    cycle_id?: string | null;
    phase_id?: string | null;
    from_time?: string | null;
    to_time?: string | null;
    limit: number;
  } | null;
  selection?: {
    record_count: number;
    truncated: boolean;
  } | null;
  localization?: DependencyLocalization | null;
  persistence_policy?: PersistencePolicyBinding | null;
  policy_application?: PolicyApplication | null;
  topology_authority?: {
    asset_id: string;
    profile_id: string;
    source_name: string;
    source_sha256: string;
  } | null;
  error?: string;
};

type LocalizationState =
  | { state: "loading" }
  | { state: "active"; payload: ConfiguredLocalizationPayload }
  | { state: "unavailable"; detail: string };

const formatTime = (value?: string | null, fallback = "Not established") => {
  if (!value) return fallback;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
};

const nodeLabel = (value: string) => (
  value
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replaceAll("_", " ")
);

const relationshipLabel = (item: DependencyRelationshipState) => (
  `${nodeLabel(item.topology_from)} → ${nodeLabel(item.topology_to)}`
);

const stateLabel = (state: DependencyRelationshipState["state"]) => {
  const labels: Record<DependencyRelationshipState["state"], string> = {
    WITHIN_ENVELOPE: "Within envelope",
    INTERMITTENT_OUTSIDE: "Intermittent outside",
    PERSISTENT_OUTSIDE: "Persistent outside",
    UNRESOLVED: "Unresolved",
    CONFLICT: "Conflict",
    NO_EVIDENCE: "No evidence",
  };
  return labels[state];
};

const dispositionLabel = (disposition: DependencyLocalization["disposition"]) => {
  const labels: Record<DependencyLocalization["disposition"], string> = {
    PERSISTENCE_ESTABLISHED: "Persistence established",
    PERSISTENCE_NOT_ESTABLISHED: "Persistence not established",
    INSUFFICIENT_EVIDENCE: "Insufficient evidence",
    EVIDENCE_CONFLICT: "Evidence conflict",
  };
  return labels[disposition];
};

function RelationshipGroup({
  label,
  items,
}: {
  label: string;
  items: DependencyRelationshipState[];
}) {
  return (
    <div className={styles.relationshipGroup}>
      <span>{label}</span>
      {items.length ? (
        <div className={styles.relationshipList}>
          {items.map((item) => (
            <article key={item.relationship_id}>
              <div>
                <b>{relationshipLabel(item)}</b>
                <small>
                  {item.sample_count} sample{item.sample_count === 1 ? "" : "s"}
                  {" · "}
                  {item.outside_count} outside
                </small>
              </div>
              <strong className={styles[`state_${item.state}`]}>
                {stateLabel(item.state)}
              </strong>
              {(item.first_outside_at || item.persistence_established_at) && (
                <p>
                  {item.first_outside_at
                    ? `First outside ${formatTime(item.first_outside_at)}`
                    : "No retained outside sample"}
                  {item.persistence_established_at
                    ? ` · persistence ${formatTime(item.persistence_established_at)}`
                    : ""}
                </p>
              )}
            </article>
          ))}
        </div>
      ) : (
        <small className={styles.emptyRelationship}>
          No {label.toLowerCase()} relationship state was returned for this target.
        </small>
      )}
    </div>
  );
}

export default function SustainedDeviation({
  assetId,
  relationshipId,
  episodeId,
}: {
  assetId: string;
  relationshipId: string;
  episodeId: string;
}) {
  const [result, setResult] = useState<LocalizationState>({ state: "loading" });

  useEffect(() => {
    let active = true;

    const load = async () => {
      setResult({ state: "loading" });
      const params = new URLSearchParams({
        asset_id: assetId,
        selection_label: `Technician episode ${episodeId}`,
        target_relationship_id: relationshipId,
        episode_id: episodeId,
        limit: "5000",
      });

      try {
        const response = await fetch(
          `/api/historian/conditions/localize?${params.toString()}`,
          { cache: "no-store" },
        );
        const payload = (await response.json()) as ConfiguredLocalizationPayload;
        if (!active) return;
        if (!payload.disposition) {
          setResult({
            state: "unavailable",
            detail:
              payload.detail
              ?? payload.reason_code
              ?? payload.error
              ?? "Historian localization returned an invalid response.",
          });
          return;
        }
        setResult({ state: "active", payload });
      } catch {
        if (active) {
          setResult({
            state: "unavailable",
            detail: "Configured persistent-localization evidence is unavailable.",
          });
        }
      }
    };

    load();
    return () => {
      active = false;
    };
  }, [assetId, relationshipId, episodeId]);

  if (result.state === "loading") {
    return (
      <section className={styles.panel} aria-label="Sustained deviation evidence">
        <div className={styles.header}>
          <div>
            <span>SUSTAINED DEVIATION · READ ONLY</span>
            <b>Configured persistence over incident history</b>
          </div>
          <small>Loading governed historian evidence…</small>
        </div>
      </section>
    );
  }

  if (result.state === "unavailable") {
    return (
      <section className={styles.panel} aria-label="Sustained deviation evidence">
        <div className={styles.header}>
          <div>
            <span>SUSTAINED DEVIATION · READ ONLY</span>
            <b>Configured persistence over incident history</b>
          </div>
          <small>Backend-derived only</small>
        </div>
        <div className={styles.refused}>
          <span>LOCALIZATION UNAVAILABLE</span>
          <b>{result.detail}</b>
          <small>No browser-side persistence result is substituted.</small>
        </div>
      </section>
    );
  }

  const payload = result.payload;
  const policy = payload.persistence_policy;
  const localization = payload.localization;
  const configuredCriterion = policy
    ? `${policy.policy.required_outside} of ${policy.policy.window_size} outside envelope`
    : "No configured criterion";

  if (payload.disposition !== "READY" || !localization) {
    return (
      <section className={styles.panel} aria-label="Sustained deviation evidence">
        <div className={styles.header}>
          <div>
            <span>SUSTAINED DEVIATION · READ ONLY</span>
            <b>Configured persistence over incident history</b>
          </div>
          <small>Backend-derived only</small>
        </div>

        <div className={styles.refused}>
          <span>{payload.disposition === "UNAVAILABLE" ? "LOCALIZATION UNAVAILABLE" : "LOCALIZATION NOT ADMITTED"}</span>
          <b>{payload.detail ?? payload.reason_code ?? payload.disposition}</b>
          {payload.reason_code && <small>{payload.reason_code}</small>}
        </div>

        {policy && (
          <div className={styles.policyStrip}>
            <div>
              <span>CONFIGURED CRITERION</span>
              <b>{configuredCriterion}</b>
            </div>
            <small>
              {policy.policy.policy_id} · rev {policy.policy.policy_revision}
            </small>
          </div>
        )}

        {payload.policy_application && (
          <div className={styles.policyCaveat}>
            <b>
              Historian write-time policy equivalence:{" "}
              {payload.policy_application.historical_policy_equivalence}
            </b>
            <small>{payload.policy_application.detail}</small>
            {payload.policy_application.authority_boundary && (
              <small>{payload.policy_application.authority_boundary}</small>
            )}
          </div>
        )}
      </section>
    );
  }

  const established = localization.disposition === "PERSISTENCE_ESTABLISHED";
  const policyApplication = payload.policy_application;
  const topologyAuthority = payload.topology_authority;

  return (
    <section className={styles.panel} aria-label="Sustained deviation evidence">
      <div className={styles.header}>
        <div>
          <span>SUSTAINED DEVIATION · READ ONLY</span>
          <b>Configured persistence over incident history</b>
        </div>
        <small>
          Backend policy + historian evidence · browser does not calculate persistence
        </small>
      </div>

      <div className={established ? styles.resultEstablished : styles.resultBounded}>
        <span>{dispositionLabel(localization.disposition).toUpperCase()}</span>
        <b>
          {established && localization.onset
            ? `${localization.onset.outside_count} of ${localization.onset.window_count} retained samples satisfied the configured criterion.`
            : localization.reasons.at(0) ?? "The backend returned a bounded persistence result."}
        </b>
      </div>

      <div className={styles.summaryGrid}>
        <div>
          <span>First outside</span>
          <b>{formatTime(localization.first_outside_at, "None retained")}</b>
        </div>
        <div>
          <span>Persistence established</span>
          <b>{formatTime(localization.onset?.persistence_established_at)}</b>
        </div>
        <div>
          <span>Configured criterion</span>
          <b>{configuredCriterion}</b>
        </div>
      </div>

      {policy && (
        <div className={styles.policyStrip}>
          <div>
            <span>POLICY</span>
            <b>
              {policy.policy.policy_id} · rev {policy.policy.policy_revision}
            </b>
          </div>
          <small>
            {policy.policy.authority_class}
            {" · "}
            {policy.source_name}
            {" · "}
            {policy.source_sha256.slice(0, 12)}…
          </small>
        </div>
      )}

      <div className={styles.relationshipGrid}>
        <RelationshipGroup label="Upstream" items={localization.upstream} />
        <RelationshipGroup label="Downstream" items={localization.downstream} />
      </div>

      {policyApplication && (
        <div className={styles.policyCaveat}>
          <b>
            Historian write-time policy equivalence ·{" "}
            {policyApplication.historical_policy_equivalence.toLowerCase()}
          </b>
          <small>{policyApplication.detail}</small>
          {policyApplication.authority_boundary && (
            <small>{policyApplication.authority_boundary}</small>
          )}
        </div>
      )}

      {topologyAuthority && (
        <small className={styles.provenance}>
          Topology authority · {topologyAuthority.profile_id} · {topologyAuthority.source_name} ·{" "}
          {topologyAuthority.source_sha256.slice(0, 12)}…
        </small>
      )}

      <small className={styles.boundary}>{localization.claim_boundary}</small>
    </section>
  );
}
