"""Read access to the training plan defined in workouts_data.py."""
from __future__ import annotations

import importlib
import re
from typing import Any

from mcp.server.fastmcp import FastMCP

import workouts_data as wd  # noqa: E402


def _err(msg: str) -> dict:
    return {"ok": False, "error": msg}


def _refresh_module() -> None:
    """Re-import workouts_data so edits via SMB land without container restart."""
    global wd
    wd = importlib.reload(wd)


def _summarize_step(step: dict[str, Any]) -> dict[str, Any]:
    """Flatten one step/repeat for compact display."""
    if step.get("kind") == "step":
        return {
            "kind": "step",
            "name": step.get("name"),
            "type": step.get("type"),
            "duration_min": step.get("duration_min"),
            "duration_open": step.get("duration_open", False),
            "target": step.get("target"),
            "notes": step.get("notes"),
        }
    if step.get("kind") == "repeat":
        return {
            "kind": "repeat",
            "iterations": step.get("iterations"),
            "steps": [_summarize_step(s) for s in step.get("steps", [])],
        }
    return {"kind": "unknown", "raw": step}


def _total_minutes(steps: list[dict[str, Any]]) -> float:
    total = 0.0
    for s in steps:
        if s.get("kind") == "step":
            d = s.get("duration_min") or 0
            if not s.get("duration_open"):
                total += d
        elif s.get("kind") == "repeat":
            iters = s.get("iterations", 1)
            total += iters * _total_minutes(s.get("steps", []))
    return total


def _workout_summary(w: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": w["date"],
        "code": w["code"],
        "full_name": wd.full_name(w),
        "description": w.get("description", ""),
        "total_min": round(_total_minutes(w["steps"]), 1),
        "n_steps": len(w["steps"]),
    }


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------

def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_workouts(
        start_date: str | None = None,
        end_date: str | None = None,
        code_pattern: str | None = None,
    ) -> dict:
        """
        List planned workouts with optional filters.

        Parameters
        ----------
        start_date   : "YYYY-MM-DD" inclusive lower bound (optional)
        end_date     : "YYYY-MM-DD" inclusive upper bound (optional)
        code_pattern : regex matched against the workout code (e.g. "C1-S3", "Trail-LR")

        Returns
        -------
        {ok: true, n: int, workouts: [{date, code, full_name, description,
                                       total_min, n_steps}]}
        """
        try:
            _refresh_module()
            out = []
            pat = re.compile(code_pattern) if code_pattern else None
            for w in wd.WORKOUTS:
                if start_date and w["date"] < start_date:
                    continue
                if end_date and w["date"] > end_date:
                    continue
                if pat and not pat.search(w["code"]):
                    continue
                out.append(_workout_summary(w))
            return {"ok": True, "n": len(out), "workouts": out}
        except Exception as exc:
            return _err(str(exc))

    @mcp.tool()
    async def get_workout(code: str) -> dict:
        """
        Return the full definition of one workout (by `code`).

        Returns the date, code, description, full_name (date+code as stored on
        Garmin Connect), and the complete step tree (warmup / active /
        intervals / repeats with targets and notes).

        Returns {ok: false, error: "..."} if no workout matches.
        """
        try:
            _refresh_module()
            for w in wd.WORKOUTS:
                if w["code"] == code:
                    return {
                        "ok": True,
                        "workout": {
                            "date": w["date"],
                            "code": w["code"],
                            "full_name": wd.full_name(w),
                            "short_name": wd.short_name(w),
                            "description": w.get("description", ""),
                            "total_min": round(_total_minutes(w["steps"]), 1),
                            "steps": [_summarize_step(s) for s in w["steps"]],
                        },
                    }
            return _err(f"No workout with code={code!r}")
        except Exception as exc:
            return _err(str(exc))
