"""
Configuracion centralizada via variables de entorno.
Todas las rutas de conexion y parametros operacionales se leen desde el entorno
para garantizar que el mismo codigo corra identico en dev, staging y produccion.
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # -------------------------------------------------------------------------
    # API
    # -------------------------------------------------------------------------
    APP_VERSION: str = "1.0.0"
    APP_TITLE: str = "Hosting Capacity API"
    APP_DESCRIPTION: str = (
        "API REST para analisis de capacidad de alojamiento de "
        "generacion distribuida en redes de distribucion electrica."
    )
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "cambiar_en_produccion"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    DEBUG: bool = False

    # -------------------------------------------------------------------------
    # Base de datos (PostgreSQL)
    # -------------------------------------------------------------------------
    DATABASE_URL: str = (
        "postgresql://postgres:postgres@postgres:5432/hosting_capacity"
    )

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    REDIS_URL: str = "redis://redis:6379/0"

    # -------------------------------------------------------------------------
    # Celery
    # -------------------------------------------------------------------------
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"
    CELERY_TASK_TIMEOUT_SECONDS: int = 3600   # 1 hora para circuitos grandes
    CELERY_WORKER_CONCURRENCY: int = 1        # NUNCA > 1 — OpenDSS no es thread-safe

    # -------------------------------------------------------------------------
    # OpenDSS / circuito
    # -------------------------------------------------------------------------
    # Tiempo de vida del circuito compilado en Redis (2 horas)
    CIRCUIT_TTL_SECONDS: int = 7200
    # Limite absoluto de potencia GD aceptado por la API
    MAX_POWER_KW_LIMIT: float = 10_000_000.0
    # Potencia inicial maxima para la busqueda binaria cuando no se especifica
    DEFAULT_MAX_POWER_KW: float = 1_500_000.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Leer ALLOWED_ORIGINS como lista separada por coma cuando viene del entorno
        # Ejemplo: ALLOWED_ORIGINS="http://a.com,http://b.com"
        env_parse_none_str = "none"

    @property
    def allowed_origins_list(self) -> List[str]:
        """Garantiza que ALLOWED_ORIGINS siempre sea una lista."""
        if isinstance(self.ALLOWED_ORIGINS, str):
            return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]
        return self.ALLOWED_ORIGINS


settings = Settings()
