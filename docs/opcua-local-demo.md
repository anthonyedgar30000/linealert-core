# Live Microsoft OPC PLC dashboard

This lab connects the LineAlert dashboard to one local Microsoft OPC PLC simulator. It is
read-only and uses explicitly allow-listed nodes. The values are simulator proxies, not verified
conveyor measurements.

## Mapping

| OPC PLC node | LineAlert proxy | Conversion |
| --- | --- | --- |
| `FastDouble1` | Motor RPM | value × 1 RPM |
| `FastDouble2` | Bottle-arrival timing | value × 10 + 1300 ms |
| `SlowDouble1` | Contact pressure | value × 1 PSI |

The conversion places the generic Microsoft signal in the demo model's declared numerical range.
It proves the protocol, timestamp, status-code, freshness, mapping, and dashboard path. It does not
prove conveyor physics or machine causation.

## Run on Windows

Keep the `linealert-opcplc` Docker container running. In a second Command Prompt, from the cloned
repository directory, run:

```bat
python -m pip install -e ".[opcua]"
linealert-opcua-bridge
```

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
