"""
Upload les workouts dans Garmin Connect via l'API + schedule au calendrier.

Usage:
    python upload_and_schedule.py            # upload + schedule
    python upload_and_schedule.py --dry-run  # affiche le JSON sans envoyer
    python upload_and_schedule.py --replace  # remplace les versions existantes

Identifiants demandes a la volee (non stockes).
"""

import argparse
import getpass
import json
import sys
import time

import workouts_data as wd

# =============================================================================
# Mapping vers le format JSON Garmin Connect
# =============================================================================

SPORT_RUNNING = {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1}

STEP_TYPE = {
    "warmup":   {"stepTypeId": 1, "stepTypeKey": "warmup",   "displayOrder": 1},
    "cooldown": {"stepTypeId": 2, "stepTypeKey": "cooldown", "displayOrder": 2},
    "interval": {"stepTypeId": 3, "stepTypeKey": "interval", "displayOrder": 3},
    "recovery": {"stepTypeId": 4, "stepTypeKey": "recovery", "displayOrder": 4},
    "rest":     {"stepTypeId": 5, "stepTypeKey": "rest",     "displayOrder": 5},
    "active":   {"stepTypeId": 8, "stepTypeKey": "other",    "displayOrder": 6},  # generic active
}

COND_TIME = {"conditionTypeId": 2, "conditionTypeKey": "time",
             "displayOrder": 2, "displayable": True}
COND_LAP_BUTTON = {"conditionTypeId": 1, "conditionTypeKey": "lap.button",
                   "displayOrder": 1, "displayable": True}
COND_ITERATIONS = {"conditionTypeId": 7, "conditionTypeKey": "iterations",
                   "displayOrder": 7, "displayable": False}

TARGET_NO = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target", "displayOrder": 1}


def make_target(target):
    """
    Convertit un target neutre vers (targetType_dict, value_one, value_two, zone_number).

    Garmin Connect distingue :
      - Zone-based : zoneNumber renseigne, targetValueOne/Two = null
      - Custom range : targetValueOne/Two renseignes, zoneNumber = null
    """
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
    raise ValueError(f"Target type inconnu: {t}")


def neutral_to_garmin_step(step_neutral, step_order):
    """Convertit un step neutre en dict Garmin ExecutableStepDTO."""
    target_type, val_one, val_two, zone_number = make_target(
        step_neutral.get("target", {"type": "none"}))

    if step_neutral.get("duration_open"):
        end_cond = COND_LAP_BUTTON
        end_val = None
    else:
        end_cond = COND_TIME
        end_val = step_neutral["duration_min"] * 60.0  # secondes

    step = {
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
    return step


def neutral_to_garmin_steps(steps_neutral, start_order=1):
    """
    Aplatit recursivement les steps + repeat en sequence Garmin.
    Repeats sont representes par RepeatGroupDTO contenant les sous-steps.
    """
    out = []
    order = start_order
    for s in steps_neutral:
        if s["kind"] == "step":
            out.append(neutral_to_garmin_step(s, order))
            order += 1
        elif s["kind"] == "repeat":
            inner_steps = []
            for inner in s["steps"]:
                if inner["kind"] != "step":
                    raise ValueError("Repeat imbrique non supporte")
                inner_steps.append(neutral_to_garmin_step(inner, order))
                order += 1
            repeat_group = {
                "type": "RepeatGroupDTO",
                "stepOrder": order,
                "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat", "displayOrder": 7},
                "numberOfIterations": s["iterations"],
                "smartRepeat": False,
                "endCondition": COND_ITERATIONS,
                "endConditionValue": float(s["iterations"]),
                "workoutSteps": inner_steps,
            }
            out.append(repeat_group)
            order += 1
    return out


def workout_to_garmin_json(workout):
    """Convertit un workout neutre en JSON pret pour l'API Garmin."""
    full_name = wd.full_name(workout)
    steps = neutral_to_garmin_steps(workout["steps"])

    def estimate_seconds(steps):
        total = 0
        for s in steps:
            if s.get("type") == "ExecutableStepDTO":
                if s.get("endConditionValue"):
                    total += s["endConditionValue"]
            elif s.get("type") == "RepeatGroupDTO":
                inner = estimate_seconds(s.get("workoutSteps", []))
                total += inner * s.get("numberOfIterations", 1)
        return total

    estimated = int(estimate_seconds(steps))

    return {
        "workoutName": full_name,
        "description": workout.get("description", "")[:1024],
        "sportType": SPORT_RUNNING,
        "estimatedDurationInSecs": estimated,
        "workoutSegments": [{
            "segmentOrder": 1,
            "sportType": SPORT_RUNNING,
            "workoutSteps": steps,
        }],
    }


