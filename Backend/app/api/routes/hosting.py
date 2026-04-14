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
from app.models.schemas import HostingCapacityRequest
from app.tasks.hosting_task import calculate_hosting_capacity

router = APIRouter()

# Factor de estimacion: ~9.45 segundos por combinacion barra-fase (hardware medio)
_SECONDS_PER_COMBINATION = 9.45


@router.post("/{circuit_id}/hosting-capacity", status_code=status.HTTP_202_ACCEPTED)
def start_hosting_capacity(circuit_id: str, body: HostingCapacityRequest):
    """
    Inicia el calculo de hosting capacity para todas las barras del circuito.
    La operacion es asincronica: retorna un task_id con 202 Accepted.
    Usar GET /api/v1/tasks/{task_id}/status para monitorear el progreso.

    Tiempo esperado: 3-15 minutos para IEEE 13 Nodos.
    """
    r = get_redis()
    circuit_data = require_circuit(circuit_id, r)

    # Estimar total de combinaciones para el progreso
    buses_phases_raw = r.get(f"circuit:{circuit_id}:buses_phases")
    buses_phases: dict = json.loads(buses_phases_raw) if buses_phases_raw else {}

    target_buses = body.buses or list(buses_phases.keys())
    total_combinations = sum(
        len(buses_phases.get(b, [])) for b in target_buses
    )
    estimated_seconds = int(math.ceil(total_combinations * _SECONDS_PER_COMBINATION))

    # Encolar la tarea Celery
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
    r = get_redis()
    require_circuit(circuit_id, r)

    results_raw = r.get(f"hosting_capacity:{circuit_id}:results")
    if not results_raw:
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

    # Construir pivot: {bus: {phase: max_gd_kw}}
    pivot: dict = {}
    for entry in results:
        if entry.get("max_gd_kw") is not None:
            bus = entry["bus"]
            phase = str(entry["phase"])
            pivot.setdefault(bus, {})[phase] = entry["max_gd_kw"]

    # Resumen estadistico
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
    r = get_redis()
    require_circuit(circuit_id, r)

    results_raw = r.get(f"hosting_capacity:{circuit_id}:results")
    if not results_raw:
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
