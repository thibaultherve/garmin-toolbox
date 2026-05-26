"""
garmin-toolbox MCP server.

Athletic computation + Garmin Connect ops. Companion to garmin-coach (read
InfluxDB) in the same Docker network. Streamable HTTP transport on /mcp.

Tools are organized in 5 internal modules under tools/:
  - pace         : pure math (no I/O)
  - metrics      : TRIMP, ACWR, CTL/ATL/TSB, polarization, decoupling, drift
  - dump         : per-second activity dump (writes to /app/activities/)
  - workouts_plan: read workouts_data.py (training plan)
  - garmin_write : upload/schedule/delete on Garmin Connect
"""
from __future__ import annotations

import logging
import os

from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

MCP_PORT = int(os.getenv("MCP_PORT", 8769))

from mcp.server.fastmcp import FastMCP  # noqa: E402
from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402

mcp = FastMCP(
    "garmin-toolbox",
    instructions=(
        "Sport-science computation engine + Garmin Connect write ops. "
        "Provides pace/speed conversions, training-load metrics (TRIMP, "
        "ACWR, CTL/ATL/TSB, polarization, decoupling, HR drift), "
        "per-second activity dumps with weather context, read access to "
        "the training plan (workouts_data.py), and write operations on "
        "the Garmin Connect account (upload, schedule, delete workouts). "
        "Use this for calculations and mutations. For pre-formatted "
        "training data (activity summaries, zones, recovery, fitness "
        "trends, personal records), use garmin-coach instead. For visual "
        "dashboard inspection or graph comparison, use grafana."
    ),
)

mcp.settings.transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
)


# ---------------------------------------------------------------------------
# Tool registration — one import per module
# ---------------------------------------------------------------------------
from tools import (  # noqa: E402,F401
    pace_tools,
    metrics_tools,
    dump_tools,
    workouts_plan_tools,
    garmin_write_tools,
)

pace_tools.register(mcp)
metrics_tools.register(mcp)
dump_tools.register(mcp)
workouts_plan_tools.register(mcp)
garmin_write_tools.register(mcp)


# ---------------------------------------------------------------------------
# FastAPI app — streamable HTTP only
# ---------------------------------------------------------------------------
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402
from starlette.routing import Mount, Route, Router  # noqa: E402

mcp_asgi = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(a):  # type: ignore[misc]
    async with mcp.session_manager.run():
        yield


async def health_check(request: Request) -> JSONResponse:
    from lib import influx_client

    influx_ok = influx_client.ping()
    return JSONResponse({
        "service": "garmin-toolbox",
        "version": "0.1.0",
        "influxdb": "connected" if influx_ok else "unreachable",
        "mcp_endpoint": f"http://localhost:{MCP_PORT}/mcp",
    })


app = Router(
    routes=[
        Route("/health", endpoint=health_check, methods=["GET"]),
        Mount("/", app=mcp_asgi),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=MCP_PORT,
    )
