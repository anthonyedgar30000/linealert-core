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

Keep the `linealert-opcplc` Docker container running. In a second Command Prompt, from the cloned
repository directory, run:

```bat
python -m pip install -e ".[opcua]"
linealert-opcua-bridge
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

## Enforced boundary

- no automatic node browsing;
- no OPC UA writes or method calls;
- source timestamp and OPC UA status retained;
- missing timestamp, bad/unknown status, nonnumeric value, or stale evidence fails closed;
- dashboard publication only; no equipment-control path.
