# garmin-toolbox — MCP server

MCP server for athletic computation + Garmin Connect ops. Companion to
`garmin-coach` (read InfluxDB) and `grafana-mcp-server` (Grafana proxy) in the
NAS stack.

## What it does

5 internal modules, exposed as ~13 MCP tools:

- **pace** — pure math (pace ↔ km/h, distance, multi-segment session predictor)
- **metrics** — TRIMP, ACWR, CTL/ATL/TSB, polarization, decoupling, HR drift (read InfluxDB)
- **dump** — per-second activity dump with weather (read InfluxDB + Open-Meteo, write volume)
- **workouts_plan** — read `workouts_data.py` (the Bedrock plan)
- **garmin_write** — upload / schedule / delete workouts on Garmin Connect

## Stack integration

Lives in the same Docker network as `garmin-grafana-mcp-stack` (network
`garmingrafana_default`), shares the InfluxDB host (`influxdb:8086`) and the
Garmin token cache volume (`/volume2/docker/garmingrafana/garminconnect-tokens/`).

Exposed on port **8769** via streamable HTTP transport (`POST /mcp`).

## Files

| File | Role |
|---|---|
| `server.py` | FastMCP entrypoint + tool registration |
| `tools/` | One module per MCP tool group |
| `lib/influx.py` | Shared InfluxDB v1.x client |
| `lib/garmin.py` | Shared Garmin Connect login helper |
| `workouts_data.py` | Source of truth for the Bedrock training plan |
| `activities/` | Per-activity JSON dumps (mounted volume, accessible via SMB) |
| `Dockerfile` | python:3.11-slim image |
| `docker-compose.fragment.yml` | Service definition to merge into the main stack |

## Wiring in Claude Code

`~/.claude.json`:

```json
"garmin-toolbox": {
  "type": "http",
  "url": "http://192.168.1.59:8769/mcp"
}
```
