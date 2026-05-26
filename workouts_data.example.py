"""
Example training plan for garmin-toolbox.

Copy this file to workouts_data.py and customise with your own workouts.
workouts_data.py is gitignored — your personal plan stays local.

Structure
---------
- WORKOUTS : list of workout dicts, consumed by the MCP tools
  (list_workouts, get_workout, garmin_upload_workout, etc.)
- Each workout has: date (ISO), code (unique ID), description, steps
- Steps use the helpers from workouts_helpers.py

Naming convention (recommended)
-------------------------------
  Code format:  C<cycle>-S<week>-<DayAbbrev>-<ShortType>
  Examples:     C1-S1-Tue-Z2-50min, C1-S3-Wed-Hills6x60s, C2-S1-Sun-LR-120min

Targets
-------
  hrZ(n)         → HR zone (1-5, as configured in Garmin Connect)
  hrR(low, high) → custom HR range in bpm
  pwr(low, high) → custom power range in watts
  OPEN()         → no target (all-out / feel-based)
  NONE()         → no target (rest)

Tips
----
- The MCP reloads this file on every call (importlib.reload) — edit via
  your editor or SMB, changes are picked up instantly without restarting
  the container.
- Set duration_open=True for lap-button steps (the watch waits for a
  manual lap press instead of auto-ending after duration_min).
- Use rep(n, step1, step2) for interval blocks.
"""

from workouts_helpers import *  # noqa: F401,F403

WORKOUTS = []


# ---------------------------------------------------------------------------
# Example workouts — replace with your own plan
# ---------------------------------------------------------------------------

# Easy Z2 run (40 min)
WORKOUTS.append({
    "date": "2026-01-05",
    "code": "C1-S1-Mon-Z2-40min",
    "description": "Easy Z2 run 40min. Stay in zone 2, walk uphills if needed.",
    "steps": [
        s("Warmup", 10, type="warmup", target=hrZ(2)),
        s("Z2 steady", 25, type="active", target=hrZ(2),
          notes="Conversational pace. Slow down if drifting into Z3."),
        s("Cooldown", 5, type="cooldown", target=hrZ(2)),
    ],
})

# VO2max intervals (5x3 min)
WORKOUTS.append({
    "date": "2026-01-07",
    "code": "C1-S1-Wed-VO2max-5x3min",
    "description": "VO2max intervals 5x3min with 2min recovery jog.",
    "steps": [
        s("Warmup", 15, type="warmup", target=hrZ(2)),
        rep(5,
            s("VO2max", 3, type="interval", target=hrZ(5),
              notes="Hard but sustainable. RPE 9/10."),
            s("Recovery jog", 2, type="recovery", target=hrZ(2))),
        s("Cooldown", 10, type="cooldown", target=hrZ(2)),
    ],
})

# Long run with tempo block (90 min)
WORKOUTS.append({
    "date": "2026-01-11",
    "code": "C1-S1-Sun-LR-90min",
    "description": "Long run 90min with 10min tempo block in the middle.",
    "steps": [
        s("Warmup", 15, type="warmup", target=hrZ(2)),
        s("Z2 first half", 30, type="active", target=hrZ(2)),
        s("Tempo block", 10, type="interval", target=hrZ(3),
          notes="Marathon pace effort, controlled breathing."),
        s("Z2 second half", 30, type="active", target=hrZ(2)),
        s("Cooldown", 5, type="cooldown", target=hrZ(2)),
    ],
})

# Hill repeats (6x60s)
WORKOUTS.append({
    "date": "2026-01-14",
    "code": "C1-S2-Wed-Hills6x60s",
    "description": "Hill repeats 6x60s on a moderate grade (5-8%). Walk down recovery.",
    "steps": [
        s("Warmup jog to hill", 15, type="warmup", target=hrZ(2),
          duration_open=True,
          notes="Jog to the base of your hill. Press lap to start reps."),
        rep(6,
            s("Hill 60s", 1.0, type="interval", target=hrZ(3),
              notes="Strong rhythm, not a sprint. RPE 7-8/10."),
            s("Walk down", 2.0, type="recovery", target=hrZ(2),
              notes="Walk back to the start. Let HR drop to Z2.")),
        s("Cooldown jog home", 10, type="cooldown", target=hrZ(2),
          duration_open=True,
          notes="Easy jog home. Press lap to finish."),
    ],
})
