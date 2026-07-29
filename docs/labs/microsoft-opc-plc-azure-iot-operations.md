# Microsoft OPC PLC Simulator + Azure IoT Operations lab

Status: planning and evidence runbook only  
Tracking issue: #31  
Base repository state: `e8bd1b7bb58112609acf27c2576abe967eda4731`  
Risk classification: Tier 2 planning under Issue #27

## Purpose

Create a disposable Microsoft-hosted lab that proves the following bounded chain:

```text
Microsoft OPC PLC simulator
        ↓ OPC UA inside the isolated cluster
Azure IoT Operations connector for OPC UA
        ↓ MQTT broker / data flow
captured simulator messages and metadata
        ↓ offline translation experiment
LineAlert JSONL fixtures
        ↓ deterministic replay
LineAlert JSON findings
```

This runbook does not add a live LineAlert connector. It does not authorize a network listener, MQTT subscriber, OPC UA client, credentials in this repository, physical-equipment access, or equipment control.

## Canonical boundaries

```text
simulated_tag != verified_physical_state
OPC_UA_connection != LineAlert_ingestion
MQTT_message != normalized_MachineEvent
Azure_asset != commissioned_machine_profile
successful_quickstart != production_readiness
LineAlert_finding != proven_root_cause
recommendation != authorized_action
```

## Selected first environment

Use the Microsoft Azure IoT Operations GitHub Codespaces quickstart with K3s.

This environment is selected because it is disposable, isolated from physical equipment, and documented by Microsoft for exploration. It is not selected for production, performance, scale, safety, or reliability claims.

Official references:

- Azure IoT Operations overview: <https://learn.microsoft.com/azure/iot-operations/overview-iot-operations>
- Codespaces deployment quickstart: <https://learn.microsoft.com/azure/iot-operations/get-started-end-to-end-sample/quickstart-deploy>
- Cluster configuration and OPC PLC simulator: <https://learn.microsoft.com/azure/iot-operations/get-started-end-to-end-sample/quickstart-configure>
- OPC UA connector configuration: <https://learn.microsoft.com/azure/iot-operations/discover-manage-assets/howto-configure-opc-ua>
- Microsoft sample repository: <https://github.com/Azure-Samples/explore-iot-operations>

## Scope

### Included

- one disposable GitHub Codespace;
- one K3s cluster connected to Azure Arc;
- one dedicated Azure resource group;
- one Azure IoT Operations instance;
- the stable connector for OPC UA feature;
- the official Microsoft OPC PLC simulator deployment;
- one explicitly declared OPC UA device endpoint;
- a small allow-list of simulator nodes;
- bounded sample-message capture;
- teardown and residue verification.

### Excluded

- physical PLCs, sensors, actuators, controllers, SCADA, historians, MES, CMMS, or production networks;
- public exposure of OPC UA port `50000`;
- LineAlert runtime deployment;
- live LineAlert OPC UA or MQTT adapter code;
- OPC UA writes, method calls, control, automatic browse expansion, or unrestricted discovery;
- production certificates, production identities, or commissioned equipment baselines;
- ChatGPT or LLM access to raw PLC protocol endpoints;
- claims of root cause, safety, maintenance authorization, or production readiness.

## Preconditions

Before starting, record the following without secrets:

```text
operator:
execution date/time and timezone:
Azure tenant ID:
Azure subscription ID:
Azure region:
resource group name:
Codespace repository/ref:
expected cleanup owner:
```

Required access:

- an Azure subscription;
- an Entra identity with the permissions required by the current Microsoft quickstart;
- a GitHub account able to create Codespaces;
- Visual Studio Code when following the documented Codespaces workflow;
- Azure CLI and required extensions inside the selected environment.

Do not paste passwords, client secrets, tokens, private keys, or certificate private material into this repository or into the evidence package.

## Phase A — capture tool and environment identity

Run these commands before creating resources:

```bash
set -euo pipefail

mkdir -p evidence/azure-opc-plc

az version > evidence/azure-opc-plc/az-version.json
az account show --output json > evidence/azure-opc-plc/azure-account.json
kubectl version --client --output yaml > evidence/azure-opc-plc/kubectl-client.yaml
uname -a > evidence/azure-opc-plc/host.txt
```

