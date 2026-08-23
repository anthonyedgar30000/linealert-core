# Live Microsoft OPC PLC dashboard

This lab connects the LineAlert dashboard to one local Microsoft OPC PLC simulator. It is
read-only and uses explicitly allow-listed nodes. The values are simulator proxies, not verified
conveyor measurements.

## Mapping

| OPC PLC node | LineAlert proxy | Conversion |
| --- | --- | --- |
| `FastDouble1` | Motor RPM | value × 1 RPM |
| `FastDouble2` | Raw independent simulator signal | retained but not treated as bottle timing |
| `SlowDouble1` | Contact pressure | value × 1 PSI |

The qualified RPM proxy drives a deterministic conveyor-motion calculation using the declared
roller diameter, sensor spacing, midpoint slip, and sensor delay. This gives the virtual operator
display a coherent healthy relationship without pretending Microsoft's independent generic tag is
a bottle-arrival sensor. It proves the protocol, timestamp, status-code, freshness, mapping, and
bounded model path. It does not prove physical conveyor state or machine causation.

## Run on Windows

Start the Microsoft simulator with unsecured transport enabled **only for this isolated localhost
lab**. The official image otherwise expects `Basic256Sha256` with `SignAndEncrypt`; a default
anonymous `asyncua` client will be rejected with `BadSecurityPolicyRejected`.

```bat
docker run --rm -it -p 50000:50000 -p 8080:8080 --name linealert-opcplc ^
  mcr.microsoft.com/iotedge/opc-plc:latest ^
  --pn=50000 --autoaccept --ut --sph --sn=5 --sr=10 --st=double --fn=5 --fr=1 --ft=double
```

`--ut` is a disposable-lab concession, not a LineAlert production-security recommendation. Do not
use this command on a production network or as the Panasonic security design.

In a second Command Prompt, from the cloned repository directory, run:

```bat
python -m pip install -e ".[opcua]"
linealert-opcua-bridge --capture-jsonl evidence/opcua/microsoft-opc-plc.jsonl
```

The dependency excludes `asyncua` 1.1.8 because that release returns
`BadServerUriInvalid` when creating a session with Microsoft OPC PLC. If 1.1.8 was installed before
this constraint was added, run `python -m pip install --force-reinstall asyncua==1.1.6`.

Then open <http://localhost:8765>. Do not use the public GitHub Pages URL for the live connection;
the local bridge serves the same dashboard and its qualified telemetry endpoint together.

If the command name is not found, use:

```bat
python -m linealert_core.opcua_bridge
```

The default endpoint is `opc.tcp://localhost:50000`. Override it only when intentionally testing a
different disposable simulator:

```bat
linealert-opcua-bridge --endpoint opc.tcp://localhost:50000
```

Stop the container while the bridge remains running. `/api/telemetry` must switch to
`connected:false`, retain the last observations only as `quality:stale`, and publish
`EVIDENCE.OPCUA_CONNECTION_UNAVAILABLE`. The dashboard must not continue treating the last values
as current.

Replay the captured snapshots without the simulator:

```bat
linealert-opcua-bridge --replay-jsonl evidence/opcua/microsoft-opc-plc.jsonl
```

Replay preserves the original observation identifiers, source timestamps, status codes and reason
codes. It adds replay transport metadata but does not rewrite old evidence into fresh live evidence.

## Semantic admission

Transport qualification and semantic admission are separate gates. The versioned profile at
`profiles/microsoft-opc-plc-proxy-v1.semantic-bindings.json` admits only `FastDouble1` as
`simulated_motor_speed_proxy`, and only when profile, source, asset, read-only state, node identity,
unit, OPC quality and freshness all match. Its scope remains `simulator_only`; it cannot support a
physical-machine claim. Pressure, derived arrival and the raw timing proxy remain visible but
diagnostically inadmissible.

## Enforced boundary

- no automatic node browsing;
- no OPC UA writes or method calls;
- source timestamp and OPC UA status retained;
- missing timestamp, bad/unknown status, nonnumeric value, or stale evidence fails closed;
- disconnect retains the last sample only as explicitly stale evidence;
- optional JSONL capture provides deterministic replay in original record order;
- dashboard publication only; no equipment-control path.
