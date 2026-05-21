"""Garmin Connect write operations — upload, schedule, delete workouts.

Uses the shared token cache mounted from the NAS. Never prompts for
credentials. If the token is expired, returns a clear error pointing at how
to refresh.
"""
from __future__ import annotations

import importlib
import re
import time
from typing import Any

from mcp.server.fastmcp import FastMCP

import workouts_data as wd  # noqa: E402

from lib import garmin_login, garmin_workouts


def _err(msg: str) -> dict:
    return {"ok": False, "error": msg}


def _refresh_wd() -> None:
    global wd
    wd = importlib.reload(wd)


def _api():
    """Lazily build a logged-in Garmin client (token cache only)."""
    return garmin_login.login_cached()


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------

def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def garmin_list_uploaded(
        name_pattern: str | None = None,
        limit: int = 200,
    ) -> dict:
        """
        List workouts currently uploaded to the Garmin Connect account.

        Parameters
        ----------
        name_pattern : optional regex matched against workoutName
        limit        : max items returned (default 200, hard cap 1000)

        Returns
        -------
        {ok: true, n: int, workouts: [{workout_id, workout_name, sport,
                                       est_duration_sec}]}
        """
        try:
            api = _api()
            pat = re.compile(name_pattern) if name_pattern else None
            out = []
            start = 0
            while len(out) < min(limit, 1000):
                batch = api.get_workouts(start, 100)
                if not batch:
                    break
                for w in batch:
                    name = w.get("workoutName", "")
                    if pat and not pat.search(name):
                        continue
                    out.append({
                        "workout_id": w.get("workoutId"),
                        "workout_name": name,
                        "sport": (w.get("sportType") or {}).get("sportTypeKey"),
                        "est_duration_sec": w.get("estimatedDurationInSecs"),
                    })
                    if len(out) >= limit:
                        break
                if len(batch) < 100:
                    break
                start += 100
            return {"ok": True, "n": len(out), "workouts": out}
        except Exception as exc:
            return _err(str(exc))

    @mcp.tool()
    async def garmin_upload_workout(
        code: str,
        replace: bool = False,
    ) -> dict:
        """
        Upload a planned workout (by `code` from workouts_data.py) to Garmin
        Connect and schedule it on the workout's date.

        Parameters
        ----------
        code    : workout code matching one entry in workouts_data.WORKOUTS
        replace : if True, delete any existing workouts on the account with
                  the same `full_name` (date_YYYYMMDD + code) before uploading

        Returns
        -------
        {ok, workout_id, full_name, scheduled_date, deleted_old_ids}
        """
        try:
            _refresh_wd()
            match = next((w for w in wd.WORKOUTS if w["code"] == code), None)
            if not match:
                return _err(f"No workout with code={code!r}")
            full_name = wd.full_name(match)

            api = _api()
            deleted = []

            if replace:
                existing = garmin_workouts.fetch_existing_by_name(api)
                for old_id in existing.get(full_name, []):
                    try:
                        api.delete_workout(old_id)
                        deleted.append(old_id)
                        time.sleep(0.3)
                    except Exception as exc:
                        return _err(f"Delete old id={old_id} failed: {exc}")

            payload = garmin_workouts.workout_to_garmin_payload(match, full_name)
            result = api.upload_workout(payload)
            workout_id = result.get("workoutId")
            if not workout_id:
                return _err(f"No workoutId in upload response: {result}")

            api.schedule_workout(workout_id, match["date"])

            return {
                "ok": True,
                "workout_id": workout_id,
                "full_name": full_name,
                "scheduled_date": match["date"],
                "deleted_old_ids": deleted,
            }
        except Exception as exc:
            return _err(str(exc))

    @mcp.tool()
    async def garmin_delete_workout(
        workout_id: int | None = None,
        workout_name: str | None = None,
    ) -> dict:
        """
        Delete one or more workouts on Garmin Connect.

        Provide exactly one of:
          - workout_id   : delete by numeric ID
          - workout_name : delete ALL workouts with this exact name (regex NOT
                           supported here — use exact `full_name`)

        Returns
        -------
        {ok, deleted_ids: [int, ...]}
        """
        try:
            if workout_id is None and workout_name is None:
                return _err("Provide workout_id OR workout_name")
            api = _api()
            deleted = []

            if workout_id is not None:
                api.delete_workout(workout_id)
                deleted.append(workout_id)
            else:
                existing = garmin_workouts.fetch_existing_by_name(api)
                ids = existing.get(workout_name, [])
                if not ids:
                    return _err(f"No workout matches name={workout_name!r}")
                for wid in ids:
                    api.delete_workout(wid)
                    deleted.append(wid)
                    time.sleep(0.3)

            return {"ok": True, "deleted_ids": deleted}
        except Exception as exc:
            return _err(str(exc))

    @mcp.tool()
    async def garmin_bulk_replace(
        start_date: str,
        end_date: str,
        code_pattern: str | None = None,
    ) -> dict:
        """
        Bulk replace all planned workouts in a date window. For each matching
        workout in workouts_data.py: delete the existing instance on Garmin
        Connect (matched by full_name), then upload + schedule the current
        version.

        Parameters
        ----------
        start_date   : "YYYY-MM-DD" inclusive
        end_date     : "YYYY-MM-DD" inclusive
        code_pattern : optional regex on the workout code

        Returns
        -------
        {ok, n, results: [{code, status, workout_id?, error?}]}
        """
        try:
            _refresh_wd()
            pat = re.compile(code_pattern) if code_pattern else None
            targets = [
                w for w in wd.WORKOUTS
                if start_date <= w["date"] <= end_date
                and (pat is None or pat.search(w["code"]))
            ]
            if not targets:
                return _err(f"No workouts match [{start_date}, {end_date}] pattern={code_pattern}")

            api = _api()
            existing = garmin_workouts.fetch_existing_by_name(api)
            results = []

            for w in targets:
                full_name = wd.full_name(w)
                entry: dict[str, Any] = {"code": w["code"], "full_name": full_name}
                try:
                    for old_id in existing.get(full_name, []):
                        api.delete_workout(old_id)
                        time.sleep(0.3)
                    payload = garmin_workouts.workout_to_garmin_payload(w, full_name)
                    result = api.upload_workout(payload)
                    wid = result.get("workoutId")
                    if not wid:
                        entry["status"] = "failed"
                        entry["error"] = f"No workoutId in upload response: {result}"
                        results.append(entry)
                        continue
                    api.schedule_workout(wid, w["date"])
                    entry["status"] = "ok"
                    entry["workout_id"] = wid
                    entry["scheduled_date"] = w["date"]
                    results.append(entry)
                    time.sleep(0.5)
                except Exception as exc:
                    entry["status"] = "failed"
                    entry["error"] = str(exc)
                    results.append(entry)

            n_ok = sum(1 for r in results if r["status"] == "ok")
            return {"ok": True, "n_total": len(results), "n_ok": n_ok, "results": results}
        except Exception as exc:
            return _err(str(exc))
