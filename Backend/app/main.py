"""
Punto de entrada de la aplicacion FastAPI.

Registra todos los routers, configura CORS, inicializa el sistema de logging
y expone el endpoint /health con informacion detallada para monitoreo.
"""
from __future__ import annotations

import os
import time
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict

import redis as redis_lib
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.api.dependencies import SessionLocal, _engine
from app.api.routes import analysis, circuit, export, hosting, simulation, tasks
from app.config import settings
from app.core.logging_config import get_logger, setup_logging

# ---------------------------------------------------------------------------
# Inicializar logging antes de todo lo demas
# ---------------------------------------------------------------------------

setup_logging(debug=settings.DEBUG)

_logger = get_logger(__name__)
_logger.info(
    "Iniciando %s v%s | debug=%s | env=%s",
    settings.APP_TITLE,
    settings.APP_VERSION,
    settings.DEBUG,
    "development" if settings.DEBUG else "production",
)

# ---------------------------------------------------------------------------
# Instancia de la aplicacion
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
)

# ---------------------------------------------------------------------------
# Middleware de logging HTTP
# Loggea CADA request/response: metodo, path, status, duracion, request_id.
# ---------------------------------------------------------------------------

# Paths que no merecen un log completo (reducir ruido)
_SILENT_PATHS = {"/api/v1/health"}

# Tiempo (ms) a partir del cual se loggea como WARNING
_SLOW_REQUEST_MS = 3_000


@app.middleware("http")
async def http_logging_middleware(request: Request, call_next) -> Response:
    request_id = uuid.uuid4().hex[:8]
    t0 = time.perf_counter()

    client_ip = request.client.host if request.client else "-"
    path = request.url.path
    query = f"?{request.url.query}" if request.url.query else ""
    silent = path in _SILENT_PATHS

    if not silent:
        _logger.info(
            ">> %s %s%s | rid=%s | ip=%s",
            request.method, path, query, request_id, client_ip,
        )

    response = await call_next(request)

    ms = round((time.perf_counter() - t0) * 1000, 1)

    if not silent:
        slow_tag = " [SLOW]" if ms > _SLOW_REQUEST_MS else ""
        level = logging.WARNING if ms > _SLOW_REQUEST_MS or response.status_code >= 500 else logging.INFO
        _logger.log(
            level,
            "<< %s %s %d | %.0f ms%s | rid=%s",
            request.method, path, response.status_code, ms, slow_tag, request_id,
        )
    elif response.status_code >= 400:
        _logger.warning(
            "<< %s %s %d | %.0f ms | rid=%s",
            request.method, path, response.status_code, ms, request_id,
        )

    response.headers["X-Request-ID"] = request_id
    return response


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(
    circuit.router,
    prefix=f"{settings.API_V1_PREFIX}/circuit",
    tags=["Circuito"],
)
app.include_router(
    analysis.router,
    prefix=f"{settings.API_V1_PREFIX}/circuit",
    tags=["Analisis"],
)
app.include_router(
    simulation.router,
    prefix=f"{settings.API_V1_PREFIX}/circuit",
    tags=["Simulacion"],
)
app.include_router(
    hosting.router,
    prefix=f"{settings.API_V1_PREFIX}/circuit",
    tags=["Hosting Capacity"],
)
app.include_router(
    tasks.router,
    prefix=f"{settings.API_V1_PREFIX}/tasks",
    tags=["Tareas Asincronas"],
)
app.include_router(
    export.router,
    prefix=f"{settings.API_V1_PREFIX}/circuit",
    tags=["Exportacion"],
)

# ---------------------------------------------------------------------------
# Tiempo de arranque (para calcular uptime)
# ---------------------------------------------------------------------------

_START_TIME: float = time.time()


# ---------------------------------------------------------------------------
# Endpoint /health
# ---------------------------------------------------------------------------


