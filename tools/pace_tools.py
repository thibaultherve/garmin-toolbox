"""Pace / speed / distance / time conversions + multi-segment session predictor.

Pure math, no I/O. Exists to ban mental arithmetic on sport conversions
(cf. COACHING_RULES.md §0 "Zero arithmetique mentale" — post-incident 2026-05-17).
"""
from __future__ import annotations

import re
from typing import Any

from mcp.server.fastmcp import FastMCP


# ---------------------------------------------------------------------------
# Core math
# ---------------------------------------------------------------------------

def _parse_pace(p: Any) -> float:
    """Parse 'mm:ss', 'mm:ss/km', or numeric min/km -> float min/km."""
    if isinstance(p, (int, float)):
        return float(p)
    s = str(p).strip().lower().replace("/km", "")
    if ":" in s:
        m, sec = s.split(":")
        return int(m) + int(sec) / 60.0
    return float(s)


def _fmt_pace(min_per_km: float) -> str:
    m = int(min_per_km)
    sec = int(round((min_per_km - m) * 60))
    if sec == 60:
        m += 1
        sec = 0
    return f"{m}:{sec:02d}/km"


def pace_to_kmh(pace: Any) -> float:
    p = _parse_pace(pace)
    if p <= 0:
        raise ValueError(f"pace must be > 0, got {pace}")
    return 60.0 / p


def kmh_to_pace(kmh: float) -> str:
    if kmh <= 0:
        raise ValueError(f"kmh must be > 0, got {kmh}")
    return _fmt_pace(60.0 / kmh)


def dist_from_pace_time(pace: Any, minutes: float) -> float:
    p = _parse_pace(pace)
    return minutes / p


def pace_from_dist_time(km: float, minutes: float) -> str:
    if km <= 0:
        raise ValueError(f"km must be > 0, got {km}")
    return _fmt_pace(minutes / km)


def predict_session(segments: list[dict]) -> dict:
    """Predict session distance from multi-step plan.

    segments: [{"name": str, "minutes": float, "pace": "mm:ss"}]
    """
    out: dict[str, Any] = {"segments": [], "total_min": 0.0, "total_km": 0.0}
    for seg in segments:
        name = seg["name"]
        mins = float(seg["minutes"])
        pace_str = seg["pace"]
        km = dist_from_pace_time(pace_str, mins)
        out["segments"].append({
            "name": name,
            "minutes": mins,
            "pace": pace_str,
            "km": round(km, 3),
        })
        out["total_min"] += mins
        out["total_km"] += km
    out["total_km"] = round(out["total_km"], 3)
    out["total_min"] = round(out["total_min"], 2)
    out["avg_pace"] = pace_from_dist_time(out["total_km"], out["total_min"])
    return out


_SEG_RE = re.compile(r"^([^=]+)=([\d.]+)min@(.+)$")


def parse_seg_string(s: str) -> dict:
    """Parse 'name=Nmin@mm:ss' into {name, minutes, pace}."""
    m = _SEG_RE.match(s)
    if not m:
        raise ValueError(f"Bad segment format: {s!r}. Expected name=Nmin@mm:ss")
    return {"name": m.group(1), "minutes": float(m.group(2)), "pace": m.group(3)}


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------

def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def compute_pace(
        op: str,
        pace: str | None = None,
        kmh: float | None = None,
        minutes: float | None = None,
        km: float | None = None,
        segments: list[dict] | None = None,
    ) -> dict:
        """
        Sport-arithmetic helper. Banned: mental math on pace/speed/distance.

        Parameters
        ----------
        op : str
            One of: "kmh", "pace", "dist", "pace_from", "predict".
              - kmh         : pace -> km/h          (needs: pace)
              - pace        : km/h -> pace mm:ss/km (needs: kmh)
              - dist        : pace + minutes -> km  (needs: pace, minutes)
              - pace_from   : km + minutes -> pace  (needs: km, minutes)
              - predict     : multi-segment session (needs: segments=[{name, minutes, pace}, ...])
        pace : str
            Pace as "mm:ss" or "mm:ss/km" or float min/km.
        kmh : float
            Speed in km/h.
        minutes : float
            Duration in minutes.
        km : float
            Distance in kilometers.
        segments : list[dict]
            For "predict": list of {"name": str, "minutes": float, "pace": "mm:ss"}.

        Returns
        -------
        dict
            Shape depends on op. Always has "ok": true on success.
            - kmh       -> {"ok": true, "kmh": 10.345}
            - pace      -> {"ok": true, "pace": "5:48/km"}
            - dist      -> {"ok": true, "km": 13.05}
            - pace_from -> {"ok": true, "pace": "6:41/km"}
            - predict   -> {"ok": true, "segments": [...], "total_min", "total_km", "avg_pace"}
        """
        try:
            if op == "kmh":
                if pace is None:
                    raise ValueError("op=kmh requires 'pace'")
                return {"ok": True, "kmh": round(pace_to_kmh(pace), 3)}

            if op == "pace":
                if kmh is None:
                    raise ValueError("op=pace requires 'kmh'")
                return {"ok": True, "pace": kmh_to_pace(kmh)}

            if op == "dist":
                if pace is None or minutes is None:
                    raise ValueError("op=dist requires 'pace' and 'minutes'")
                return {"ok": True, "km": round(dist_from_pace_time(pace, minutes), 3)}

            if op == "pace_from":
                if km is None or minutes is None:
                    raise ValueError("op=pace_from requires 'km' and 'minutes'")
                return {"ok": True, "pace": pace_from_dist_time(km, minutes)}

            if op == "predict":
                if not segments:
                    raise ValueError("op=predict requires 'segments'")
                result = predict_session(segments)
                result["ok"] = True
                return result

            raise ValueError(f"Unknown op={op!r}. Valid: kmh, pace, dist, pace_from, predict")

        except (ValueError, KeyError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}
