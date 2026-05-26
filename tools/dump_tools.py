"""Per-activity dump tool — mirrors dashboard 03 activity drill-down panel queries.

Writes a JSON to the activities output directory and returns a compact summary
plus the file path. Never returns the full ~5MB JSON inline.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from mcp.server.fastmcp import FastMCP

from lib import influx_client

OUT_DIR = Path(os.environ.get("ACTIVITY_DUMP_PATH", "/app/activities"))
SMB_BASE = os.environ.get("ACTIVITY_DUMP_SMB", "")
PARIS = ZoneInfo("Europe/Paris")


# ---------------------------------------------------------------------------
# Selector resolution + parsing
# ---------------------------------------------------------------------------

def _err(msg: str) -> dict:
    return {"ok": False, "error": msg}


def _resolve_selector(
    activity_id: str | None,
    activity_selector: str | None,
    date_str: str | None,
    last: bool,
    sport: str,
) -> str:
    if activity_selector:
        return activity_selector
    if activity_id:
        rows = influx_client.query(
            'SHOW TAG VALUES FROM "ActivityGPS" WITH KEY = "ActivitySelector" '
            f"WHERE \"ActivityID\" = '{activity_id}'"
        )
        if not rows:
            raise ValueError(f"No ActivitySelector found for ActivityID {activity_id}")
        return rows[0]["value"]
    if date_str:
        date_compact = date_str.replace("-", "")
        rows = influx_client.query(
            'SHOW TAG VALUES FROM "ActivityGPS" WITH KEY = "ActivitySelector" '
            f"WHERE \"ActivitySelector\" =~ /^{date_compact}.*-{sport}$/"
        )
        if not rows:
            raise ValueError(f"No activity on {date_str} for sport={sport}")
        return sorted(r["value"] for r in rows)[-1]
    if last:
        rows = influx_client.query(
            'SHOW TAG VALUES FROM "ActivityGPS" WITH KEY = "ActivitySelector" '
            f"WHERE \"ActivitySelector\" =~ /-{sport}$/"
        )
        if not rows:
            raise ValueError(f"No {sport} activity found")
        return sorted(r["value"] for r in rows)[-1]
    raise ValueError("Provide one of: activity_id, activity_selector, date, last=true")


def _parse_selector_meta(selector: str) -> dict[str, Any]:
    m = re.match(r"^(\d{8})T(\d{6})UTC-(.+)$", selector)
    if not m:
        raise ValueError(f"Bad ActivitySelector format: {selector}")
    date_s, time_s, sport = m.groups()
    dt_utc = datetime.strptime(date_s + time_s, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    return {
        "activity_selector": selector,
        "sport": sport,
        "start_time_utc": dt_utc.isoformat().replace("+00:00", "Z"),
        "start_time_local_paris": dt_utc.astimezone(PARIS).isoformat(),
        "date_local": dt_utc.astimezone(PARIS).date().isoformat(),
    }


def _fetch_table(selector: str, measurement: str) -> list[dict[str, Any]]:
    return influx_client.query(
        f'SELECT * FROM "{measurement}" '
        f"WHERE \"ActivitySelector\" = '{selector}' ORDER BY time ASC"
    )


_ACTIVITY_SUMMARY_FIELDS = [
    "Activity_ID", "Device_ID", "activityName", "activityTrainingLoad",
    "activityType", "aerobicTrainingEffect", "anaerobicTrainingEffect",
    "averageHR", "averageSpeed", "bmrCalories", "calories", "description",
    "distance", "elapsedDuration", "elevationGain", "elevationLoss",
    "hrTimeInZone_1", "hrTimeInZone_2", "hrTimeInZone_3", "hrTimeInZone_4", "hrTimeInZone_5",
    "hrZoneLowBoundary_1", "hrZoneLowBoundary_2", "hrZoneLowBoundary_3", "hrZoneLowBoundary_4", "hrZoneLowBoundary_5",
    "lapCount", "locationName", "maxHR", "maxSpeed",
    "moderateIntensityMinutes", "movingDuration",
    "trainingEffectLabel", "vO2MaxValue", "vigorousIntensityMinutes",
]


def _fetch_summary(selector: str) -> dict[str, Any]:
    selects = ", ".join(f'last("{f}") AS "{f}"' for f in _ACTIVITY_SUMMARY_FIELDS)
    rows = influx_client.query(
        f'SELECT {selects} FROM "ActivitySummary" '
        f"WHERE \"ActivitySelector\" = '{selector}' "
        f"AND \"activityName\" != 'END'"
    )
    if not rows:
        raise ValueError(f"No ActivitySummary for {selector}")
    row = rows[0]
    row.pop("time", None)
    if row.get("averageSpeed"):
        row["avg_pace_sec_per_km"] = round(1000.0 / row["averageSpeed"], 1)
    if row.get("distance"):
        row["distance_km"] = round(row["distance"] / 1000.0, 3)
    total_z = sum((row.get(f"hrTimeInZone_{i}") or 0) for i in range(1, 6))
    if total_z:
        row["hr_zones_pct"] = {
            f"z{i}": round(100.0 * (row.get(f"hrTimeInZone_{i}") or 0) / total_z, 1)
            for i in range(1, 6)
        }
    return row


def _collapse_workout_target(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    keys = ("StepIndex", "TargetLowBPM", "TargetHighBPM", "TargetLowW", "TargetHighW",
            "TargetLowRPM", "TargetHighRPM", "StepAvgHR", "StepAvgPower",
            "StepAvgSpeed", "StepAvgCadence", "StepAvgStride", "StepAvgVR")
    out: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for r in rows:
        sig = tuple(r.get(k) for k in keys)
        if cur is None or cur["_sig"] != sig:
            if cur is not None:
                cur.pop("_sig", None)
                out.append(cur)
            cur = {
                "_sig": sig,
                "step_index": r.get("StepIndex"),
                "row_marker_start": r.get("RowMarker"),
                "row_marker_end": r.get("RowMarker"),
                "target_low_bpm": r.get("TargetLowBPM"),
                "target_high_bpm": r.get("TargetHighBPM"),
                "target_low_w": r.get("TargetLowW"),
                "target_high_w": r.get("TargetHighW"),
                "target_low_rpm": r.get("TargetLowRPM"),
                "target_high_rpm": r.get("TargetHighRPM"),
                "step_avg_hr": r.get("StepAvgHR"),
                "step_avg_power": r.get("StepAvgPower"),
                "step_avg_speed": r.get("StepAvgSpeed"),
                "step_avg_cadence": r.get("StepAvgCadence"),
                "step_avg_stride": r.get("StepAvgStride"),
                "step_avg_vr": r.get("StepAvgVR"),
                "step_avg_altitude": r.get("StepAvgAltitude"),
                "duration_seconds": r.get("DurationSeconds"),
                "rows": 1,
            }
        else:
            cur["row_marker_end"] = r.get("RowMarker")
            cur["duration_seconds"] = r.get("DurationSeconds")
            cur["rows"] += 1
    if cur is not None:
        cur.pop("_sig", None)
        out.append(cur)
    return out


def _fetch_weather(lat: float, lon: float, start_local: datetime, end_local: datetime) -> dict[str, Any]:
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "start_date": start_local.date().isoformat(),
        "end_date": end_local.date().isoformat(),
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,wind_gusts_10m,surface_pressure,cloud_cover,dew_point_2m,apparent_temperature",
        "timezone": "Europe/Paris",
        "wind_speed_unit": "kmh",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    j = r.json()
    times = j["hourly"]["time"]
    samples = []
    for i, t in enumerate(times):
        samples.append({
            "time_local": t,
            "temperature_c": j["hourly"]["temperature_2m"][i],
            "apparent_temperature_c": j["hourly"]["apparent_temperature"][i],
            "humidity_pct": j["hourly"]["relative_humidity_2m"][i],
            "dew_point_c": j["hourly"]["dew_point_2m"][i],
            "precipitation_mm": j["hourly"]["precipitation"][i],
            "wind_kmh": j["hourly"]["wind_speed_10m"][i],
            "wind_gust_kmh": j["hourly"]["wind_gusts_10m"][i],
            "wind_direction_deg": j["hourly"]["wind_direction_10m"][i],
            "pressure_hpa": j["hourly"]["surface_pressure"][i],
            "cloud_cover_pct": j["hourly"]["cloud_cover"][i],
        })
    s_dt = start_local.replace(minute=0, second=0, microsecond=0)
    e_dt = end_local.replace(minute=0, second=0, microsecond=0)
    activity = [s for s in samples
                if s_dt.isoformat(timespec="minutes") <= s["time_local"] <= e_dt.isoformat(timespec="minutes")]
    if not activity:
        activity = samples

    def _avg(key: str) -> float | None:
        vals = [s[key] for s in activity if s[key] is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    summary = {
        "temp_avg_c": _avg("temperature_c"),
        "apparent_temp_avg_c": _avg("apparent_temperature_c"),
        "temp_min_c": min((s["temperature_c"] for s in activity if s["temperature_c"] is not None), default=None),
        "temp_max_c": max((s["temperature_c"] for s in activity if s["temperature_c"] is not None), default=None),
        "humidity_avg_pct": _avg("humidity_pct"),
        "wind_avg_kmh": _avg("wind_kmh"),
        "wind_gust_max_kmh": max((s["wind_gust_kmh"] for s in activity if s["wind_gust_kmh"] is not None), default=None),
        "wind_direction_avg_deg": _avg("wind_direction_deg"),
        "precipitation_total_mm": round(sum(s["precipitation_mm"] for s in activity if s["precipitation_mm"] is not None), 2) if activity else None,
        "pressure_avg_hpa": _avg("pressure_hpa"),
        "cloud_cover_avg_pct": _avg("cloud_cover_pct"),
    }
    return {
        "source": "Open-Meteo Historical (archive-api)",
        "lat": params["latitude"],
        "lon": params["longitude"],
        "timezone": "Europe/Paris",
        "samples_around_activity": samples,
        "summary_during_activity": summary,
    }


def _parse_session_code(activity_name: str | None) -> str | None:
    if not activity_name:
        return None
    m = re.search(r"\d{8}_(.+)$", activity_name)
    return m.group(1) if m else None


def _compact_summary(summary: dict[str, Any], weather: dict | None,
                     n_laps: int, n_gps: int, n_steps: int) -> dict[str, Any]:
    """Return a small JSON safe for inline MCP response (no per-second arrays)."""
    keep = {
        "activity_id": summary.get("Activity_ID"),
        "activity_name": summary.get("activityName"),
        "location_name": summary.get("locationName"),
        "training_effect_label": summary.get("trainingEffectLabel"),
        "distance_km": summary.get("distance_km"),
        "duration_min": round((summary.get("movingDuration") or 0) / 60.0, 2),
        "elapsed_duration_min": round((summary.get("elapsedDuration") or 0) / 60.0, 2),
        "elevation_gain_m": summary.get("elevationGain"),
        "elevation_loss_m": summary.get("elevationLoss"),
        "avg_hr": summary.get("averageHR"),
        "max_hr": summary.get("maxHR"),
        "avg_pace_sec_per_km": summary.get("avg_pace_sec_per_km"),
        "calories": summary.get("calories"),
        "aerobic_te": summary.get("aerobicTrainingEffect"),
        "anaerobic_te": summary.get("anaerobicTrainingEffect"),
        "training_load": summary.get("activityTrainingLoad"),
        "vo2max": summary.get("vO2MaxValue"),
        "hr_zones_pct": summary.get("hr_zones_pct"),
        "n_laps": n_laps,
        "n_workout_steps": n_steps,
        "n_gps_points": n_gps,
    }
    if weather:
        keep["weather_summary"] = weather.get("summary_during_activity")
    return keep


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------

def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def dump_activity(
        activity_id: str | None = None,
        activity_selector: str | None = None,
        date: str | None = None,
        last: bool = False,
        sport: str = "running",
        force: bool = False,
        no_weather: bool = False,
    ) -> dict:
        """
        Dump per-activity data (summary + laps + workout steps + targets +
        per-second GPS telemetry + Open-Meteo weather) to a JSON file in the
        garmin-toolbox activities/ volume.

        Returns a compact summary inline (NOT the full ~5MB JSON) plus the SMB
        path so the file can be read separately if the full detail is needed.

        Selector resolution (provide exactly one):
          - activity_id        : Garmin numeric activity ID
          - activity_selector  : ActivitySelector tag (e.g. "20260520T092419UTC-running")
          - date               : "YYYY-MM-DD" (UTC date of activity)
          - last=True          : most recent activity for `sport`

        Parameters
        ----------
        sport       : sport filter (default "running")
        force       : overwrite existing dump
        no_weather  : skip the Open-Meteo fetch (faster)

        Returns
        -------
        dict with:
          - ok            : bool
          - path_smb      : Windows SMB path to the full JSON
          - path_container: path inside the container (debug)
          - size_mb       : file size
          - summary       : compact KPIs (distance, duration, HR, TE, zones,
                            weather, counts of laps/gps/steps)
        """
        try:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            selector = _resolve_selector(
                activity_id, activity_selector, date, last, sport
            )
            meta = _parse_selector_meta(selector)
            summary = _fetch_summary(selector)
            activity_id_v = summary.get("Activity_ID")
            activity_name = summary.get("activityName")
            session_code = _parse_session_code(activity_name)

            out_filename = meta["date_local"]
            if session_code:
                out_filename += f"_{session_code}"
            elif activity_id_v:
                out_filename += f"_id{activity_id_v}"
            out_filename += ".json"
            out_path = OUT_DIR / out_filename

            if out_path.exists() and not force:
                # Just return existing file info
                size_mb = out_path.stat().st_size / (1024 * 1024)
                with out_path.open("r", encoding="utf-8") as f:
                    existing = json.load(f)
                return {
                    "ok": True,
                    "from_cache": True,
                    "path_smb": f"{SMB_BASE}\\{out_filename}",
                    "path_container": str(out_path),
                    "size_mb": round(size_mb, 2),
                    "summary": _compact_summary(
                        existing.get("summary", {}),
                        existing.get("weather"),
                        len(existing.get("laps", [])),
                        len(existing.get("gps", [])),
                        len(existing.get("workout_steps", [])),
                    ),
                    "note": "Existing dump returned. Pass force=true to refresh.",
                }

            laps = _fetch_table(selector, "ActivityLap")
            workout_steps = _fetch_table(selector, "WorkoutStep")
            workout_target = _fetch_table(selector, "WorkoutTarget")
            workout_target_collapsed = _collapse_workout_target(workout_target)
            gps = _fetch_table(selector, "ActivityGPS")

            weather = None
            if not no_weather and gps:
                first = next((pt for pt in gps if pt.get("Latitude") and pt.get("Longitude")), None)
                if first:
                    start_utc = datetime.fromisoformat(meta["start_time_utc"].replace("Z", "+00:00"))
                    duration_s = summary.get("elapsedDuration") or summary.get("movingDuration") or 3600
                    end_utc = datetime.fromtimestamp(start_utc.timestamp() + duration_s, tz=timezone.utc)
                    try:
                        weather = _fetch_weather(
                            first["Latitude"], first["Longitude"],
                            start_utc.astimezone(PARIS), end_utc.astimezone(PARIS),
                        )
                    except Exception as exc:
                        weather = {"error": f"Open-Meteo fetch failed: {exc}"}

            payload = {
                "metadata": {
                    **meta,
                    "activity_id": activity_id_v,
                    "activity_name": activity_name,
                    "session_code": session_code,
                    "fetched_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "schema_version": 1,
                },
                "summary": summary,
                "laps": laps,
                "workout_steps": workout_steps,
                "workout_target_collapsed": workout_target_collapsed,
                "workout_target": workout_target,
                "gps": gps,
                "weather": weather,
            }

            text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
            out_path.write_text(text, encoding="utf-8")
            size_mb = out_path.stat().st_size / (1024 * 1024)

            return {
                "ok": True,
                "from_cache": False,
                "path_smb": f"{SMB_BASE}\\{out_filename}",
                "path_container": str(out_path),
                "size_mb": round(size_mb, 2),
                "summary": _compact_summary(summary, weather, len(laps), len(gps), len(workout_steps)),
            }
        except Exception as exc:
            return _err(str(exc))