Redact only secrets. Preserve tenant, subscription, CLI version, operating-system, and timestamp evidence.

Record the installed Azure extensions:

```bash
az extension list --output json > evidence/azure-opc-plc/az-extensions.json
```

Expected observation:

- Azure CLI is authenticated to the intended tenant and subscription;
- the current `azure-iot-ops` and `connectedk8s` extensions can be installed or upgraded according to the Microsoft quickstart;
- no cluster or simulator exists yet.

Failure response:

- stop on the wrong tenant or subscription;
- stop if the required role assignments cannot be confirmed;
- do not substitute a production subscription or shared production resource group merely to make the quickstart work.

## Phase B — deploy the disposable Azure IoT Operations environment

Follow the current Microsoft Codespaces quickstart rather than copying an old command sequence from memory.

At minimum, preserve the exact commands used to:

1. create or select the dedicated resource group;
2. create the K3s cluster in Codespaces;
3. connect the cluster to Azure Arc;
4. create the schema registry and namespace resources required by the current quickstart;
5. initialize the cluster for Azure IoT Operations;
6. create the Azure IoT Operations instance with the connector for OPC UA enabled.

The current Microsoft quickstart uses commands in this family:

```bash
az iot ops init \
  --cluster "$CLUSTER_NAME" \
  --resource-group "$RESOURCE_GROUP"

az iot ops create \
  --cluster "$CLUSTER_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --name "${CLUSTER_NAME}-instance" \
  --sr-resource-id "$SCHEMA_REGISTRY_RESOURCE_ID" \
  --ns-resource-id "$NAMESPACE_RESOURCE_ID" \
  --broker-frontend-replicas 1 \
  --broker-frontend-workers 1 \
  --broker-backend-part 1 \
  --broker-backend-workers 1 \
  --broker-backend-rf 2 \
  --broker-mem-profile Low \
  --feature opcua.mode=Stable
```

Treat this as a shape, not a permanently pinned command. Compare it with the current Microsoft page immediately before execution.

Capture:

```bash
kubectl get nodes -o wide > evidence/azure-opc-plc/nodes.txt
kubectl get pods -A -o wide > evidence/azure-opc-plc/pods-after-iot-ops.txt
kubectl get events -A --sort-by=.metadata.creationTimestamp \
  > evidence/azure-opc-plc/events-after-iot-ops.txt
```

Expected observation:

- the Arc-connected cluster appears in the intended resource group;
- Azure IoT Operations resources report successful provisioning;
- required pods become ready within the bounds documented by Microsoft;
- no public OPC UA endpoint is created.

Failure response:

- capture pod status, events, Azure deployment errors, and timestamps;
- classify the run as `unavailable` or `incomplete_evidence`;
- do not loosen firewall, identity, or certificate controls without recording and reviewing the change.

## Phase C — pin and deploy the official OPC PLC simulator

The Microsoft quickstart currently deploys the simulator from:

```text
https://raw.githubusercontent.com/Azure-Samples/explore-iot-operations/main/samples/quickstarts/opc-plc-deployment.yaml
```

Download the manifest before applying it so its content can be retained and hashed:

```bash
curl --fail --location --silent --show-error \
  https://raw.githubusercontent.com/Azure-Samples/explore-iot-operations/main/samples/quickstarts/opc-plc-deployment.yaml \
  --output evidence/azure-opc-plc/opc-plc-deployment.yaml

sha256sum evidence/azure-opc-plc/opc-plc-deployment.yaml \
  > evidence/azure-opc-plc/opc-plc-deployment.sha256

kubectl apply -f evidence/azure-opc-plc/opc-plc-deployment.yaml
```

Capture the resolved runtime identity:

```bash
kubectl get deployment,pod,service -A -o yaml \
  > evidence/azure-opc-plc/opc-plc-kubernetes-resources.yaml

kubectl get pods -A -o json \
  > evidence/azure-opc-plc/pods-with-image-ids.json
```

The manifest hash is necessary but insufficient. Preserve the image reference and resolved image digest from the running pod.

Expected observation:

- the simulator pod reaches `Running` and `Ready`;
- its service is reachable from the Azure IoT Operations connector inside the cluster;
- no NodePort, LoadBalancer, ingress, host networking, or public exposure is introduced;
- the simulator uses the sample's documented certificate/trust behavior only within this disposable lab.

