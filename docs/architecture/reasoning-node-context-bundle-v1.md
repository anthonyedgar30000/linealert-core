# Reasoning Node context bundle v1

## Purpose

The Reasoning Node is a bounded consumer of governed LineAlert evidence. It may retrieve,
assemble, summarize, and help interpret context, but it does not become a source of equipment
truth, diagnostic authority, maintenance authority, engineering approval, safety approval, or
control authority.

The first implementation deliberately does not begin with embeddings or a local LLM. It creates
a deterministic context package that later retrieval adapters and models can consume.

## Core boundary

~~~text
structured sources
  -> retrieval candidates
  -> deterministic admission and classification
  -> linealert.reasoning-context-bundle.v1
  -> optional semantic retrieval / local model / remote model
~~~

The model is downstream of evidence admission.

~~~text
retrieval != diagnosis
semantic_similarity != evidentiary_authority
generated_summary != source_evidence
historical_pattern != current_root_cause
recommendation != authorized_action
sensor_value != verified_physical_state
~~~

## Candidate contract

Every candidate must retain:

- evidence identity;
- asset identity;
- source identity and source class;
- evidence role;
- retrieval method;
- original structured content;
- one or more provenance references;
- semantic-admission state;
- source-binding verification state where the role represents source evidence;
- invalidation and supersession state;
- configuration version when known;
- observation timestamp when known;
- authority classification when known;
- tags without replacing source fields.

The assembler never rewrites source timestamps or source content. Clock evidence is preserved as
ordinary source content and is not interpreted by this increment. Clock quality, drift, temporal
uncertainty, and temporal admissibility remain owned by the separate time-integrity workstream.

## Retrieval methods

DETERMINISTIC_ID and DETERMINISTIC_SCOPE may contribute source evidence when all admission
checks pass.

SEMANTIC_DISCOVERY can only contribute CONTEXT_ONLY. Similarity may discover something useful,
but it cannot elevate the discovered item to evidentiary authority.

This means a future vector index is a discovery accelerator, not an authority store.

## Evidence roles

The bundle distinguishes CURRENT_OBSERVATION, DECLARED_CONFIGURATION, TOPOLOGY, PROCEDURE,
HISTORICAL_OBSERVATION, ANALYTICAL_FINDING, and GENERATED_SUMMARY.

Analytical findings and generated summaries are always CONTEXT_ONLY. They may be useful to a
human or model, but they cannot silently re-enter the source-evidence lane.

## Fail-closed admission

The v1 assembler refuses candidates when:

- asset identity does not match the request;
- evidence is invalidated;
- evidence has been superseded;
- semantic admission failed;
- a source-evidence role lacks verified binding;
- a source-evidence role lacks a declared authority class;
- historical or generated context is disabled by the request;
- semantic discovery is disabled;
- a current-evidence role lacks the requested configuration identity or is bound to a
  different declared configuration;
- duplicate evidence IDs contain conflicting payloads;
- the bounded context-item limit is exceeded.

Historical evidence from a different configuration may remain visible only as CONTEXT_ONLY.
That preserves useful history without implying current applicability.

## Determinism

Candidate input order does not determine output order. The assembler uses an explicit role order
and stable source/evidence keys. The complete bundle receives a SHA-256 digest over canonical JSON.

The digest proves deterministic package identity for the assembled content. It does not prove the
truth of the underlying evidence or the correctness of a diagnosis.

## NUC execution

The module has no network, vector-database, or model dependency. It can run locally with:

~~~powershell
python -m linealert_core.reasoning_context --request request.json --candidates candidates.json --output context-bundle.json
~~~

This makes the NUC useful before model integration: adapters can feed governed candidate records
into a stable package that can be inspected, hashed, logged, replayed, and tested independently
of Ollama.

## Planned adapters

Adapters should be added as separate bounded increments.

### Timescale / historian adapter

Use deterministic asset, episode, relationship, configuration, and time-window queries first.
Preserve historian record identity, evidence authority, operating context, clock evidence, and
database provenance. Database retrieval must remain read-only.

### Repository and equipment-document adapter

Index exact document identity, revision, path, equipment applicability, source authority, and
supersession state. Text chunks must retain their parent document identity and revision.

An embedding hit from an OEM manual is not itself proof that the manual applies to the current
machine. Applicability must be separately established.

### Semantic discovery adapter

Embeddings may broaden recall after deterministic scope filters have selected the eligible corpus.
The returned candidates must remain tagged SEMANTIC_DISCOVERY until a deterministic binding
establishes stronger applicability.

### Local model adapter

A small local model such as a 3B Ollama model may summarize an already assembled bundle, propose
search terms, classify a user question, or help formulate a bounded investigation note.

Its output must be recorded as generated context and must not overwrite source evidence, invent
missing provenance, change evidence admission, grant diagnostic certainty, grant equipment-control
authority, or grant maintenance, engineering, production, or safety authorization.

## Relationship to ChatGPT

A larger remote model can consume the same governed context bundle. The important architectural
property is that local and remote models receive the same source identities and boundaries rather
than each constructing an opaque private evidence set.

The intended path is:

~~~text
Timescale + config + topology + documents
                |
                v
deterministic candidate adapters
                |
                v
reasoning-context-bundle.v1
          /             \
         v               v
local 3B model        ChatGPT
         \               /
          v             v
       bounded analysis / review
~~~

Model choice therefore changes reasoning capacity, not evidence authority.

## Not established by v1

This increment does not establish a vector database, an embedding model, Ollama connectivity,
automatic document ingestion, live Timescale retrieval, production equipment connectivity,
commissioned machine authority, diagnosis, root cause, safe change, or equipment control.

Those remain separate increments with their own evidence and verification.
