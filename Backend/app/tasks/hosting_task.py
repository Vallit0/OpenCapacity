"""
Tarea Celery para el calculo de Hosting Capacity.

Corre en el proceso worker (nunca en FastAPI). Tiene su propia instancia de
DSSEngine. Actualiza el estado de la tarea en tiempo real para que el endpoint
GET /tasks/{id}/status pueda informar el progreso al cliente.
"""
from __future__ import annotations

import json
import time
from typing import List, Optional

import redis
from celery import current_task
from celery.exceptions import SoftTimeLimitExceeded

from app.config import settings
from app.core.dss_engine import DSSEngine, CircuitDidNotConvergeError
from app.core.logging_config import get_logger, log_timer
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Tarea principal
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="app.tasks.hosting_task.calculate_hosting_capacity",
    max_retries=2,
    soft_time_limit=settings.CELERY_TASK_TIMEOUT_SECONDS - 300,
    time_limit=settings.CELERY_TASK_TIMEOUT_SECONDS,
)
def calculate_hosting_capacity(
    self,
    circuit_id: str,
    dss_content: str,
    linecodes_content: Optional[str],
    max_power_kw: float,
    check_voltage: bool,
    check_current: bool,
    check_power: bool,
    target_buses: Optional[List[str]],
) -> dict:
    """
    Busqueda binaria completa de hosting capacity para todas las barras
    (o un subconjunto) del circuito.

    Actualiza el estado de la tarea Celery con progreso en tiempo real.
    Guarda resultados parciales en Redis ante SoftTimeLimitExceeded.
    """
    task_id = self.request.id
    logger.info(
        "TASK START calculate_hosting_capacity | task_id=%s | circuit_id=%s | max_kw=%.0f | "
        "check_v=%s check_i=%s check_p=%s",
        task_id, circuit_id, max_power_kw,
        check_voltage, check_current, check_power,
    )

    with log_timer(logger, "cargar_circuito_worker", circuit_id=circuit_id):
        engine = DSSEngine()
        engine.load_circuit(dss_content, linecodes_content)

    barras = target_buses or list(engine._dss.Circuit.AllBusNames())
    results: List[dict] = []
    completed_combinations = 0

    total_combinations = 0
    for bus in barras:
        engine._dss.Circuit.SetActiveBus(bus)
        total_combinations += len(engine._dss.Bus.Nodes())

    logger.info(
        "TASK INFO | task_id=%s | circuit_id=%s | buses=%d | combinaciones_total=%d | est=%.0f min",
        task_id, circuit_id, len(barras), total_combinations,
        total_combinations * 9.45 / 60,
    )

    start_time = time.time()

    for bus_idx, bus in enumerate(barras):
        engine._dss.Circuit.SetActiveBus(bus)
        nodes = sorted(engine._dss.Bus.Nodes())
        kv_ln = engine._dss.Bus.kVBase()

        logger.debug(
            "TASK bus | task_id=%s | circuit_id=%s | bus=%s | fases=%s | kv_base=%.3f",
            task_id, circuit_id, bus, nodes, kv_ln,
        )

        bus_start = time.time()

        for phase in nodes:
            try:
                max_kw = _binary_search(
                    engine=engine,
                    dss_content=dss_content,
                    linecodes_content=linecodes_content,
                    bus=bus,
                    phase=phase,
                    kv_ln=kv_ln,
                    max_power_kw=max_power_kw,
                    check_voltage=check_voltage,
                    check_current=check_current,
                    check_power=check_power,
                )

                limiting = _determine_limiting_constraint(
                    engine=engine,
                    dss_content=dss_content,
                    linecodes_content=linecodes_content,
                    bus=bus,
                    phase=phase,
                    kv_ln=kv_ln,
                    max_kw=max_kw,
                )

                logger.debug(
                    "binary_search OK | task_id=%s | bus=%s | fase=%d | max_gd_kw=%.1f | limiting=%s",
                    task_id, bus, phase, max_kw, limiting,
                )

                results.append(
                    {
                        "bus": bus,
                        "phase": phase,
                        "max_gd_kw": max_kw,
                        "limiting_constraint": limiting,
                    }
                )

            except SoftTimeLimitExceeded:
                logger.warning(
                    "TASK TIMEOUT | task_id=%s | circuit_id=%s | guardando %d resultados parciales",
                    task_id, circuit_id, len(results),
                )
                _save_partial_results(circuit_id, results)
                raise

            except Exception as exc:
                logger.error(
                    "binary_search ERROR | task_id=%s | bus=%s | fase=%d | %s: %s",
                    task_id, bus, phase, type(exc).__name__, exc,
                )
                results.append(
                    {
                        "bus": bus,
                        "phase": phase,
                        "max_gd_kw": None,
                        "limiting_constraint": None,
                        "error": str(exc),
                    }
                )

            completed_combinations += 1
            elapsed = int(time.time() - start_time)
            remaining = _estimate_remaining(
                elapsed, completed_combinations, total_combinations
            )

            current_task.update_state(
                state="PROGRESS",
                meta={
                    "progress_pct": round(
                        completed_combinations / total_combinations * 100
                    ),
                    "current_step": (
                        f"Calculando barra {bus}, fase {phase} "
                        f"({completed_combinations}/{total_combinations})"
                    ),
                    "buses_completed": bus_idx,
                    "buses_total": len(barras),
                    "elapsed_seconds": elapsed,
                    "estimated_remaining_seconds": remaining,
                },
            )

        bus_elapsed_ms = round((time.time() - bus_start) * 1000)
        logger.info(
            "TASK bus DONE | task_id=%s | circuit_id=%s | bus=%s | fases=%d | %.0f ms | "
            "progreso=%d/%d (%.0f%%)",
            task_id, circuit_id, bus, len(nodes), bus_elapsed_ms,
            completed_combinations, total_combinations,
            completed_combinations / total_combinations * 100,
        )

        if bus_idx % 5 == 0 and results:
            _save_partial_results(circuit_id, results)
            logger.debug(
                "TASK checkpoint | task_id=%s | circuit_id=%s | guardados=%d resultados",
                task_id, circuit_id, len(results),
            )

    total_elapsed = round(time.time() - start_time)
    errors = sum(1 for r in results if r.get("error"))

    # Persistir resultados finales en Redis para que el endpoint GET los lea
    calculated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    r_client = redis.from_url(settings.REDIS_URL)
    r_client.setex(
        f"hosting_capacity:{circuit_id}:results",
        settings.CIRCUIT_TTL_SECONDS,
        json.dumps(results),
    )
    r_client.setex(
        f"hosting_capacity:{circuit_id}:calculated_at",
        settings.CIRCUIT_TTL_SECONDS,
        calculated_at,
    )

    logger.info(
        "TASK DONE calculate_hosting_capacity | task_id=%s | circuit_id=%s | "
        "combinaciones=%d | errores=%d | elapsed=%ds | guardado en Redis OK",
        task_id, circuit_id, len(results), errors, total_elapsed,
    )

    return {
        "circuit_id": circuit_id,
        "results": results,
        "total_combinations": len(results),
    }


