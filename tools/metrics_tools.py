"""Training-load metrics — TRIMP, ACWR, CTL/ATL/TSB, polarization, decoupling, drift.

All readings from InfluxDB (read-only). Defaults to athlete env vars
(ATHLETE_HR_MAX / ATHLETE_HR_REST) when not provided explicitly.
"""
from __future__ import annotations

import math
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP

from lib import influx_client

DEFAULT_HR_MAX = float(os.getenv("ATHLETE_HR_MAX", 190))
DEFAULT_HR_REST = float(os.getenv("ATHLETE_HR_REST", 50))


# ---------------------------------------------------------------------------
# Helpers shared across metrics
# ---------------------------------------------------------------------------

def _err(msg: str) -> dict:
    return {"ok": False, "error": msg}


def _trimp_score(duration_min: float, hr_avg: float, hr_max: float, hr_rest: float) -> float:
    """Banister TRIMP (male). HRr clamped to [0, 1]."""
    if hr_max <= hr_rest:
        raise ValueError("hr_max must be > hr_rest")
    hrr = max(0.0, min(1.0, (hr_avg - hr_rest) / (hr_max - hr_rest)))
    return duration_min * hrr * 0.64 * math.exp(1.92 * hrr)


def _trimp_from_session(dur_s: float | None, hr_avg: float | None,
                        hr_max: float, hr_rest: float) -> float:
    """TRIMP from a session row, returns 0.0 if data missing."""
    if hr_max <= hr_rest or hr_avg is None or dur_s is None:
        return 0.0
    hrr = max(0.0, min(1.0, (hr_avg - hr_rest) / (hr_max - hr_rest)))
    return (dur_s / 60.0) * hrr * 0.64 * math.exp(1.92 * hrr)


