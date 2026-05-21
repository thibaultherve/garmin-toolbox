"""Garmin Connect login helper — token-cache only (headless, no MFA prompt).

In a containerized context we can't prompt for password / MFA. We rely entirely
on the shared token cache mounted from the NAS
(/volume2/docker/garmingrafana/garminconnect-tokens) which is refreshed by the
garmin-fetch-data container.

If the token is expired or missing, callers get a clear error pointing at how
to refresh from a workstation with interactive access.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TOKEN_DIR = Path.home() / ".garminconnect"


def login_cached():
    """Return a logged-in Garmin client using only the cached token.

    Raises RuntimeError with a clear message if the cache is missing or expired.
    Never prompts for credentials.
    """
    try:
        from garminconnect import Garmin, GarminConnectAuthenticationError
    except ImportError as exc:
        raise RuntimeError(f"garminconnect not installed: {exc}")

    if not TOKEN_DIR.exists():
        raise RuntimeError(
            f"Token cache missing at {TOKEN_DIR}. Refresh it from a workstation "
            "with interactive access (run garmin_login.py --force-relogin)."
        )

    try:
        api = Garmin()
        api.login(str(TOKEN_DIR))
        logger.info("Garmin login via token cache OK")
        return api
    except (FileNotFoundError, GarminConnectAuthenticationError) as exc:
        raise RuntimeError(
            f"Garmin token cache invalid or expired ({type(exc).__name__}: {exc}). "
            "Refresh it from a workstation by re-running upload_and_schedule.py "
            "interactively, or via the garmin-fetch-data container restart."
        )
    except Exception as exc:
        raise RuntimeError(f"Unexpected Garmin login error: {exc}")
