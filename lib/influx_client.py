"""Shared InfluxDB v1.x HTTP client.

Reads creds from env vars (set via docker-compose). Returns parsed rows as
list[dict]. Never silently swallows errors — raises loudly so callers either
fail fast or fall back explicitly.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

INFLUXDB_HOST = os.getenv("INFLUXDB_HOST", "influxdb")
INFLUXDB_PORT = int(os.getenv("INFLUXDB_PORT", 8086))
INFLUXDB_DATABASE = os.getenv("INFLUXDB_DATABASE", "GarminStats")
INFLUXDB_USERNAME = os.getenv("INFLUXDB_USERNAME", "influxdb_user")
INFLUXDB_PASSWORD = os.getenv("INFLUXDB_PASSWORD", "influxdb_secret_password")

_BASE_URL = f"http://{INFLUXDB_HOST}:{INFLUXDB_PORT}"


def ping() -> bool:
    """Return True if the InfluxDB endpoint responds to /ping."""
    try:
        r = requests.get(f"{_BASE_URL}/ping", timeout=3)
        return r.status_code in (200, 204)
    except Exception as exc:
        logger.warning("InfluxDB ping failed: %s", exc)
        return False


def query(q: str) -> list[dict[str, Any]]:
    """Run an InfluxQL query, return list of dict rows.

    Raises RuntimeError on HTTP error or InfluxDB error payload — never returns
    a fabricated empty list to mask failure.
    """
    r = requests.get(
        f"{_BASE_URL}/query",
        params={"db": INFLUXDB_DATABASE, "q": q},
        auth=(INFLUXDB_USERNAME, INFLUXDB_PASSWORD),
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"InfluxDB HTTP {r.status_code}: {r.text[:500]}")
    j = r.json()
    if "error" in j:
        raise RuntimeError(f"InfluxDB error: {j['error']}")
    rows: list[dict[str, Any]] = []
    for res in j.get("results", []):
        if "error" in res:
            raise RuntimeError(f"InfluxDB result error: {res['error']}")
        for series in res.get("series", []):
            cols = series.get("columns", [])
            for vals in series.get("values", []):
                rows.append(dict(zip(cols, vals)))
    return rows
