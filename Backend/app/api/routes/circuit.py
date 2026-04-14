"""
Grupo 1 — Gestion de Circuito.

POST /upload            Sube, valida y compila un archivo DSS.
GET  /{circuit_id}      Informacion basica del circuito compilado.
DELETE /{circuit_id}    Elimina el circuito de Redis.
"""
from __future__ import annotations

import datetime
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.dependencies import get_redis, require_circuit
from app.config import settings
from app.core.dss_engine import (
    CircuitDidNotConvergeError,
    DSSEngine,
    DSSEngineError,
)

router = APIRouter()


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_circuit(
    main_dss: UploadFile = File(..., description="Archivo principal del circuito (.dss)"),
    linecodes_dss: UploadFile = File(None, description="Definiciones de codigos de linea (.dss)"),
    busxy_csv: UploadFile = File(None, description="Coordenadas de barras (.csv) — opcional, no afecta la simulacion"),
):
    """
    Sube un archivo DSS, lo valida compilandolo con OpenDSS y lo almacena en
    Redis con un TTL de 2 horas. Retorna el circuit_id y la informacion basica.
    """
    if not (main_dss.filename or "").endswith(".dss"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_FILE_EXTENSION",
                "message": "El archivo principal debe tener extension .dss",
            },
        )

    dss_content = (await main_dss.read()).decode("utf-8")
    linecodes_content: str | None = None
    if linecodes_dss:
        linecodes_content = (await linecodes_dss.read()).decode("utf-8")

    # Compilar y validar el circuito
    # Nota: la compilacion ocurre aqui en el proceso API (no en Celery) porque
    # es rapida (300-1500ms) y necesitamos los metadatos del circuito de inmediato.
    preprocessing_warnings: list[str] = []
    if linecodes_content is None and "ieeelinecodes" in dss_content.lower():
        preprocessing_warnings.append(
            "Se elimino referencia a IEEELineCodes.dss (resuelto automaticamente)"
        )

    try:
        engine = DSSEngine()
        circuit_info = engine.load_circuit(dss_content, linecodes_content)
    except CircuitDidNotConvergeError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "CIRCUIT_DID_NOT_CONVERGE",
                "message": str(exc),
                "suggestion": (
                    "Verifique que el circuito tenga una fuente definida "
                    "y que las cargas sean validas."
                ),
            },
        ) from exc
    except DSSEngineError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_DSS_FORMAT",
                "message": "Error de compilacion en el archivo DSS.",
                "detail": str(exc),
            },
        ) from exc

    # Obtener buses y fases disponibles
    buses_phases = engine.get_buses_phases()

    # Persistir en Redis con TTL
    circuit_id = f"ckt_{uuid.uuid4().hex[:12]}"
    r = get_redis()
    r.setex(f"circuit:{circuit_id}:dss", settings.CIRCUIT_TTL_SECONDS, dss_content)
    if linecodes_content:
        r.setex(
            f"circuit:{circuit_id}:linecodes",
            settings.CIRCUIT_TTL_SECONDS,
            linecodes_content,
        )
    # Guardar metadatos del circuito para GET /{circuit_id}
    import json
    r.setex(
        f"circuit:{circuit_id}:info",
        settings.CIRCUIT_TTL_SECONDS,
        json.dumps(circuit_info),
    )
    r.setex(
        f"circuit:{circuit_id}:buses_phases",
        settings.CIRCUIT_TTL_SECONDS,
        json.dumps({k: list(v) for k, v in buses_phases.items()}),
    )

    expires_at = (
        datetime.datetime.utcnow()
        + datetime.timedelta(seconds=settings.CIRCUIT_TTL_SECONDS)
    ).isoformat() + "Z"

    return {
        "circuit_id": circuit_id,
        "circuit_info": circuit_info,
        "buses": list(buses_phases.keys()),
        "buses_phases": {k: list(v) for k, v in buses_phases.items()},
        "expires_at": expires_at,
        "preprocessing_warnings": preprocessing_warnings,
    }


@router.get("/{circuit_id}")
def get_circuit(circuit_id: str):
    """Retorna informacion basica del circuito. Util para verificar que sigue activo."""
    import json

    r = get_redis()
    circuit_data = require_circuit(circuit_id, r)

    info_raw = r.get(f"circuit:{circuit_id}:info")
    buses_phases_raw = r.get(f"circuit:{circuit_id}:buses_phases")

    info = json.loads(info_raw) if info_raw else {}
    buses_phases = json.loads(buses_phases_raw) if buses_phases_raw else {}

    # TTL restante para calcular expires_at
    ttl = r.ttl(f"circuit:{circuit_id}:dss")
    expires_at = (
        datetime.datetime.utcnow() + datetime.timedelta(seconds=max(ttl, 0))
    ).isoformat() + "Z"

    # Reconstruir info de lineas sin recompilar (usamos el engine con el contenido guardado)
    try:
        engine = DSSEngine()
        engine.load_circuit(
            circuit_data["dss_content"], circuit_data["linecodes_content"]
        )
        lines = engine.get_lines_info()
    except Exception:
        lines = []

    return {
        "circuit_id": circuit_id,
        **info,
        "buses_phases": buses_phases,
        "lines": lines,
        "expires_at": expires_at,
    }


@router.delete("/{circuit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_circuit(circuit_id: str):
    """Elimina el circuito de Redis antes de que expire. Libera memoria."""
    r = get_redis()
    # Eliminar todas las claves asociadas al circuito
    keys = r.keys(f"circuit:{circuit_id}:*")
    if keys:
        r.delete(*keys)
    # 204 No Content — sin cuerpo de respuesta
