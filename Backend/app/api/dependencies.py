"""
Dependencias compartidas para los routers de FastAPI.

Proveen conexiones a Redis y PostgreSQL como dependencias inyectables,
manteniendo el ciclo de vida de las conexiones correctamente.
"""
import asyncio
from typing import Generator

import redis as redis_lib
from fastapi import HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Lock global para OpenDSS
#
# opendssdirect tiene afinidad al hilo principal (event loop de asyncio).
# Todos los endpoints que usan DSSEngine son async def y corren DSS inline
# en el event loop (sin executor). Este lock serializa accesos concurrentes.
# ---------------------------------------------------------------------------

dss_lock = asyncio.Lock()

# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

_engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def get_db() -> Generator[Session, None, None]:
    """Dependencia FastAPI que provee una sesion de base de datos."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------


def get_redis() -> redis_lib.Redis:
    """Retorna un cliente Redis con decode_responses=True."""
    return redis_lib.from_url(settings.REDIS_URL, decode_responses=True)


# ---------------------------------------------------------------------------
# Helpers comunes para rutas
# ---------------------------------------------------------------------------


def require_circuit(circuit_id: str, r: redis_lib.Redis) -> dict:
    """
    Verifica que el circuit_id exista en Redis y retorna sus datos.
    Lanza HTTPException 404 si no existe o expiro.
    """
    dss_content = r.get(f"circuit:{circuit_id}:dss")
    if not dss_content:
        logger.warning("circuit NOT FOUND | circuit_id=%s (expirado o nunca subido)", circuit_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "CIRCUIT_NOT_FOUND",
                "message": "El circuit_id no existe o ha expirado.",
                "suggestion": (
                    "Vuelva a cargar el archivo DSS mediante "
                    "POST /api/v1/circuit/upload"
                ),
            },
        )
    logger.debug("circuit OK | circuit_id=%s", circuit_id)
    linecodes_content = r.get(f"circuit:{circuit_id}:linecodes")
    return {
        "dss_content": dss_content,
        "linecodes_content": linecodes_content,
    }
