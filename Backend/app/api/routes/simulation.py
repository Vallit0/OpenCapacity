"""
Grupo 3 — Simulacion con GD.

POST /{circuit_id}/simulate  Aplica una GD al circuito y retorna analisis comparativo.
"""
from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, HTTPException

from app.api.dependencies import get_redis, require_circuit
from app.core.dss_engine import (
    CircuitDidNotConvergeError,
    DSSEngine,
    DSSEngineError,
)
from app.models.schemas import SimulateGDRequest

router = APIRouter()


@router.post("/{circuit_id}/simulate")
def simulate_gd(circuit_id: str, body: SimulateGDRequest):
    """
    Aplica una GD al circuito y retorna el analisis comparativo completo:
    comparacion de voltajes antes/despues, variacion de perdidas y violaciones.

    Sincronica — tipicamente 400ms-2s.
    """
    r = get_redis()
    circuit_data = require_circuit(circuit_id, r)

    import json
    buses_phases_raw = r.get(f"circuit:{circuit_id}:buses_phases")
    buses_phases: dict[str, List[int]] = (
        json.loads(buses_phases_raw) if buses_phases_raw else {}
    )

    # Validar que la barra existe en el circuito
    if buses_phases and body.bus not in buses_phases:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "BUS_NOT_FOUND",
                "message": f"La barra '{body.bus}' no existe en el circuito.",
                "available_buses": list(buses_phases.keys()),
            },
        )

    # Validar compatibilidad de fases
    if buses_phases:
        available = buses_phases.get(body.bus, [])
        requested = set(body.phases)
        if not requested.issubset(set(available)):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "PHASE_INCOMPATIBILITY",
                    "message": (
                        f"La barra '{body.bus}' solo tiene disponibles las "
                        f"fases {available}. No es posible conectar la GD con "
                        f"las fases {sorted(body.phases)}."
                    ),
                    "bus": body.bus,
                    "available_phases": available,
                    "requested_phases": sorted(body.phases),
                },
            )

    try:
        engine = DSSEngine()
        engine.load_circuit(
            circuit_data["dss_content"], circuit_data["linecodes_content"]
        )

        # Estado base
        base_voltages = engine.get_voltage_profile()
        _, base_summary = engine.get_losses()

        # Aplicar GD y resolver
        engine.apply_gd(body.bus, body.phases, body.power_kw, body.power_kvar)

        # Estado con GD
        gd_voltages = engine.get_voltage_profile()
        _, gd_summary = engine.get_losses()
        violations = engine.check_violations()

    except CircuitDidNotConvergeError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "CIRCUIT_DID_NOT_CONVERGE",
                "message": str(exc),
            },
        ) from exc
    except DSSEngineError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Construir comparativo de voltajes
    base_map = {v["bus_phase"]: v for v in base_voltages}
    voltage_comparison = []
    for gd_v in gd_voltages:
        base_v = base_map.get(gd_v["bus_phase"], {})
        base_pu = base_v.get("voltage_pu", 0.0)
        voltage_comparison.append(
            {
                "bus_phase": gd_v["bus_phase"],
                "voltage_base_pu": base_pu,
                "voltage_with_gd_pu": gd_v["voltage_pu"],
                "delta_pu": round(gd_v["voltage_pu"] - base_pu, 6),
                "in_range_base": base_v.get("in_range", True),
                "in_range_with_gd": gd_v["in_range"],
            }
        )

    base_kw = base_summary["total_losses_kw"]
    gd_kw = gd_summary["total_losses_kw"]
    losses_change_pct = (
        round((gd_kw - base_kw) / base_kw * 100, 2) if base_kw else 0.0
    )

    v_viol = violations["voltage"]
    i_viol = violations["current"]
    p_viol = violations["power"]

    simulation_id = f"sim_{uuid.uuid4().hex[:12]}"

    return {
        "circuit_id": circuit_id,
        "simulation_id": simulation_id,
        "input": body.model_dump(),
        "converged": True,
        "voltage_comparison": voltage_comparison,
        "losses": {
            "base_kw": base_kw,
            "with_gd_kw": gd_kw,
            "delta_kw": round(gd_kw - base_kw, 4),
            "base_kvar": base_summary["total_losses_kvar"],
            "with_gd_kvar": gd_summary["total_losses_kvar"],
            "delta_kvar": round(
                gd_summary["total_losses_kvar"] - base_summary["total_losses_kvar"], 4
            ),
        },
        "violations": violations,
        "summary": {
            "has_violations": bool(v_viol or i_viol or p_viol),
            "voltage_violations_count": len(v_viol),
            "current_violations_count": len(i_viol),
            "power_violations_count": len(p_viol),
            "losses_change_pct": losses_change_pct,
        },
    }
