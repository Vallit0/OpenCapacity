"""
Punto de entrada de la aplicacion FastAPI.

Registra todos los routers, configura CORS y expone el endpoint /health
con informacion detallada para monitoreo en produccion.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from typing import Dict

import redis as redis_lib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.api.dependencies import SessionLocal, _engine
from app.api.routes import analysis, circuit, export, hosting, simulation, tasks
from app.config import settings

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

        # Informacion adicional util para monitoreo
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
        return {
            "status": "error",
            "error": str(exc),
            "url": _sanitize_url(settings.DATABASE_URL),
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "url": _sanitize_url(settings.DATABASE_URL),
        }


def _check_celery() -> Dict:
    """
    Verifica workers Celery activos usando el broker Redis.
    Retorna status "no_workers" (no "error") si no hay workers levantados —
    esto es esperado durante el desarrollo antes de levantar los containers.
    """
    try:
        from app.tasks.celery_app import celery_app

        inspector = celery_app.control.inspect(timeout=1.0)
        active_workers = inspector.active() or {}
        worker_names = list(active_workers.keys())

        return {
            "status": "ok" if worker_names else "no_workers",
            "active_workers": len(worker_names),
            "worker_names": worker_names,
            "broker_url": _sanitize_url(settings.CELERY_BROKER_URL),
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "broker_url": _sanitize_url(settings.CELERY_BROKER_URL),
        }


def _sanitize_url(url: str) -> str:
    """Oculta credenciales en URLs para no exponerlas en el health endpoint."""
    import re

    # Reemplazar password en URLs del tipo scheme://user:password@host
    return re.sub(r"(:)[^:@/]+(@)", r"\1****\2", url)
