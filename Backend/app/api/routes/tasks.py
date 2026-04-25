"""
Grupo 5 — Tareas Asincronas.

GET    /tasks/{task_id}/status  Consulta estado y progreso de una tarea.
DELETE /tasks/{task_id}         Cancela una tarea en cola o en ejecucion.
"""
from __future__ import annotations

import datetime

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, status

from app.core.logging_config import get_logger
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)
router = APIRouter()

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

    logger.debug("GET task status | task_id=%s | state=%s (%s)", task_id, celery_state, api_status)

    response: dict = {
        "task_id": task_id,
        "status": api_status,
    }

    if celery_state == "PENDING":
        response["position_in_queue"] = None

    elif celery_state in ("STARTED", "PROGRESS"):
        meta = result.info or {}
        progress_pct = meta.get("progress_pct", 0)
        current_step = meta.get("current_step", "")
        logger.info(
            "TASK running | task_id=%s | progress=%d%% | step=%s",
            task_id, progress_pct, current_step,
        )
        response.update(
            {
                "progress_pct": progress_pct,
                "current_step": current_step,
                "buses_completed": meta.get("buses_completed"),
                "buses_total": meta.get("buses_total"),
                "elapsed_seconds": meta.get("elapsed_seconds"),
                "estimated_remaining_seconds": meta.get("estimated_remaining_seconds"),
            }
        )

    elif celery_state == "SUCCESS":
        task_result = result.result or {}
        circuit_id = task_result.get("circuit_id", "")
        logger.info(
            "TASK completed | task_id=%s | circuit_id=%s",
            task_id, circuit_id,
        )
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
        logger.error(
            "TASK failed | task_id=%s | error=%s",
            task_id, str(exc) if exc else "desconocido",
        )
        response.update(
            {
                "error_code": "ENGINE_ERROR",
                "error_message": str(exc) if exc else "Error desconocido.",
                "failed_at": datetime.datetime.utcnow().isoformat() + "Z",
                "partial_results_available": False,
            }
        )

    elif celery_state == "REVOKED":
        logger.info("TASK cancelled | task_id=%s", task_id)
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
        logger.warning(
            "CANCEL rechazada | task_id=%s | ya finalizo con state=%s", task_id, result.state
        )
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

    logger.info("TASK cancelada | task_id=%s | state_previo=%s", task_id, result.state)

    return {
        "task_id": task_id,
        "status": "cancelled",
        "cancelled_at": cancelled_at,
    }
