"""
Grupo 2 — Analisis Base.

GET /{circuit_id}/analysis/voltage-profile  Perfil de voltajes PU.
GET /{circuit_id}/analysis/losses           Tabla de perdidas por elemento.
GET /{circuit_id}/analysis/lines            Informacion de lineas.

Los datos se pre-computan en el upload y se cachean en Redis.
Estos endpoints son lecturas puras — sin OpenDSS en el path.
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.dependencies import get_redis, require_circuit

router = APIRouter()


@router.get("/{circuit_id}/analysis/voltage-profile")
def get_voltage_profile(
    circuit_id: str,
    phase: Optional[int] = Query(None, ge=1, le=3),
    only_violations: bool = Query(False),
):
    r = get_redis()
    require_circuit(circuit_id, r)

    raw = r.get(f"circuit:{circuit_id}:voltage_profile")
    if not raw:
        raise HTTPException(status_code=404, detail="Datos de voltaje no encontrados. Vuelva a subir el circuito.")

    profile = json.loads(raw)

    if phase is not None:
        profile = [p for p in profile if p["phase"] == phase]
    if only_violations:
        profile = [p for p in profile if not p["in_range"]]

    violations_count = sum(1 for p in profile if not p["in_range"])
    voltages = [p["voltage_pu"] for p in profile]
    summary = (
        {
            "min_voltage_pu": min(voltages),
            "max_voltage_pu": max(voltages),
            "avg_voltage_pu": round(sum(voltages) / len(voltages), 6),
        }
        if voltages
        else {}
    )

    return {
        "circuit_id": circuit_id,
        "state": "base",
        "voltage_profile": profile,
        "limits": {"lower": 0.95, "upper": 1.05},
        "violations_count": violations_count,
        "summary": summary,
    }


@router.get("/{circuit_id}/analysis/losses")
def get_losses(circuit_id: str):
    r = get_redis()
    require_circuit(circuit_id, r)

    raw = r.get(f"circuit:{circuit_id}:losses")
    if not raw:
        raise HTTPException(status_code=404, detail="Datos de perdidas no encontrados. Vuelva a subir el circuito.")

    data = json.loads(raw)
    return {
        "circuit_id": circuit_id,
        "state": "base",
        "summary": data["summary"],
        "elements": data["elements"],
    }


@router.get("/{circuit_id}/analysis/lines")
def get_lines(circuit_id: str):
    r = get_redis()
    require_circuit(circuit_id, r)

    raw = r.get(f"circuit:{circuit_id}:lines")
    if not raw:
        raise HTTPException(status_code=404, detail="Datos de lineas no encontrados. Vuelva a subir el circuito.")

    return {"circuit_id": circuit_id, "lines": json.loads(raw)}
