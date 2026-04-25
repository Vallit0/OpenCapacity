"""
Configuracion de Celery.

Principio critico: worker_concurrency=1 SIEMPRE.
OpenDSS no es thread-safe. Cada proceso worker debe tener exactamente una
instancia del motor. Con concurrency=1 y multiples replicas del container
se obtiene paralelismo real sin colisiones entre tareas.
"""
from celery import Celery
from celery.signals import worker_process_init

from app.config import settings

celery_app = Celery(
    "hosting_capacity",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.hosting_task"],
)

celery_app.conf.update(
    # --- Serializacion segura (nunca pickle) --------------------------------
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # --- Timeouts -----------------------------------------------------------
    task_time_limit=settings.CELERY_TASK_TIMEOUT_SECONDS,
    task_soft_time_limit=settings.CELERY_TASK_TIMEOUT_SECONDS - 300,

    # --- Concurrencia -------------------------------------------------------
    # NUNCA cambiar a mas de 1. OpenDSS no es thread-safe.
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,

    # --- Persistencia de resultados -----------------------------------------
    result_expires=86400,  # 24 horas

    # --- Reintentos ---------------------------------------------------------
    task_max_retries=2,
    task_default_retry_delay=30,

    # --- Enrutamiento de tareas ---------------------------------------------
    task_routes={
        "app.tasks.hosting_task.calculate_hosting_capacity": {
            "queue": "hosting_capacity"
        },
        "app.tasks.hosting_task.run_simulation": {
            "queue": "simulation"
        },
    },

    # --- Configuracion de broker y backend ----------------------------------
    broker_connection_retry_on_startup=True,
)


# ---------------------------------------------------------------------------
# Inicializar logging en cada proceso worker al arrancar
# ---------------------------------------------------------------------------

@worker_process_init.connect
def _init_worker_logging(**kwargs):
    """
    Se ejecuta una vez cuando cada proceso worker de Celery arranca.
    Garantiza que el sistema de logging este configurado correctamente
    en el proceso worker (separado del proceso FastAPI).
    """
    from app.core.logging_config import get_logger, setup_logging
    setup_logging(debug=settings.DEBUG)
    logger = get_logger(__name__)
    logger.info(
        "Celery worker proceso iniciado | concurrency=%d | debug=%s",
        settings.CELERY_WORKER_CONCURRENCY, settings.DEBUG,
    )
