"""
Grupo 4 — Hosting Capacity.

POST /{circuit_id}/hosting-capacity           Inicia calculo asincrono (202).
GET  /{circuit_id}/hosting-capacity           Retorna resultados completados.
GET  /{circuit_id}/hosting-capacity/{bus}     Resultados por barra especifica.
"""
from __future__ import annotations

import datetime
import json
import math
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import get_redis, require_circuit
from app.config import settings
from app.core.logging_config import get_logger
from app.models.schemas import HostingCapacityRequest
from app.tasks.hosting_task import calculate_hosting_capacity

logger = get_logger(__name__)
router = APIRouter()

_SECONDS_PER_COMBINATION = 9.45


@router.post("/{circuit_id}/hosting-capacity", status_code=status.HTTP_202_ACCEPTED)
def start_hosting_capacity(circuit_id: str, body: HostingCapacityRequest):
    """
    Inicia el calculo de hosting capacity para todas las barras del circuito.
    La operacion es asincronica: retorna un task_id con 202 Accepted.
    Usar GET /api/v1/tasks/{task_id}/status para monitorear el progreso.
    """
    r = get_redis()
    circuit_data = require_circuit(circuit_id, r)

    buses_phases_raw = r.get(f"circuit:{circuit_id}:buses_phases")
    buses_phases: dict = json.loads(buses_phases_raw) if buses_phases_raw else {}

    target_buses = body.buses or list(buses_phases.keys())
    total_combinations = sum(
        len(buses_phases.get(b, [])) for b in target_buses
    )
    estimated_seconds = int(math.ceil(total_combinations * _SECONDS_PER_COMBINATION))

    logger.info(
        "HOSTING_CAPACITY iniciando | circuit_id=%s | buses=%d | combinaciones=%d | max_kw=%.0f | est=%ds",
        circuit_id, len(target_buses), total_combinations,
        min(body.max_power_kw, settings.MAX_POWER_KW_LIMIT), estimated_seconds,
    )

    task = calculate_hosting_capacity.apply_async(
        kwargs={
            "circuit_id": circuit_id,
            "dss_content": circuit_data["dss_content"],
            "linecodes_content": circuit_data["linecodes_content"],
            "max_power_kw": min(body.max_power_kw, settings.MAX_POWER_KW_LIMIT),
            "check_voltage": body.check_voltage,
            "check_current": body.check_current,
            "check_power": body.check_power,
            "target_buses": body.buses,
        }
    )
    task_id = task.id
    created_at = datetime.datetime.utcnow().isoformat() + "Z"

    logger.info(
        "HOSTING_CAPACITY encolada | circuit_id=%s | task_id=%s | combinaciones=%d",
        circuit_id, task_id, total_combinations,
    )

    return {
        "task_id": task_id,
        "status": "queued",
        "circuit_id": circuit_id,
        "total_combinations": total_combinations,
        "estimated_duration_seconds": estimated_seconds,
        "poll_url": f"/api/v1/tasks/{task_id}/status",
        "created_at": created_at,
    }


@router.get("/{circuit_id}/hosting-capacity")
def get_hosting_capacity(circuit_id: str):
    """
    Retorna los resultados del ultimo calculo completado de hosting capacity.
    Retorna 404 si el calculo no se ha realizado aun.
    """
    logger.info("GET hosting_capacity | circuit_id=%s", circuit_id)

    r = get_redis()
    require_circuit(circuit_id, r)

    results_raw = r.get(f"hosting_capacity:{circuit_id}:results")
    if not results_raw:
        logger.warning(
            "GET hosting_capacity | circuit_id=%s | sin resultados (no calculado)", circuit_id
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "HOSTING_CAPACITY_NOT_CALCULATED",
                "message": "No existe un calculo de hosting capacity para este circuito.",
                "suggestion": (
                    f"Ejecute POST /api/v1/circuit/{circuit_id}/hosting-capacity "
                    f"para iniciar el calculo."
                ),
            },
        )

    results: List[dict] = json.loads(results_raw)
    calculated_at = (
        r.get(f"hosting_capacity:{circuit_id}:calculated_at") or ""
    )

    pivot: dict = {}
    for entry in results:
        if entry.get("max_gd_kw") is not None:
            bus = entry["bus"]
            phase = str(entry["phase"])
            pivot.setdefault(bus, {})[phase] = entry["max_gd_kw"]

    valid_kws = [e["max_gd_kw"] for e in results if e.get("max_gd_kw") is not None]
    summary: dict = {"total_combinations": len(results)}
    if valid_kws:
        summary.update(
            {
                "max_hosting_kw": max(valid_kws),
                "min_hosting_kw": min(valid_kws),
                "avg_hosting_kw": round(sum(valid_kws) / len(valid_kws), 2),
                "most_constrained_bus": _bus_with_min(results),
                "least_constrained_bus": _bus_with_max(results),
            }
        )

    logger.info(
        "GET hosting_capacity OK | circuit_id=%s | combinaciones=%d | validas=%d | max_kw=%s",
        circuit_id, len(results), len(valid_kws),
        round(max(valid_kws), 1) if valid_kws else "N/A",
    )

    return {
        "circuit_id": circuit_id,
        "calculated_at": calculated_at,
        "results": results,
        "pivot": pivot,
        "summary": summary,
    }


@router.get("/{circuit_id}/hosting-capacity/{bus}")
def get_hosting_capacity_bus(circuit_id: str, bus: str):
    """
    Retorna el hosting capacity para una barra especifica, con detalle por fase.
    """
    logger.info("GET hosting_capacity bus | circuit_id=%s | bus=%s", circuit_id, bus)

    r = get_redis()
    require_circuit(circuit_id, r)

    results_raw = r.get(f"hosting_capacity:{circuit_id}:results")
    if not results_raw:
        logger.warning(
            "GET hosting_capacity bus | circuit_id=%s | bus=%s | sin resultados", circuit_id, bus
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "HOSTING_CAPACITY_NOT_CALCULATED",
                "message": "No existe un calculo de hosting capacity para este circuito.",
            },
        )

    results: List[dict] = json.loads(results_raw)
    bus_results = [r_item for r_item in results if r_item["bus"] == bus]

    if not bus_results:
        logger.warning(
            "GET hosting_capacity bus | circuit_id=%s | bus=%s NOT FOUND en resultados", circuit_id, bus
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "BUS_NOT_FOUND",
                "message": f"No hay resultados de hosting capacity para la barra '{bus}'.",
            },
        )

    phases = [
        {
            "phase": entry["phase"],
            "max_gd_kw": entry.get("max_gd_kw"),
            "limiting_constraint": entry.get("limiting_constraint"),
        }
        for entry in bus_results
    ]

    logger.info(
        "GET hosting_capacity bus OK | circuit_id=%s | bus=%s | fases=%d",
        circuit_id, bus, len(phases),
    )

    return {
        "circuit_id": circuit_id,
        "bus": bus,
        "phases": phases,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bus_with_min(results: List[dict]) -> Optional[str]:
    valid = [e for e in results if e.get("max_gd_kw") is not None]
    if not valid:
        return None
    return min(valid, key=lambda e: e["max_gd_kw"])["bus"]


def _bus_with_max(results: List[dict]) -> Optional[str]:
    valid = [e for e in results if e.get("max_gd_kw") is not None]
    if not valid:
        return None
    return max(valid, key=lambda e: e["max_gd_kw"])["bus"]
