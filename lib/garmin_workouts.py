"""Garmin Connect workout JSON conversion (neutral dict -> Garmin API payload).

Lifted from upload_and_schedule.py — same conversion rules, no behavioral
changes.
"""
from __future__ import annotations

from typing import Any

SPORT_RUNNING = {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1}
SPORT_CYCLING = {"sportTypeId": 2, "sportTypeKey": "cycling", "displayOrder": 2}

# Map the neutral workout "sport" field -> Garmin sportType dict. Default running.
SPORTS = {"running": SPORT_RUNNING, "cycling": SPORT_CYCLING}

STEP_TYPE = {
    "warmup":   {"stepTypeId": 1, "stepTypeKey": "warmup",   "displayOrder": 1},
    "cooldown": {"stepTypeId": 2, "stepTypeKey": "cooldown", "displayOrder": 2},
    "interval": {"stepTypeId": 3, "stepTypeKey": "interval", "displayOrder": 3},
    "recovery": {"stepTypeId": 4, "stepTypeKey": "recovery", "displayOrder": 4},
    "rest":     {"stepTypeId": 5, "stepTypeKey": "rest",     "displayOrder": 5},
    "active":   {"stepTypeId": 8, "stepTypeKey": "other",    "displayOrder": 6},
}

COND_TIME = {"conditionTypeId": 2, "conditionTypeKey": "time",
             "displayOrder": 2, "displayable": True}
COND_DISTANCE = {"conditionTypeId": 3, "conditionTypeKey": "distance",
                 "displayOrder": 3, "displayable": True}
COND_LAP_BUTTON = {"conditionTypeId": 1, "conditionTypeKey": "lap.button",
                   "displayOrder": 1, "displayable": True}
COND_ITERATIONS = {"conditionTypeId": 7, "conditionTypeKey": "iterations",
                   "displayOrder": 7, "displayable": False}

TARGET_NO = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target", "displayOrder": 1}


def _make_target(target: dict[str, Any]) -> tuple[dict, Any, Any, Any]:
    """Convert a neutral target dict -> (targetType_dict, value_one, value_two, zone_number)."""
    t = target["type"]
    if t == "none" or t == "open":
        return TARGET_NO, None, None, None
    if t == "hr_zone":
        return ({"workoutTargetTypeId": 4, "workoutTargetTypeKey": "heart.rate.zone",
                 "displayOrder": 4},
                None, None, target["zone"])
    if t == "power_zone":
        return ({"workoutTargetTypeId": 2, "workoutTargetTypeKey": "power.zone",
                 "displayOrder": 2},
                None, None, target["zone"])
    if t == "power_range":
        return ({"workoutTargetTypeId": 2, "workoutTargetTypeKey": "power.zone",
                 "displayOrder": 2},
                target["low"], target["high"], None)
    if t == "hr_range":
        return ({"workoutTargetTypeId": 4, "workoutTargetTypeKey": "heart.rate.zone",
                 "displayOrder": 4},
                target["low"], target["high"], None)
    raise ValueError(f"Unknown target type: {t}")


def _neutral_to_garmin_step(step_neutral: dict[str, Any], step_order: int) -> dict[str, Any]:
    target_type, val_one, val_two, zone_number = _make_target(
        step_neutral.get("target", {"type": "none"})
    )
    if step_neutral.get("duration_open"):
        end_cond = COND_LAP_BUTTON
        end_val = None
    elif "distance_km" in step_neutral:
        end_cond = COND_DISTANCE
        end_val = step_neutral["distance_km"] * 1000.0
    else:
        end_cond = COND_TIME
        end_val = step_neutral["duration_min"] * 60.0

    return {
        "type": "ExecutableStepDTO",
        "stepOrder": step_order,
        "stepType": STEP_TYPE.get(step_neutral.get("type", "active"), STEP_TYPE["active"]),
        "endCondition": end_cond,
        "endConditionValue": end_val,
        "targetType": target_type,
        "targetValueOne": val_one,
        "targetValueTwo": val_two,
        "zoneNumber": zone_number,
        "description": step_neutral.get("notes", "") or step_neutral.get("name", ""),
    }


def _neutral_to_garmin_steps(steps_neutral: list[dict], start_order: int = 1) -> list[dict]:
    out = []
    order = start_order
    for s in steps_neutral:
        if s["kind"] == "step":
            out.append(_neutral_to_garmin_step(s, order))
            order += 1
        elif s["kind"] == "repeat":
            inner = []
            for inner_s in s["steps"]:
                if inner_s["kind"] != "step":
                    raise ValueError("Nested repeats not supported")
                inner.append(_neutral_to_garmin_step(inner_s, order))
                order += 1
            out.append({
                "type": "RepeatGroupDTO",
                "stepOrder": order,
                "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat", "displayOrder": 7},
                "numberOfIterations": s["iterations"],
                "smartRepeat": False,
                "endCondition": COND_ITERATIONS,
                "endConditionValue": float(s["iterations"]),
                "workoutSteps": inner,
            })
            order += 1
    return out


def _estimate_seconds(steps: list[dict]) -> int:
    """Estimate total workout duration. Distance steps use 6:30/km (390s/km)."""
    total = 0
    for s in steps:
        if s.get("type") == "ExecutableStepDTO":
            cond = s.get("endCondition", {}).get("conditionTypeKey", "")
            val = s.get("endConditionValue")
            if val:
                if cond == "distance":
                    total += val / 1000.0 * 390
                else:
                    total += val
        elif s.get("type") == "RepeatGroupDTO":
            inner = _estimate_seconds(s.get("workoutSteps", []))
            total += inner * s.get("numberOfIterations", 1)
    return int(total)


def workout_to_garmin_payload(workout: dict, full_name: str) -> dict:
    """Build the Garmin API JSON payload from a neutral workout dict."""
    steps = _neutral_to_garmin_steps(workout["steps"])
    sport = SPORTS.get(workout.get("sport", "running"), SPORT_RUNNING)
    return {
        "workoutName": full_name,
        "description": workout.get("description", "")[:1024],
        "sportType": sport,
        "estimatedDurationInSecs": _estimate_seconds(steps),
        "workoutSegments": [{
            "segmentOrder": 1,
            "sportType": sport,
            "workoutSteps": steps,
        }],
    }


def fetch_existing_by_name(api) -> dict[str, list[int]]:
    """Return {workoutName: [workoutId, ...]} for all workouts on the account."""
    existing: dict[str, list[int]] = {}
    start = 0
    while True:
        batch = api.get_workouts(start, 100)
        if not batch:
            break
        for w in batch:
            name = w.get("workoutName", "")
            existing.setdefault(name, []).append(w.get("workoutId"))
        if len(batch) < 100:
            break
        start += 100
    return existing
