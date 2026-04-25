"""
Sistema de logging centralizado para toda la aplicacion.

- Desarrollo (DEBUG=True):  salida coloreada en consola + archivo rotativo
- Produccion (DEBUG=False): JSON estructurado en consola + archivo rotativo

Uso en cualquier modulo:
    from app.core.logging_config import get_logger, log_timer
    logger = get_logger(__name__)

    logger.info("operacion completada | circuit_id=%s", cid)

    with log_timer(logger, "compilar_dss", circuit_id=cid):
        engine.load_circuit(...)
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

# Operaciones que superen este umbral reciben nivel WARNING en log_timer
SLOW_THRESHOLD_MS: int = 2_000

_LOG_DIR = Path("/app/logs")

# Campos internos de LogRecord que no deben repetirse en el JSON de salida
_INTERNAL_KEYS = frozenset({
    "args", "created", "exc_info", "exc_text", "filename", "funcName",
    "levelname", "levelno", "lineno", "message", "module", "msecs",
    "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "taskName", "thread", "threadName",
})


# ---------------------------------------------------------------------------
# Formateadores
# ---------------------------------------------------------------------------


class _JSONFormatter(logging.Formatter):
    """
    Formateador JSON para produccion.
    Produce una linea JSON por evento, compatible con Loki / Datadog / ELK.
    """

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        payload: dict = {
            "ts":      datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level":   record.levelname,
            "logger":  record.name,
            "msg":     record.message,
            "loc":     f"{record.module}.{record.funcName}:{record.lineno}",
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Adjuntar campos extra inyectados via extra={...}
        for key, val in record.__dict__.items():
            if key not in _INTERNAL_KEYS:
                payload[key] = val
        return json.dumps(payload, default=str, ensure_ascii=False)


class _ColoredFormatter(logging.Formatter):
    """
    Formateador con colores ANSI para desarrollo.
    Produce lineas legibles: hora  NIVEL  logger  mensaje
    """

    _COLORS = {
        logging.DEBUG:    "\x1b[38;5;242m",  # gris
        logging.INFO:     "\x1b[32m",         # verde
        logging.WARNING:  "\x1b[33m",         # amarillo
        logging.ERROR:    "\x1b[31m",         # rojo
        logging.CRITICAL: "\x1b[31;1m",       # rojo negrita
    }
    _RESET = "\x1b[0m"
    _CYAN  = "\x1b[36m"
    _GREY  = "\x1b[38;5;242m"

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelno, "")
        fmt = (
            f"{self._GREY}%(asctime)s{self._RESET} "
            f"{color}%(levelname)-8s{self._RESET} "
            f"{self._CYAN}%(name)-38s{self._RESET} "
            f"%(message)s"
        )
        return logging.Formatter(fmt, datefmt="%H:%M:%S").format(record)


# ---------------------------------------------------------------------------
# Configuracion global
# ---------------------------------------------------------------------------


def setup_logging(debug: bool = False) -> None:
    """
    Configura el sistema de logging global. Llamar UNA sola vez al arrancar
    el proceso (main.py para FastAPI, celery_app.py para workers Celery).

    - debug=True : logs coloreados en consola, nivel DEBUG.
    - debug=False: logs JSON en consola, nivel INFO.
    En ambos casos escribe tambien en /app/logs/app.log (JSON, rotacion diaria).
    """
    root = logging.getLogger()

    # Evitar agregar handlers duplicados si se llama mas de una vez
    if root.handlers:
        return

    root.setLevel(logging.DEBUG if debug else logging.INFO)

    # Silenciar librerias ruidosas que no aportan valor operacional
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
    logging.getLogger("celery.app.trace").setLevel(logging.WARNING)
    logging.getLogger("kombu").setLevel(logging.WARNING)

    formatter_console = _ColoredFormatter() if debug else _JSONFormatter()

    # Handler de consola (stdout para compatibilidad con Docker logs)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if debug else logging.INFO)
    console.setFormatter(formatter_console)
    root.addHandler(console)

    # Handler de archivo — rotacion diaria, 30 dias, siempre JSON
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=_LOG_DIR / "app.log",
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(_JSONFormatter())
        root.addHandler(file_handler)
    except (PermissionError, OSError):
        logging.getLogger(__name__).warning(
            "No se pudo crear archivo de log en %s — solo consola activa.", _LOG_DIR
        )


def get_logger(name: str) -> logging.Logger:
    """
    Retorna un logger nombrado.
    Llamar a nivel de modulo: logger = get_logger(__name__)
    """
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# Utilidad de temporizacion
# ---------------------------------------------------------------------------


@contextmanager
def log_timer(
    logger: logging.Logger,
    operation: str,
    **context: object,
) -> Generator[None, None, None]:
    """
    Context manager que mide y loggea el tiempo de ejecucion de un bloque.

    - Si el bloque tarda mas de SLOW_THRESHOLD_MS: log WARNING con [SLOW].
    - Si el bloque lanza una excepcion: log ERROR con el tipo y mensaje.

    Ejemplo:
        with log_timer(logger, "compilar_dss", circuit_id=cid, archivo=fname):
            engine.load_circuit(dss_content)
    """
    ctx = "  ".join(f"{k}={v}" for k, v in context.items()) if context else ""
    logger.info("START %s | %s", operation, ctx)
    t0 = time.perf_counter()
    try:
        yield
        ms = round((time.perf_counter() - t0) * 1000, 1)
        if ms > SLOW_THRESHOLD_MS:
            logger.warning("DONE %s | %.0f ms [SLOW] | %s", operation, ms, ctx)
        else:
            logger.info("DONE %s | %.0f ms | %s", operation, ms, ctx)
    except Exception as exc:
        ms = round((time.perf_counter() - t0) * 1000, 1)
        logger.error(
            "FAIL %s | %.0f ms | %s: %s | %s",
            operation, ms, type(exc).__name__, exc, ctx,
        )
        raise
