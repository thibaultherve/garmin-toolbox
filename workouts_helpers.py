"""Workout DSL helpers for garmin-toolbox.

Provides reusable building blocks for defining training workouts in Python.
Workouts are encoded as plain dicts and compiled to .fit / Garmin Connect
payloads by garmin_write_tools.

Usage in your workouts_data.py::

    from workouts_helpers import *

    WORKOUTS = []

    WORKOUTS.append({
        "date": "2026-01-15",
        "code": "C1-S1-Tue-Z2-50min",
        "description": "Easy Z2 run 50min.",
        "steps": [
            s("Warmup", 10, type="warmup", target=hrZ(2)),
            s("Z2 steady", 35, type="active", target=hrZ(2)),
            s("Cooldown", 5, type="cooldown", target=hrZ(2)),
        ],
    })

Step targets
------------
- ``hrZ(n)``          : heart rate zone 1-5 (as configured in Garmin Connect)
- ``hrR(low, high)``  : custom heart rate range in bpm
- ``pwr(low, high)``  : custom power range in watts
- ``OPEN()``          : no target (all-out / feel-based)
- ``NONE()``          : no target (placeholder / rest)

Step types
----------
``warmup``, ``cooldown``, ``interval``, ``recovery``, ``rest``, ``active``

Repeats
-------
Use ``rep(iterations, step1, step2, ...)`` for interval blocks.

Duration
--------
``duration_min`` is in minutes (float). Set ``duration_open=True`` for
lap-button-ended steps (the watch waits for a manual lap press).

Naming
------
``full_name(workout)``  → ``"YYYYMMDD_<code>"`` (Garmin workout name)
``short_name(workout)`` → short label for the watch face (max 15 chars)
"""


# ---------------------------------------------------------------------------
# Step constructors
# ---------------------------------------------------------------------------

def s(name, dur, **kw):
    """Create a workout step.

    Parameters
    ----------
    name : str — display name (e.g. "Warmup", "Z2 steady", "Hill 60s")
    dur  : float — duration in minutes
    **kw : type (str), target (dict), notes (str), duration_open (bool)
    """
    d = {"kind": "step", "name": name, "duration_min": dur}
    d.update(kw)
    return d


def rep(iters, *steps):
    """Create a repeat block (interval set)."""
    return {"kind": "repeat", "iterations": iters, "steps": list(steps)}


# ---------------------------------------------------------------------------
# Target helpers
# ---------------------------------------------------------------------------

def hrZ(z):
    """Heart rate zone target (zone number 1-5 as set in Garmin Connect)."""
    return {"type": "hr_zone", "zone": z}


def hrR(low, high):
    """Custom heart rate range target (bpm)."""
    return {"type": "hr_range", "low": low, "high": high}


def pwr(low, high):
    """Custom power range target (watts)."""
    return {"type": "power_range", "low": low, "high": high}


def OPEN():
    """Open target — no beeping, run by feel / all-out."""
    return {"type": "open"}


def NONE():
    """No target (rest / placeholder)."""
    return {"type": "none"}


# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------

def full_name(workout):
    """Full workout name: ``YYYYMMDD_<code>`` (used as Garmin workout name)."""
    return f"{workout['date'].replace('-', '')}_{workout['code']}"


def short_name(workout, max_len=15):
    """Short name for the watch face (FIT workout_name, max 15 chars)."""
    mmdd = workout['date'][5:].replace('-', '')
    parts = workout['code'].split('-')
    short = f"{mmdd} {parts[0]}{parts[1][:3] if len(parts) > 1 else ''}{parts[-1][:6] if len(parts) > 2 else ''}"
    return short[:max_len]