Failure response:

- stop on an unexpected image repository, tag, digest, privilege request, host network, host path, or public service;
- retain the manifest and status evidence;
- remove the simulator before continuing.

## Phase D — configure the OPC UA device endpoint

The Microsoft sample currently documents the endpoint as:

```text
opc.tcp://opcplc-000000:50000
```

Create the Azure IoT Operations device and inbound OPC UA endpoint using the current operations experience, Azure CLI, or Bicep procedure from Microsoft.

The current Azure CLI command family is:

```bash
az iot ops ns device create \
  --name opc-ua-connector-cli \
  --resource-group "$RESOURCE_GROUP" \
  --instance "$AIO_INSTANCE"

az iot ops ns device endpoint inbound add opcua \
  --device opc-ua-connector-cli \
  --resource-group "$RESOURCE_GROUP" \
  --instance "$AIO_INSTANCE" \
  --name opc-ua-connector-0 \
  --endpoint-address "opc.tcp://opcplc-000000:50000"
```

For the quickstart sample, anonymous authentication and sample self-signed trust behavior may be used only where the current Microsoft documentation explicitly calls for them. Record the exact setting. Do not carry that setting into preproduction or production.

Capture:

- Azure resource IDs for the device and endpoint;
- endpoint address;
- authentication mode;
- certificate/trust mode;
- creation timestamp;
- connector status and logs needed to establish whether the connection succeeded.

Expected observation:

- the connector establishes an OPC UA session to the simulator service;
- certificate/trust decisions are visible;
- authentication and connection failures remain explicit;
- no write or command capability is configured.

## Phase E — create one bounded asset and node allow-list

Do not import or browse the complete simulator address space automatically.

Choose the smallest node set required to prove telemetry flow. Record for every selected node:

```text
logical name:
OPC UA node ID:
namespace URI or index:
data type:
engineering unit, when supplied:
source timestamp availability:
quality/status availability:
expected update behavior:
Azure asset/data-point identifier:
```

The first run should prefer simple sample variables documented by Microsoft. Do not rename simulator variables to LineAlert event names until the offline mapping stage.

Expected observation:

- only allow-listed nodes generate messages;
- payloads retain enough identity and timing information to distinguish source evidence from receive evidence;
- unknown or malformed node mappings are rejected or visibly degraded.

## Phase F — verify message flow and capture bounded samples

Use the current Microsoft quickstart to verify data reaches its documented MQTT and data-flow destination.

Capture a small, time-bounded sample rather than an unlimited stream. Suggested first window:

```text
maximum duration: 10 minutes
maximum messages retained: 1,000
selected nodes only: yes
secrets retained: no
```

For each retained message, preserve where available:

- simulator/server identity;
- OPC UA node ID;
- source timestamp;
- server timestamp;
- connector receive timestamp;
- quality/status code;
- value and engineering unit;
- Azure device and asset identity;
- topic or route identity;
- connector/session identity;
- payload schema/version evidence.

Expected observation:

- messages are observable downstream of the OPC UA connector;
- values change according to the simulator's documented behavior;
- quality and timestamp evidence are not silently discarded;
- duplicates, gaps, reconnects, and out-of-order evidence remain visible.

This establishes:

```text
simulator_data_reached_Azure_pipeline = supported_by_evidence
```

It does not establish:

```text
LineAlert_received_live_data
physical_machine_state_verified
production_connector_ready
root_cause_proven
```

## Phase G — interruption and recovery experiment

Perform one reversible interruption after the normal path is verified:

1. record the current session and timestamps;
2. stop or scale down only the simulator pod using the documented Kubernetes control;
3. wait for the connector failure state to appear;
4. restore the simulator;
5. record reconnection, new session evidence, message gaps, duplicates, and ordering behavior.

Do not alter the Azure IoT Operations connector to hide the failure.

Expected observation:

- loss of the simulator produces an explicit connection or availability failure;
- recovery is visible;
- any gap or duplicate is retained as evidence;
- the experiment does not affect physical or production equipment.

## Phase H — export only offline mapping evidence

Before any LineAlert integration work, export a bounded payload set and node-contract record to a non-secret evidence location.