# ---------------------------------------------------------------------------
# Tarea de simulacion puntual (cola separada, prioridad alta)
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="app.tasks.hosting_task.run_simulation",
    time_limit=120,
)
def run_simulation(
    self,
    circuit_id: str,
    dss_content: str,
    linecodes_content: Optional[str],
    bus: str,
    phases: List[int],
    power_kw: float,
    power_kvar: float,
) -> dict:
    """
    Tarea para simulacion puntual con GD. Se usa cuando la simulacion sincronica
    excede el timeout del worker ASGI (circuitos muy grandes).
    """
    task_id = self.request.id
    logger.info(
        "TASK START run_simulation | task_id=%s | circuit_id=%s | bus=%s | fases=%s | power=%.1f kW",
        task_id, circuit_id, bus, phases, power_kw,
    )

    with log_timer(logger, "run_simulation_dss", circuit_id=circuit_id, bus=bus, power_kw=power_kw):
        engine = DSSEngine()
        engine.load_circuit(dss_content, linecodes_content)

        base_voltages = engine.get_voltage_profile()
        base_elements, base_summary = engine.get_losses()

        engine.apply_gd(bus, phases, power_kw, power_kvar)
        gd_voltages = engine.get_voltage_profile()
        _, gd_summary = engine.get_losses()
        violations = engine.check_violations()

    base_map = {v["bus_phase"]: v for v in base_voltages}
    comparison = []
    for gd_v in gd_voltages:
        base_v = base_map.get(gd_v["bus_phase"], {})
        base_pu = base_v.get("voltage_pu", 0.0)
        comparison.append(
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

    has_violations = bool(
        violations.get("voltage") or violations.get("current") or violations.get("power")
    )

    logger.info(
        "TASK DONE run_simulation | task_id=%s | circuit_id=%s | violations=%s | losses_delta=%.2f%%",
        task_id, circuit_id, has_violations, losses_change_pct,
    )

    return {
        "circuit_id": circuit_id,
        "voltage_comparison": comparison,
        "losses": {
            "base_kw": base_kw,
            "with_gd_kw": gd_kw,
            "delta_kw": round(gd_kw - base_kw, 4),
            "base_kvar": base_summary["total_losses_kvar"],
            "with_gd_kvar": gd_summary["total_losses_kvar"],
            "delta_kvar": round(
                gd_summary["total_losses_kvar"] - base_summary["total_losses_kvar"], 4,
            ),
        },
        "violations": violations,
        "losses_change_pct": losses_change_pct,
    }


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------


def _binary_search(
    engine: DSSEngine,
    dss_content: str,
    linecodes_content: Optional[str],
    bus: str,
    phase: int,
    kv_ln: float,
    max_power_kw: float,
    check_voltage: bool,
    check_current: bool,
    check_power: bool,
) -> float:
    """
    Busqueda binaria del maximo kW sin violaciones para una combinacion
    barra-fase. Siempre reinicia el circuito antes de cada prueba.
    """
    low = 0
    high = int(max_power_kw)
    best_kw = 0.0

    while low <= high:
        mid = (low + high) // 2
        engine.reset_circuit(dss_content, linecodes_content)
        engine._dss.Text.Command(
            f"New Generator.GD Bus1={bus}.{phase} Phases=1 "
            f"kV={kv_ln:.3f} kW={mid} kvar=0 Model=1"
        )
        engine._dss.Text.Command("Solve")

        if not engine._dss.Solution.Converged():
            high = mid - 1
            continue

        violations = engine.check_violations()
        has_violation = (
            (check_voltage and len(violations["voltage"]) > 0)
            or (check_current and len(violations["current"]) > 0)
            or (check_power and len(violations["power"]) > 0)
        )

        if not has_violation:
            best_kw = float(mid)
            low = mid + 1
        else:
            high = mid - 1

    return best_kw


def _determine_limiting_constraint(
    engine: DSSEngine,
    dss_content: str,
    linecodes_content: Optional[str],
    bus: str,
    phase: int,
    kv_ln: float,
    max_kw: float,
) -> str:
    """
    Determina cual restriccion fue la limitante probando con max_kw + 1 kW.
    """
    test_kw = max_kw + 1
    engine.reset_circuit(dss_content, linecodes_content)
    engine._dss.Text.Command(
        f"New Generator.GD Bus1={bus}.{phase} Phases=1 "
        f"kV={kv_ln:.3f} kW={test_kw} kvar=0 Model=1"
    )
    engine._dss.Text.Command("Solve")

    if not engine._dss.Solution.Converged():
        return "convergence"

    violations = engine.check_violations()
    if violations["voltage"]:
        return "voltage"
    if violations["current"]:
        return "current"
    if violations["power"]:
        return "power"
    return "none"


def _estimate_remaining(elapsed: int, done: int, total: int) -> int:
    """Estima segundos restantes basado en velocidad actual."""
    if done == 0:
        return 0
    rate = elapsed / done
    return int(rate * (total - done))


def _save_partial_results(circuit_id: str, results: list) -> None:
    """Guarda resultados parciales en Redis. Usado ante timeout o checkpointing."""
    r = redis.from_url(settings.REDIS_URL)
    r.setex(
        f"partial_results:{circuit_id}",
        3600,
        json.dumps(results),
    )
    logger.debug("partial_results guardados | circuit_id=%s | n=%d", circuit_id, len(results))
