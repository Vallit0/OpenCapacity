"""
Grupo 6 — Exportacion.

GET /{circuit_id}/export/excel  Exporta resultados a Excel (.xlsx).
GET /{circuit_id}/export/json   Exporta todos los resultados a JSON.
"""
from __future__ import annotations

import datetime
import io
import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.dependencies import get_redis, require_circuit
from app.core.dss_engine import DSSEngine, DSSEngineError

router = APIRouter()


@router.get("/{circuit_id}/export/excel")
def export_excel(
    circuit_id: str,
    include_voltage_profile: bool = Query(True),
    include_losses: bool = Query(True),
    include_hosting_capacity: bool = Query(True),
    include_violations: bool = Query(True),
    simulation_id: str = Query(None),
):
    """
    Exporta los resultados disponibles a un archivo Excel con multiples hojas.
    Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
    """
    try:
        import openpyxl
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="openpyxl no esta instalado. Agregue 'openpyxl' a requirements.txt.",
        )

    r = get_redis()
    circuit_data = require_circuit(circuit_id, r)

    info_raw = r.get(f"circuit:{circuit_id}:info")
    circuit_info = json.loads(info_raw) if info_raw else {}
    circuit_name = circuit_info.get("name", circuit_id)

    try:
        engine = DSSEngine()
        engine.load_circuit(
            circuit_data["dss_content"], circuit_data["linecodes_content"]
        )
        voltage_profile = engine.get_voltage_profile() if include_voltage_profile else []
        elements, losses_summary = engine.get_losses() if include_losses else ([], {})
    except DSSEngineError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    wb = openpyxl.Workbook()

    # --- Hoja: Circuito ---
    ws_circuit = wb.active
    ws_circuit.title = "Circuito"
    ws_circuit.append(["Campo", "Valor"])
    for k, v in circuit_info.items():
        ws_circuit.append([k, v])

    # --- Hoja: Voltajes_Base ---
    if include_voltage_profile and voltage_profile:
        ws_v = wb.create_sheet("Voltajes_Base")
        ws_v.append(["Bus_Fase", "Voltaje PU", "En rango (0.95-1.05)"])
        for row in voltage_profile:
            ws_v.append([row["bus_phase"], row["voltage_pu"], row["in_range"]])

    # --- Hoja: Perdidas_Base ---
    if include_losses and elements:
        ws_l = wb.create_sheet("Perdidas_Base")
        ws_l.append(["Tipo", "Elemento", "kW Perdida", "kvar Perdida", "% Potencia"])
        for el in elements:
            ws_l.append(
                [el["type"], el["element"], el["losses_kw"], el["losses_kvar"], el["losses_pct"]]
            )

    # --- Hoja: Hosting_Capacity ---
    if include_hosting_capacity:
        results_raw = r.get(f"hosting_capacity:{circuit_id}:results")
        if results_raw:
            results = json.loads(results_raw)
            ws_hc = wb.create_sheet("Hosting_Capacity")
            ws_hc.append(["Barra", "Fase", "Max GD sin violacion (kW)", "Restriccion limitante"])
            for entry in results:
                ws_hc.append(
                    [
                        entry["bus"],
                        entry["phase"],
                        entry.get("max_gd_kw"),
                        entry.get("limiting_constraint"),
                    ]
                )

    # Serializar a bytes
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"hosting_capacity_{circuit_name}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{circuit_id}/export/json")
def export_json(circuit_id: str):
    """
    Exporta todos los resultados disponibles del circuito en formato JSON.
    """
    r = get_redis()
    circuit_data = require_circuit(circuit_id, r)

    info_raw = r.get(f"circuit:{circuit_id}:info")
    circuit_info = json.loads(info_raw) if info_raw else {}

    try:
        engine = DSSEngine()
        engine.load_circuit(
            circuit_data["dss_content"], circuit_data["linecodes_content"]
        )
        voltage_profile = engine.get_voltage_profile()
        elements, losses_summary = engine.get_losses()
    except DSSEngineError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    results_raw = r.get(f"hosting_capacity:{circuit_id}:results")
    hosting_capacity = json.loads(results_raw) if results_raw else None

    exported_at = datetime.datetime.utcnow().isoformat() + "Z"

    payload = {
        "circuit_id": circuit_id,
        "exported_at": exported_at,
        "circuit_info": circuit_info,
        "voltage_profile": voltage_profile,
        "losses": {
            "summary": losses_summary,
            "elements": elements,
        },
        "hosting_capacity": hosting_capacity,
    }

    return JSONResponse(content=payload)