Do not commit raw Azure account data, credentials, certificates, tokens, or unrestricted telemetry into this public repository.

A future software-only increment may create sanitized fixtures shaped like:

```json
{
  "event_id": "derived-from-bounded-mapping-rule",
  "source_id": "microsoft-opc-plc-simulator",
  "asset_id": "AZURE-OPC-PLC-DEMO-01",
  "component_id": "candidate-component",
  "event_type": "candidate-event",
  "timestamp": "2026-07-29T23:00:00Z",
  "correlation_id": "candidate-cycle",
  "value": 1.0,
  "unit": null,
  "quality": "good",
  "attributes": {
    "opcua_node_id": "candidate-node-id",
    "opcua_source_timestamp": "2026-07-29T23:00:00Z",
    "adapter_receive_timestamp": "2026-07-29T23:00:00.050000Z",
    "source_session_id": "candidate-session",
    "simulator_image_digest": "sha256:candidate",
    "mapping_version": "candidate-v1",
    "evidence_classification": "simulated"
  }
}
```

Every field marked `candidate` must be replaced by captured and reviewed evidence. The example is not a node map, commissioned profile, or approved mapping.

## Phase I — teardown and rollback

Teardown is part of the experiment, not optional cleanup.

1. capture final status and timestamps;
2. delete the OPC PLC simulator deployment;
3. remove the sample Azure IoT Operations device, asset, and data-flow resources;
4. delete the disposable Azure IoT Operations deployment and Arc-connected cluster according to the current Microsoft cleanup procedure;
5. delete the Codespace;
6. delete the dedicated Azure resource group when no retained resource is required;
7. revoke lab secrets or certificates, if any were created;
8. verify no public endpoint, listener, persistent workload, or equipment-control path remains.

Suggested residue checks:

```bash
az resource list --resource-group "$RESOURCE_GROUP" --output table
kubectl get all -A
kubectl get service -A
```

When the resource group is deleted, verify that it no longer resolves:

```bash
az group exists --name "$RESOURCE_GROUP"
```

Expected result:

```text
false
```

If retained evidence requires the resource group to remain temporarily, record the owner, reason, expiry date, and exact retained resources.

## Evidence package index

Create an index containing:

```text
experiment_id:
issue: 31
operator:
reviewer:
start_timestamp:
end_timestamp:
timezone:
subscription_id:
tenant_id:
resource_group:
cluster:
Azure IoT Operations instance:
simulator manifest SHA-256:
simulator image reference:
simulator image digest:
OPC UA endpoint:
authentication mode:
certificate/trust mode:
selected node IDs:
normal-flow result:
interruption result:
cleanup result:
known gaps:
contradictions:
review sign-off:
```

Preserve source identity, timestamps, clock quality, engineering units, sampling behavior, runtime and configuration versions, test conditions, interventions, and supersession history.

## Failure classifications

Use explicit terminal states:

- `unavailable`
- `rejected`
- `incomplete_evidence`
- `mapping_mismatch`
- `authentication_failure`
- `certificate_mismatch`
- `degraded_clock`
- `transport_gap`
- `unexpected_runtime_identity`
- `cleanup_incomplete`

Do not convert these states into a diagnosis.

## Gate for a future live LineAlert adapter

A live adapter issue may be opened only after the lab evidence package exists and the following are explicit:

- qualified independent reviewer;
- exact OPC UA/MQTT payload contract;
- allow-listed nodes;
- read-only proof;
- no write, method-call, control, or automatic browse capability;
- credential and certificate lifecycle;
- network boundary and listener exposure;
- clock, duplicate, gap, reconnect, and ordering behavior;
- resource limits and restart behavior;
- tests, expected observations, failure states, and rollback;
- fresh named implementation authority.

Implementation authority does not authorize merge, deployment, or physical-equipment connection.

## Run completion criteria

A successful Stage 1 run requires evidence for all of the following:

- official simulator identity is pinned;
- Azure IoT Operations reaches the simulator through the in-cluster OPC UA endpoint;
- bounded selected-node data is visible downstream;
- identity, timestamp, quality, and mapping evidence is captured;
- interruption and recovery behavior is observed;
- cleanup is verified;
- no LineAlert runtime listener or connector was introduced;
- no physical or production equipment was contacted.