# =============================================================================
# Upload + Schedule
# =============================================================================

def fetch_existing_by_name(api):
    """Recupere tous les workouts du compte, indexes par workoutName."""
    existing = {}
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Affiche le JSON sans envoyer a Garmin")
    ap.add_argument("--limit", type=int, default=0,
                    help="Limite le nombre de workouts traites (test)")
    ap.add_argument("--code", type=str, default=None,
                    help="Ne traite que le workout dont le code matche (ex: C0-Ven-TestFCmax)")
    ap.add_argument("--replace", action="store_true",
                    help="Supprime les workouts existants du meme nom avant upload")
    ap.add_argument("--cleanup-only", action="store_true",
                    help="Supprime les workouts du plan sans en uploader (cleanup)")
    args = ap.parse_args()

    workouts = wd.WORKOUTS
    if args.code:
        workouts = [w for w in workouts if w["code"] == args.code]
        if not workouts:
            sys.exit(f"Aucun workout trouve avec code={args.code}")
    if args.limit:
        workouts = workouts[:args.limit]

    if args.dry_run:
        for w in workouts[:2]:  # juste 2 pour le dry-run
            payload = workout_to_garmin_json(w)
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            print("---")
        print(f"Dry-run termine ({len(workouts)} workouts seraient envoyes)")
        return

    # Login : reutilise le token cache via garmin_extras/garmin_login pour eviter
    # les rate-limits Garmin (429) sur logins frais repetes.
    sys.path.insert(0, "garmin_extras")
    from garmin_login import login as gx_login
    print("=== Login Garmin Connect ===")
    api = gx_login()
    print()

    # Fetch existing workouts si replace ou cleanup-only
    existing_by_name = {}
    if args.replace or args.cleanup_only:
        print("Recuperation des workouts existants...")
        existing_by_name = fetch_existing_by_name(api)
        target_names = {wd.full_name(w) for w in workouts}
        nb_matching = sum(len(existing_by_name.get(n, [])) for n in target_names)
        print(f"  {nb_matching} workouts existants matchent le plan\n")

    # Cleanup-only : on supprime et on s'arrete
    if args.cleanup_only:
        deleted = 0
        for w in workouts:
            full_name = wd.full_name(w)
            for old_id in existing_by_name.get(full_name, []):
                try:
                    api.delete_workout(old_id)
                    print(f"  deleted {full_name} (id={old_id})")
                    deleted += 1
                    time.sleep(0.3)
                except Exception as e:
                    print(f"  ECHEC delete {full_name} (id={old_id}): {e}")
        print(f"\n=== {deleted} workouts supprimes ===")
        return

    # Upload + schedule
    success, failed = [], []
    for i, w in enumerate(workouts, 1):
        full_name = wd.full_name(w)
        print(f"[{i}/{len(workouts)}] {full_name}")
        try:
            # Replace : supprimer doublons existants
            if args.replace:
                for old_id in existing_by_name.get(full_name, []):
                    try:
                        api.delete_workout(old_id)
                        print(f"   deleted old id={old_id}")
                        time.sleep(0.3)
                    except Exception as e:
                        print(f"   warn: delete failed id={old_id}: {e}")

            payload = workout_to_garmin_json(w)
            result = api.upload_workout(payload)
            workout_id = result.get("workoutId")
            if not workout_id:
                raise RuntimeError(f"Pas de workoutId retourne: {result}")
            print(f"   uploaded id={workout_id}")

            # Schedule
            api.schedule_workout(workout_id, w["date"])
            print(f"   scheduled le {w['date']}")
            success.append((full_name, workout_id, w["date"]))

            time.sleep(0.5)  # politesse API
        except Exception as e:
            print(f"   ECHEC: {e}")
            failed.append((full_name, str(e)))

    # Recap
    print(f"\n=== RECAP ===")
    print(f"Reussites : {len(success)}/{len(workouts)}")
    if failed:
        print(f"Echecs    : {len(failed)}")
        for name, err in failed:
            print(f"  - {name}: {err}")


if __name__ == "__main__":
    main()
