"""
Grupo 2 — Analisis Base.

GET /{circuit_id}/analysis/voltage-profile  Perfil de voltajes PU.
GET /{circuit_id}/analysis/losses           Tabla de perdidas por elemento.
GET /{circuit_id}/analysis/lines            Informacion de lineas.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.dependencies import get_redis, require_circuit
from app.core.dss_engine import DSSEngine, DSSEngineError

router = APIRouter()


def _build_engine(circuit_data: dict) -> DSSEngine:
    """Instancia y carga un DSSEngine desde los datos del circuito en Redis."""
    engine = DSSEngine()
    engine.load_circuit(
        circuit_data["dss_content"], circuit_data["linecodes_content"]
    )
    return engine


@router.get("/{circuit_id}/analysis/voltage-profile")
def get_voltage_profile(
    circuit_id: str,
    phase: Optional[int] = Query(
        None,
        ge=1,
        le=3,
        description="Filtrar por fase (1, 2 o 3). Sin valor = todas las fases.",
    ),
    only_violations: bool = Query(
        False,
        description="Retornar solo barras fuera del rango 0.95-1.05 PU.",
    ),
):
    """
    Perfil de voltajes en por unidad del estado base (sin GD).
    Sincronica — tipicamente 50-400ms.
    """
    r = get_redis()
    circuit_data = require_circuit(circuit_id, r)

    try:
        engine = _build_engine(circuit_data)
        profile = engine.get_voltage_profile()
    except DSSEngineError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Filtros opcionales
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
    """
    Tabla de perdidas del sistema en estado base, desglosada por elemento.
    Sincronica — tipicamente 80-500ms.
    """
    r = get_redis()
    circuit_data = require_circuit(circuit_id, r)

    try:
        engine = _build_engine(circuit_data)
        elements, summary = engine.get_losses()
    except DSSEngineError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "circuit_id": circuit_id,
        "state": "base",
        "summary": summary,
        "elements": elements,
    }


@router.get("/{circuit_id}/analysis/lines")
def get_lines(circuit_id: str):
    """
    Informacion de todas las lineas: fases, limites de corriente y potencia.
    Sincronica — tipicamente 20-100ms.
    """
    r = get_redis()
    circuit_data = require_circuit(circuit_id, r)

    try:
        engine = _build_engine(circuit_data)
        lines = engine.get_lines_info()
    except DSSEngineError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"circuit_id": circuit_id, "lines": lines}