@app.get(
    f"{settings.API_V1_PREFIX}/health",
    tags=["Sistema"],
    summary="Estado del servidor",
    response_description="Informacion detallada del estado de todos los componentes",
)
def health_check() -> Dict:
    """
    Endpoint de salud para monitoreo en produccion.

    Verifica el estado de todos los componentes del sistema:
    - **Redis**: conectividad y latencia de PING.
    - **PostgreSQL**: conectividad y latencia de SELECT 1.
    - **Celery**: numero de workers activos (via Redis).
    - **Sistema**: uptime, version, PID del proceso.

    El campo `status` es `"ok"` solo si todos los componentes estan saludables.
    Ante cualquier falla, `status` es `"degraded"` y el campo del componente
    afectado contiene `"status": "error"` con el mensaje de error.
    """
    uptime_seconds = round(time.time() - _START_TIME, 1)
    uptime_human = str(timedelta(seconds=int(uptime_seconds)))

    components: Dict[str, Dict] = {}
    all_healthy = True

    # --- Redis ---
    redis_status = _check_redis()
    components["redis"] = redis_status
    if redis_status["status"] != "ok":
        all_healthy = False

    # --- PostgreSQL ---
    postgres_status = _check_postgres()
    components["postgres"] = postgres_status
    if postgres_status["status"] != "ok":
        all_healthy = False

    # --- Celery workers (via Redis inspect) ---
    celery_status = _check_celery()
    components["celery"] = celery_status
    if celery_status["status"] not in ("ok", "no_workers"):
        all_healthy = False

    return {
        "status": "ok" if all_healthy else "degraded",
        "version": settings.APP_VERSION,
        "uptime_seconds": uptime_seconds,
        "uptime_human": uptime_human,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "pid": os.getpid(),
        "environment": "development" if settings.DEBUG else "production",
        "components": components,
    }


# ---------------------------------------------------------------------------
# Checks de dependencias
# ---------------------------------------------------------------------------


def _check_redis() -> Dict:
    """Verifica la conexion a Redis y mide latencia de PING."""
    try:
        r = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        t0 = time.perf_counter()
        r.ping()
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        info = r.info("memory")
        used_memory_mb = round(info.get("used_memory", 0) / (1024 * 1024), 2)
        maxmemory_mb = round(info.get("maxmemory", 0) / (1024 * 1024), 2)

        return {
            "status": "ok",
            "latency_ms": latency_ms,
            "used_memory_mb": used_memory_mb,
            "maxmemory_mb": maxmemory_mb if maxmemory_mb > 0 else "unlimited",
            "url": _sanitize_url(settings.REDIS_URL),
        }
    except Exception as exc:
        _logger.error("health check Redis FAILED | %s", exc)
        return {
            "status": "error",
            "error": str(exc),
            "url": _sanitize_url(settings.REDIS_URL),
        }


def _check_postgres() -> Dict:
    """Verifica la conexion a PostgreSQL y mide latencia de SELECT 1."""
    try:
        with _engine.connect() as conn:
            t0 = time.perf_counter()
            conn.execute(text("SELECT 1"))
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        return {
            "status": "ok",
            "latency_ms": latency_ms,
            "url": _sanitize_url(settings.DATABASE_URL),
        }
    except OperationalError as exc:
        _logger.error("health check Postgres FAILED | %s", exc)
        return {
            "status": "error",
            "error": str(exc),
            "url": _sanitize_url(settings.DATABASE_URL),
        }
    except Exception as exc:
        _logger.error("health check Postgres FAILED | %s", exc)
        return {
            "status": "error",
            "error": str(exc),
            "url": _sanitize_url(settings.DATABASE_URL),
        }


def _check_celery() -> Dict:
    """
    Verifica workers Celery activos usando el broker Redis.
    Retorna status "no_workers" (no "error") si no hay workers levantados.
    """
    try:
        from app.tasks.celery_app import celery_app

        inspector = celery_app.control.inspect(timeout=1.0)
        active_workers = inspector.active() or {}
        worker_names = list(active_workers.keys())

        if worker_names:
            _logger.debug("Celery workers activos: %s", worker_names)
        else:
            _logger.warning("health check Celery | sin workers activos")

        return {
            "status": "ok" if worker_names else "no_workers",
            "active_workers": len(worker_names),
            "worker_names": worker_names,
            "broker_url": _sanitize_url(settings.CELERY_BROKER_URL),
        }
    except Exception as exc:
        _logger.error("health check Celery FAILED | %s", exc)
        return {
            "status": "error",
            "error": str(exc),
            "broker_url": _sanitize_url(settings.CELERY_BROKER_URL),
        }


def _sanitize_url(url: str) -> str:
    """Oculta credenciales en URLs para no exponerlas en el health endpoint."""
    import re

    return re.sub(r"(:)[^:@/]+(@)", r"\1****\2", url)
