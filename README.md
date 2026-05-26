# garmin-toolbox

MCP server for athletic computation and Garmin Connect operations. Built with
[FastMCP](https://github.com/jlowin/fastmcp), exposed via streamable HTTP
transport (`POST /mcp`).

Part of the [Garvis Coach](https://github.com/thibaultherve/garvis-coach)
stack, but can run standalone.

## What it does

13 tools in 5 modules:

| Module | Tools | Description |
|---|---|---|
| **pace** | `compute_pace` | Pure math: pace ↔ km/h, distance from pace + time, multi-segment session predictor |
| **metrics** | `compute_trimp`, `compute_acwr`, `compute_ctl_atl_tsb`, `compute_polarization`, `compute_decoupling`, `compute_hr_drift` | Training load metrics from InfluxDB activity data |
| **dump** | `dump_activity` | Per-second activity dump (summary + laps + workout steps + GPS + Open-Meteo weather) |
| **workouts_plan** | `list_workouts`, `get_workout` | Read the training plan from `workouts_data.py` |
| **garmin_write** | `garmin_upload_workout`, `garmin_delete_workout`, `garmin_bulk_replace`, `garmin_list_uploaded` | Upload, schedule, and delete workouts on Garmin Connect |

### Metrics reference

| Metric | Source | What it tells you |
|---|---|---|
| TRIMP | Banister 1991 | Training impulse — single-number session load |
| ACWR | Hulin/Gabbett 2016, Williams 2017 | Acute:Chronic workload ratio (injury risk proxy) |
| CTL/ATL/TSB | Banister / TrainingPeaks PMC | Fitness (CTL), fatigue (ATL), form (TSB) |
| Polarization | Seiler 2010 | LIT/MIT/HIT time-in-zone distribution |
| Decoupling | Friel / TrainingPeaks | Aerobic decoupling Pa:HR (base fitness proxy) |
| HR drift | Maffetone / Friel | Cardiac drift on steady runs |

## Prerequisites

- **InfluxDB 1.x** with Garmin data (populated by
  [garmin-grafana](https://github.com/arpanghosh8453/garmin-grafana) or
  compatible fetcher)
- **Garmin Connect account** (for workout upload/delete operations)
- **Docker** (recommended) or Python 3.11+

## Quick start

### With Docker (recommended)

```bash
cp .env.example .env
# Edit .env: set InfluxDB credentials, athlete HR parameters

# Create the token directory for Garmin Connect auth
mkdir -p data/tokens

docker compose up -d
```

The server starts on port **8770** (host) → 8769 (container).

### Standalone

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env
uvicorn server:app --host 0.0.0.0 --port 8769
```

### Health check

```bash
curl http://localhost:8770/health
```

## Training plan (workouts)

The workout tools read from `workouts_data.py` — your personal training plan
encoded as Python dicts using the DSL from `workouts_helpers.py`.

```bash
# Start from the example
cp workouts_data.example.py workouts_data.py
# Edit with your own workouts
```

The MCP reloads `workouts_data.py` on every call (`importlib.reload`) — edit
the file and changes are picked up instantly without restarting the container.

See `workouts_helpers.py` for the full DSL reference (`s()`, `rep()`, `hrZ()`,
`pwr()`, `OPEN()`, etc.).

## Connecting to an MCP client

### Claude Code (`~/.claude.json`)

```json
{
  "mcpServers": {
    "garmin-toolbox": {
      "type": "http",
      "url": "http://YOUR_HOST:8770/mcp"
    }
  }
}
```

### Any MCP client

The server exposes streamable HTTP transport at `POST /mcp`.

## Files

| File | Role |
|---|---|
| `server.py` | FastMCP entrypoint + ASGI app |
| `tools/` | One module per tool group |
| `lib/influx_client.py` | Shared InfluxDB v1.x query client |
| `lib/garmin_login.py` | Garmin Connect token-cache login |
| `lib/garmin_workouts.py` | Workout → Garmin API payload conversion |
| `workouts_helpers.py` | Workout DSL (step constructors, targets, naming) |
| `workouts_data.example.py` | Example training plan (copy to `workouts_data.py`) |
| `workouts_data.py` | **Your** training plan (gitignored) |
| `activities/` | Per-activity JSON dumps (gitignored) |

## Docker networking

When running as part of Garvis Coach, this container joins the
`garmingrafana_default` network to reach InfluxDB at `influxdb:8086`. It also
mounts the Garmin Connect token cache shared with `garmin-fetch-data` so both
services use the same login session.

## License

MIT
