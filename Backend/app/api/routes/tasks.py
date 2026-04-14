"""
Grupo 5 — Tareas Asincronas.

GET    /tasks/{task_id}/status  Consulta estado y progreso de una tarea.
DELETE /tasks/{task_id}         Cancela una tarea en cola o en ejecucion.
"""
from __future__ import annotations

import datetime

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, status

from app.tasks.celery_app import celery_app

router = APIRouter()

# Mapeo de estados internos de Celery a los estados del contrato REST
_CELERY_TO_API_STATUS = {
    "PENDING": "queued",
    "RECEIVED": "queued",
    "STARTED": "running",
    "PROGRESS": "running",
    "SUCCESS": "completed",
    "FAILURE": "failed",
    "REVOKED": "cancelled",
    "RETRY": "running",
}


@router.get("/{task_id}/status")
def get_task_status(task_id: str):
    """
    Consulta el estado de una tarea en ejecucion o completada.
    Devuelve progreso detallado cuando la tarea esta corriendo.
    """
    result: AsyncResult = AsyncResult(task_id, app=celery_app)
    celery_state = result.state
    api_status = _CELERY_TO_API_STATUS.get(celery_state, "queued")

    response: dict = {
        "task_id": task_id,
        "status": api_status,
    }

    if celery_state == "PENDING":
        response["position_in_queue"] = None  # Celery no expone la posicion directamente

    elif celery_state in ("STARTED", "PROGRESS"):
        meta = result.info or {}
        response.update(
            {
                "progress_pct": meta.get("progress_pct", 0),
                "current_step": meta.get("current_step", ""),
                "buses_completed": meta.get("buses_completed"),
                "buses_total": meta.get("buses_total"),
                "elapsed_seconds": meta.get("elapsed_seconds"),
                "estimated_remaining_seconds": meta.get("estimated_remaining_seconds"),
            }
        )

    elif celery_state == "SUCCESS":
        task_result = result.result or {}
        circuit_id = task_result.get("circuit_id", "")
        response.update(
            {
                "progress_pct": 100,
                "result_url": (
                    f"/api/v1/circuit/{circuit_id}/hosting-capacity"
                    if circuit_id
                    else None
                ),
                "completed_at": datetime.datetime.utcnow().isoformat() + "Z",
            }
        )

    elif celery_state == "FAILURE":
        exc = result.result
        response.update(
            {
                "error_code": "ENGINE_ERROR",
                "error_message": str(exc) if exc else "Error desconocido.",
                "failed_at": datetime.datetime.utcnow().isoformat() + "Z",
                "partial_results_available": False,
            }
        )

    elif celery_state == "REVOKED":
        response["cancelled_at"] = datetime.datetime.utcnow().isoformat() + "Z"

    return response


@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
def cancel_task(task_id: str):
    """
    Cancela una tarea en cola o en ejecucion.
    Usa SIGTERM para terminar el worker de forma limpia.
    """
    result: AsyncResult = AsyncResult(task_id, app=celery_app)

    if result.state in ("SUCCESS", "FAILURE"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "TASK_ALREADY_FINISHED",
                "message": (
                    f"La tarea ya finalizo con estado '{result.state}'. "
                    "No se puede cancelar."
                ),
            },
        )

    result.revoke(terminate=True, signal="SIGTERM")
    cancelled_at = datetime.datetime.utcnow().isoformat() + "Z"

    return {
        "task_id": task_id,
        "status": "cancelled",
        "cancelled_at": cancelled_at,
    }