def _daily_loads(days: int, hr_max: float, hr_rest: float) -> dict[str, float]:
    """Aggregate TRIMP by UTC day from ActivitySummary over the last N days."""
    since = (datetime.now(timezone.utc) - timedelta(days=days + 5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = influx_client.query(
        'SELECT "averageHR" AS hr, "movingDuration" AS dur '
        f"FROM \"ActivitySummary\" WHERE time > '{since}'"
    )
    by_day: dict[str, float] = {}
    for r in rows:
        ts = r.get("time")
        if not ts:
            continue
        d = ts.split("T")[0]
        by_day[d] = by_day.get(d, 0.0) + _trimp_from_session(
            r.get("dur") or 0, r.get("hr") or 0, hr_max, hr_rest
        )
    return by_day


def _ewma(loads: list[float], alpha: float) -> float:
    s = 0.0
    for x in loads:
        s = alpha * x + (1 - alpha) * s
    return s


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------

def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def compute_trimp(
        selector: str | None = None,
        duration_min: float | None = None,
        hr_avg: float | None = None,
        hr_max: float = DEFAULT_HR_MAX,
        hr_rest: float = DEFAULT_HR_REST,
    ) -> dict:
        """
        TRIMP (Banister 1991) — training impulse score.

        Two input modes:
          - from activity : pass `selector` (ActivitySelector tag from InfluxDB,
            e.g. "20260520T092419UTC-running"). Pulls averageHR + movingDuration
            from ActivitySummary.
          - manual        : pass `duration_min` and `hr_avg` directly.

        Formula : TRIMP = duration_min * HRr * 0.64 * exp(1.92 * HRr)
                  HRr   = (HR_avg - HR_rest) / (HR_max - HR_rest), clamped [0,1]

        Defaults to athlete env vars ATHLETE_HR_MAX / ATHLETE_HR_REST.
        Source : Banister 1991.
        """
        try:
            if selector:
                rows = influx_client.query(
                    'SELECT mean("averageHR") AS hr, mean("movingDuration") AS dur '
                    f"FROM \"ActivitySummary\" WHERE \"ActivitySelector\" = '{selector}'"
                )
                if not rows or rows[0].get("hr") is None or rows[0].get("dur") is None:
                    return _err(f"No ActivitySummary row for selector={selector}")
                hr_avg_v = float(rows[0]["hr"])
                dur_min = float(rows[0]["dur"]) / 60.0
                score = _trimp_score(dur_min, hr_avg_v, hr_max, hr_rest)
                return {
                    "ok": True,
                    "source": "activity",
                    "selector": selector,
                    "duration_min": round(dur_min, 1),
                    "hr_avg": round(hr_avg_v, 1),
                    "hr_max": hr_max,
                    "hr_rest": hr_rest,
                    "trimp": round(score, 1),
                }

            if duration_min is not None and hr_avg is not None:
                return {
                    "ok": True,
                    "source": "manual",
                    "duration_min": duration_min,
                    "hr_avg": hr_avg,
                    "hr_max": hr_max,
                    "hr_rest": hr_rest,
                    "trimp": round(_trimp_score(duration_min, hr_avg, hr_max, hr_rest), 1),
                }

            return _err("Provide either `selector` OR (`duration_min` AND `hr_avg`)")
        except Exception as exc:
            return _err(str(exc))

    @mcp.tool()
    async def compute_acwr(
        hr_max: float = DEFAULT_HR_MAX,
        hr_rest: float = DEFAULT_HR_REST,
    ) -> dict:
        """
        ACWR — Acute:Chronic Workload Ratio (Hulin/Gabbett 2016 + Williams 2017).

        Returns two variants:
          - rolling : acute = mean(load, 7d), chronic = mean(load, 28d)
          - ewma    : Williams 2017 exponentially-weighted

        Daily load = TRIMP from ActivitySummary. Days w/o activity = 0.
        Sweet spot (Gabbett) : 0.8 - 1.3. Reports flags but never treats
        thresholds as hard cutoffs (Impellizzeri 2020 critique).
        """
        try:
            by_day = _daily_loads(60, hr_max, hr_rest)
            today = date.today()
            last_28 = [by_day.get((today - timedelta(days=i)).isoformat(), 0.0)
                       for i in range(27, -1, -1)]
            acute = sum(last_28[-7:]) / 7.0
            chronic = sum(last_28) / 28.0
            rolling = acute / chronic if chronic > 0 else None

            ewma_acute = _ewma(last_28, 2.0 / (7 + 1))
            ewma_chronic = _ewma(last_28, 2.0 / (28 + 1))
            ewma_ratio = ewma_acute / ewma_chronic if ewma_chronic > 0 else None

            flags = []
            for label, r in (("rolling", rolling), ("ewma", ewma_ratio)):
                if r is None:
                    continue
                if r < 0.8:
                    flags.append(f"{label} ACWR={r:.2f} <0.8 → undertraining / detraining")
                elif r > 1.3:
                    flags.append(f"{label} ACWR={r:.2f} >1.3 → spike (Gabbett sweet spot exceeded)")

            return {
                "ok": True,
                "hr_max": hr_max,
                "hr_rest": hr_rest,
                "acute_7d_mean": round(acute, 1),
                "chronic_28d_mean": round(chronic, 1),
                "acwr_rolling": round(rolling, 3) if rolling else None,
                "acwr_ewma": round(ewma_ratio, 3) if ewma_ratio else None,
                "sweet_spot": "0.8 - 1.3 (Gabbett 2016)",
                "flags": flags,
                "caveat": "Impellizzeri 2020 critique — do not treat thresholds as hard cutoffs.",
            }
        except Exception as exc:
            return _err(str(exc))

    @mcp.tool()
    async def compute_ctl_atl_tsb(
        days: int = 90,
        hr_max: float = DEFAULT_HR_MAX,
        hr_rest: float = DEFAULT_HR_REST,
        brief: bool = False,
    ) -> dict:
        """
        CTL/ATL/TSB — Performance Manager (Banister/TrainingPeaks).

        CTL_today = CTL_yest + (load_today - CTL_yest) / 42   [42d EWMA chronic]
        ATL_today = ATL_yest + (load_today - ATL_yest) / 7    [7d EWMA acute]
        TSB       = CTL - ATL                                  [form]

        Parameters
        ----------
        days  : output window length (default 90). Internal warm-up is +60 days.
        brief : if True, omit the per-day series (just current + flags).

        Flags : TSB < -30 = overreaching risk, TSB > +25 = detraining if not taper.
        """
        try:
            loads = _daily_loads(days + 60, hr_max, hr_rest)
            today = date.today()
            start = today - timedelta(days=days + 60)
            ctl = atl = 0.0
            series = []
            for i in range((today - start).days + 1):
                d = (start + timedelta(days=i)).isoformat()
                load = loads.get(d, 0.0)
                ctl += (load - ctl) / 42.0
                atl += (load - atl) / 7.0
                if (today - date.fromisoformat(d)).days <= days:
                    series.append({
                        "date": d,
                        "load": round(load, 1),
                        "ctl": round(ctl, 1),
                        "atl": round(atl, 1),
                        "tsb": round(ctl - atl, 1),
                    })
            last = series[-1]
            flags = []
            if last["tsb"] < -30:
                flags.append("TSB<-30 → overreaching risk (Banister)")
            if last["tsb"] > 25:
                flags.append("TSB>+25 → detraining if not pre-race")
            result = {
                "ok": True,
                "hr_max": hr_max,
                "hr_rest": hr_rest,
                "current": last,
                "flags": flags,
            }
            if not brief:
                result["series"] = series
            return result
        except Exception as exc:
            return _err(str(exc))

    @mcp.tool()
    async def compute_polarization(
        days: int = 7,
        running_only: bool = True,
    ) -> dict:
        """
        Polarization — time-in-zone distribution (Seiler 2010).

        Aggregates hrTimeInZone_1..5 over a window and reports the 3-band split:
          LIT = Z1+Z2
          MIT = Z3
          HIT = Z4+Z5

        Reference (elite, polarized) : LIT ≥ 80%, MIT ≤ 5%, HIT 15-20%.
        Flags : LIT<75 (not polarized), MIT>10 (threshold trap), HIT>25 (overreaching).
        """
        try:
            since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
            where = f"time > '{since}'"
            if running_only:
                where += " AND \"ActivitySelector\" =~ /running/"
            fields = ", ".join(f'"hrTimeInZone_{i}"' for i in range(1, 6))
            rows = influx_client.query(
                f'SELECT {fields} FROM "ActivitySummary" WHERE {where}'
            )
            if not rows:
                return _err(f"No activities in last {days} days (running_only={running_only})")
            z = [0.0] * 6
            for r in rows:
                for i in range(1, 6):
                    v = r.get(f"hrTimeInZone_{i}")
                    if v:
                        z[i] += float(v)
            total = sum(z[1:6])
            if total <= 0:
                return _err("All hrTimeInZone fields are zero — check field names / data")
            pct = {f"z{i}": round(100 * z[i] / total, 1) for i in range(1, 6)}
            lit = pct["z1"] + pct["z2"]
            mit = pct["z3"]
            hit = pct["z4"] + pct["z5"]
            flags = []
            if lit < 75:
                flags.append(f"LIT={lit}% <75% → not polarized (Seiler target ≥80%)")
            if mit > 10:
                flags.append(f"MIT={mit}% >10% → threshold trap")
            if hit > 25:
                flags.append(f"HIT={hit}% >25% → likely overreaching")
            return {
                "ok": True,
                "window_days": days,
                "running_only": running_only,
                "n_activities": len(rows),
                "total_minutes": round(total / 60.0, 1),
                "per_zone_pct": pct,
                "lit_pct": round(lit, 1),
                "mit_pct": round(mit, 1),
                "hit_pct": round(hit, 1),
                "seiler_target": "LIT≥80, MIT≤5, HIT 15-20",
                "flags": flags,
            }
        except Exception as exc:
            return _err(str(exc))

    @mcp.tool()
    async def compute_decoupling(
        selector: str,
        warmup_min: float = 10.0,
    ) -> dict:
        """
        Aerobic decoupling Pa:HR (Friel / TrainingPeaks).

        Splits the activity in two equal halves by time (after warmup), computes
        EF = mean(GAP_speed_mps * 60) / mean(HR) for each half.
        decoupling_% = (EF_first - EF_second) / EF_first * 100

        Verdict (Friel):
          <5%  → aerobic base sound
          5-7% → marginal, watch trend
          >7%  → poor aerobic base or excessive intensity
        """
        try:
            rows = influx_client.query(
                'SELECT "HeartRate", "Speed", "GradeAdjustedSpeed", "Distance" '
                f"FROM \"ActivityGPS\" WHERE \"ActivitySelector\" = '{selector}'"
            )
            if not rows:
                return _err(f"No ActivityGPS rows for selector={selector}")
            if len(rows) < 2 * int(warmup_min * 60):
                return _err(f"Activity too short (need >{warmup_min*2}min, got {len(rows)/60:.1f}min)")

            skip = int(warmup_min * 60)
            body = rows[skip:]
            half = len(body) // 2
            h1, h2 = body[:half], body[half:]

            def _ef(samples: list[dict]) -> tuple[float, float, float, int]:
                speeds, hrs = [], []
                for r in samples:
                    s = r.get("GradeAdjustedSpeed") or r.get("Speed")
                    h = r.get("HeartRate")
                    if s is None or h is None or h <= 0 or s <= 0:
                        continue
                    speeds.append(float(s))
                    hrs.append(float(h))
                if not speeds:
                    return 0.0, 0.0, 0.0, 0
                mean_s = sum(speeds) / len(speeds)
                mean_h = sum(hrs) / len(hrs)
                return (mean_s * 60.0) / mean_h, mean_s, mean_h, len(speeds)

            ef1, s1, hr1, n1 = _ef(h1)
            ef2, s2, hr2, n2 = _ef(h2)
            if ef1 == 0 or ef2 == 0:
                return _err("EF computation failed (missing speed/HR)")

            decoupling = (ef1 - ef2) / ef1 * 100.0
            if decoupling < 5:
                verdict = "aerobic base sound (<5%)"
            elif decoupling < 7:
                verdict = "marginal — watch trend (5-7%)"
            else:
                verdict = "poor aerobic base or too much intensity (>7%)"

            return {
                "ok": True,
                "selector": selector,
                "warmup_skipped_min": warmup_min,
                "n_samples": len(body),
                "half_1": {"ef": round(ef1, 4), "mean_speed_mps": round(s1, 3),
                           "mean_hr": round(hr1, 1), "n": n1},
                "half_2": {"ef": round(ef2, 4), "mean_speed_mps": round(s2, 3),
                           "mean_hr": round(hr2, 1), "n": n2},
                "decoupling_pct": round(decoupling, 2),
                "verdict": verdict,
                "source": "Friel/TrainingPeaks Pa:HR",
            }
        except Exception as exc:
            return _err(str(exc))

    @mcp.tool()
    async def compute_hr_drift(
        selector: str,
        warmup_min: float = 10.0,
        min_total_min: float = 45.0,
    ) -> dict:
        """
        HR drift — cardiac drift on a steady aerobic run (Maffetone/Friel).

        Drops the warmup, then compares mean HR of first 1/3 vs last 1/3 of the
        remaining body. If pace is steady, drift > 5% signals fatigue /
        dehydration / heat / aerobic base limit.

        Caveats : only meaningful on activities >45 min with relatively flat
        pace. If pace varies a lot, prefer compute_decoupling.
        """
        try:
            rows = influx_client.query(
                'SELECT "HeartRate", "Speed", "GradeAdjustedSpeed" '
                f"FROM \"ActivityGPS\" WHERE \"ActivitySelector\" = '{selector}'"
            )
            if not rows:
                return _err(f"No ActivityGPS rows for selector={selector}")
            total_min = len(rows) / 60.0
            if total_min < min_total_min:
                return _err(f"Activity too short ({total_min:.1f}min < {min_total_min}min) — drift not meaningful")

            skip = int(warmup_min * 60)
            body = [r for r in rows[skip:] if r.get("HeartRate") and r["HeartRate"] > 0]
            if len(body) < 600:
                return _err("Less than 10min of valid HR samples after warmup")

            third = len(body) // 3
            first = body[:third]
            last = body[-third:]

            def m(samples: list[dict], key: str) -> float:
                vals = [float(r[key]) for r in samples
                        if r.get(key) is not None and r[key] > 0]
                return sum(vals) / len(vals) if vals else 0.0

            hr1, hr2 = m(first, "HeartRate"), m(last, "HeartRate")
            sp1 = m(first, "GradeAdjustedSpeed") or m(first, "Speed")
            sp2 = m(last, "GradeAdjustedSpeed") or m(last, "Speed")
            drift = (hr2 - hr1) / hr1 * 100.0 if hr1 else 0.0
            pace_change_pct = (sp1 - sp2) / sp1 * 100.0 if sp1 else 0.0

            flags = []
            if drift > 5:
                flags.append(f"HR drift {drift:.1f}% > 5% → fatigue / dehydration / heat / aerobic base limit")
            if abs(pace_change_pct) > 5:
                flags.append(f"Pace varied {pace_change_pct:+.1f}% — drift interpretation weakened, prefer compute_decoupling")

            return {
                "ok": True,
                "selector": selector,
                "total_min": round(total_min, 1),
                "warmup_skipped_min": warmup_min,
                "first_third_hr": round(hr1, 1),
                "last_third_hr": round(hr2, 1),
                "first_third_speed_mps": round(sp1, 3),
                "last_third_speed_mps": round(sp2, 3),
                "drift_pct": round(drift, 2),
                "pace_change_pct": round(pace_change_pct, 2),
                "flags": flags,
                "source": "Maffetone/Friel HR drift test",
            }
        except Exception as exc:
            return _err(str(exc))
