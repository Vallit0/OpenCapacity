# Hosting Capacity API — Backend

API REST para el análisis de capacidad de alojamiento de generación distribuida en redes de distribución eléctrica. Construida con **FastAPI**, **Celery**, **Redis** y **PostgreSQL**, containerizada con **Docker**.

---

## Descripción

Este backend expone los cálculos del motor **OpenDSS** como endpoints REST, resolviendo los tres problemas fundamentales de la arquitectura Dash monolítica original:

| Problema original | Solución |
|---|---|
| Estado global del motor (un usuario rompe la sesión del otro) | Cada tarea Celery tiene su propia instancia de `DSSEngine` aislada |
| Búsqueda binaria bloquea el servidor (3-15 min) | Tarea asíncrona Celery con sistema de polling |
| Lógica mezclada con HTML en un solo archivo | Separación en capas: `core/`, `api/routes/`, `tasks/` |

---

## Requisitos

| Herramienta | Versión mínima | Instalación |
|---|---|---|
| Docker | 24.0+ | [docs.docker.com](https://docs.docker.com/get-docker/) |
| Docker Compose | 2.20+ | Incluido con Docker Desktop |
| Python (solo dev local) | 3.11+ | [python.org](https://www.python.org/) |

> En producción y CI/CD solo se necesita Docker. Python local es opcional para ejecutar tests o scripts de migración.

---

## Estructura del proyecto

```
Backend/
├── docker/
│   ├── Dockerfile.api          # Imagen FastAPI (sin OpenDSS)
│   ├── Dockerfile.worker       # Imagen Celery worker (con OpenDSS)
│   └── nginx/
│       └── nginx.conf          # Proxy inverso para producción
│
├── app/
│   ├── main.py                 # Punto de entrada FastAPI + endpoint /health
│   ├── config.py               # Configuración via variables de entorno
│   │
│   ├── api/
│   │   ├── dependencies.py     # Redis, PostgreSQL como dependencias inyectables
│   │   └── routes/
│   │       ├── circuit.py      # POST/GET/DELETE /circuit
│   │       ├── analysis.py     # GET voltage-profile, losses, lines
│   │       ├── simulation.py   # POST /simulate
│   │       ├── hosting.py      # POST/GET /hosting-capacity
│   │       ├── tasks.py        # GET/DELETE /tasks/{id}
│   │       └── export.py       # GET /export/excel, /export/json
│   │
│   ├── core/
│   │   └── dss_engine.py       # Wrapper completo del motor OpenDSS
│   │
│   ├── models/
│   │   ├── schemas.py          # Modelos Pydantic (request/response)
│   │   └── database.py         # Modelos SQLAlchemy (persistencia)
│   │
│   ├── tasks/
│   │   ├── celery_app.py       # Configuración de Celery
│   │   └── hosting_task.py     # Tarea asíncrona de hosting capacity
│   │
│   └── utils/
│       ├── dss_preprocessor.py # Limpieza de archivos DSS
│       └── exporters.py        # Construcción de Excel y JSON
│
├── tests/
│   ├── conftest.py             # Fixtures pytest
│   ├── test_circuit.py
│   ├── test_simulation.py
│   └── test_hosting.py
│
├── docker-compose.yml          # Orquestación desarrollo
├── docker-compose.prod.yml     # Orquestación producción
├── requirements.txt
├── .env.example
└── README.md
```

---

## Levantar el backend (desarrollo)

### Paso 1 — Clonar y configurar variables de entorno

```bash
# Desde la raíz del repositorio
cd Backend/

cp .env.example .env
# Los valores por defecto funcionan para desarrollo local
```

### Paso 2 — Construir las imágenes Docker

La primera build tarda ~5 minutos porque compila `opendssdirect.py` y sus dependencias nativas. Las builds siguientes son casi instantáneas gracias al cache de capas.

```bash
docker-compose build
```

### Paso 3 — Iniciar todos los servicios

```bash
docker-compose up -d
```

Servicios levantados:

| Servicio | URL | Descripción |
|---|---|---|
| API FastAPI | http://localhost:8000 | Servidor principal |
| Docs interactivos | http://localhost:8000/api/v1/docs | Swagger UI |
| ReDoc | http://localhost:8000/api/v1/redoc | Documentación alternativa |
| Flower (Celery) | http://localhost:5555 | Monitor de tareas |
| Redis | localhost:6379 | Broker + cache |
| PostgreSQL | localhost:5432 | Persistencia |

### Paso 4 — Verificar que OpenDSS funciona en el worker

```bash
docker-compose logs worker | grep "OpenDSS OK"
# Esperado: "OpenDSS OK"
```

### Paso 5 — Verificar que la API responde

```bash
curl http://localhost:8000/api/v1/health
```

Respuesta esperada:

```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime_seconds": 12.3,
  "uptime_human": "0:00:12",
  "timestamp": "2026-04-13T20:00:00Z",
  "pid": 1,
  "environment": "development",
  "components": {
    "redis": {
      "status": "ok",
      "latency_ms": 0.42,
      "used_memory_mb": 1.2,
      "maxmemory_mb": 512
    },
    "postgres": {
      "status": "ok",
      "latency_ms": 1.1
    },
    "celery": {
      "status": "ok",
      "active_workers": 1,
      "worker_names": ["celery@worker_1"]
    }
  }
}
```

---

## Usar el endpoint `/health`

El endpoint `/health` está diseñado para monitoreo en producción. Verifica activamente todos los componentes del sistema.

### Campos de la respuesta

| Campo | Tipo | Descripción |
|---|---|---|
| `status` | `"ok"` / `"degraded"` | `"ok"` solo si todos los componentes están saludables |
| `version` | string | Versión de la API |
| `uptime_seconds` | float | Segundos desde el arranque del proceso |
| `uptime_human` | string | Uptime en formato legible (`"1:23:45"`) |
| `timestamp` | ISO 8601 | Momento de la consulta en UTC |
| `pid` | int | PID del proceso (útil para identificar replicas) |
| `environment` | string | `"development"` o `"production"` |
| `components.redis.status` | `"ok"` / `"error"` | Estado de Redis |
| `components.redis.latency_ms` | float | Latencia del PING a Redis |
| `components.postgres.status` | `"ok"` / `"error"` | Estado de PostgreSQL |
| `components.postgres.latency_ms` | float | Latencia del `SELECT 1` |
| `components.celery.status` | `"ok"` / `"no_workers"` / `"error"` | Estado de los workers |
| `components.celery.active_workers` | int | Número de workers activos |

### Usar con un monitor de uptime

```bash
# Ejemplo con curl — retorna código de salida 0 solo si status=ok
curl -sf http://localhost:8000/api/v1/health | python3 -c "
import sys, json
data = json.load(sys.stdin)
sys.exit(0 if data['status'] == 'ok' else 1)
"
```

---

## Construir y ejecutar con Docker

### Construir solo la imagen de la API

```bash
docker build -f docker/Dockerfile.api -t hosting-capacity-api:latest .
```

### Construir solo la imagen del worker

```bash
docker build -f docker/Dockerfile.worker -t hosting-capacity-worker:latest .
```

### Ejecutar la API sin Compose

```bash
docker run -p 8000:8000 \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  -e DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/hosting_capacity \
  -e CELERY_BROKER_URL=redis://host.docker.internal:6379/1 \
  -e CELERY_RESULT_BACKEND=redis://host.docker.internal:6379/2 \
  hosting-capacity-api:latest
```

### Ejecutar el worker sin Compose

```bash
docker run \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  -e CELERY_BROKER_URL=redis://host.docker.internal:6379/1 \
  -e CELERY_RESULT_BACKEND=redis://host.docker.internal:6379/2 \
  hosting-capacity-worker:latest
```

---

## Despliegue en producción

```bash
# 1. Configurar variables de entorno de producción
cp .env.example .env
# Editar .env con valores reales (SECRET_KEY, DATABASE_URL, etc.)

# 2. Construir imágenes
docker-compose -f docker-compose.prod.yml build

# 3. Levantar con 3 workers en paralelo
docker-compose -f docker-compose.prod.yml up -d --scale worker=3

# 4. Ver estado de los workers
docker-compose -f docker-compose.prod.yml exec worker \
  celery -A app.tasks.celery_app inspect active

# 5. Ver cola de tareas pendientes
docker-compose -f docker-compose.prod.yml exec worker \
  celery -A app.tasks.celery_app inspect reserved
```

---

## Resumen de endpoints

| Método | Endpoint | Tipo | Tiempo est. |
|---|---|---|---|
| POST | `/api/v1/circuit/upload` | Sinc. | 300ms-1.5s |
| GET | `/api/v1/circuit/{id}` | Sinc. | 5-30ms |
| DELETE | `/api/v1/circuit/{id}` | Sinc. | 5ms |
| GET | `/api/v1/circuit/{id}/analysis/voltage-profile` | Sinc. | 50-400ms |
| GET | `/api/v1/circuit/{id}/analysis/losses` | Sinc. | 80-500ms |
| GET | `/api/v1/circuit/{id}/analysis/lines` | Sinc. | 20-100ms |
| POST | `/api/v1/circuit/{id}/simulate` | Sinc. | 400ms-2s |
| POST | `/api/v1/circuit/{id}/hosting-capacity` | **Asínc.** | Inmediato (202) |
| GET | `/api/v1/circuit/{id}/hosting-capacity` | Sinc. | 10-50ms |
| GET | `/api/v1/circuit/{id}/hosting-capacity/{bus}` | Sinc. | 10-30ms |
| GET | `/api/v1/tasks/{task_id}/status` | Sinc. | 5-20ms |
| DELETE | `/api/v1/tasks/{task_id}` | Sinc. | 5ms |
| GET | `/api/v1/circuit/{id}/export/excel` | Sinc. | 200ms-1s |
| GET | `/api/v1/circuit/{id}/export/json` | Sinc. | 50-200ms |
| GET | `/api/v1/health` | Sinc. | ~5ms |

La documentación interactiva completa con esquemas de request/response está disponible en http://localhost:8000/api/v1/docs una vez que el servidor está corriendo.

---

## Ejecutar tests

```bash
# Instalar dependencias en un entorno virtual local
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt

# Tests unitarios (sin Redis ni PostgreSQL)
pytest tests/ -m unit -v

# Tests de integración (requieren docker-compose up -d)
pytest tests/ -m integration -v

# Todos los tests
pytest tests/ -v
```

---

## Notas importantes

- **OpenDSS no es thread-safe.** Cada worker Celery debe tener `--concurrency=1`. Para más paralelismo, escalar el número de containers, no la concurrencia interna.
- **No usar Alpine Linux** como imagen base para el worker. Alpine usa `musl libc` y los binarios de `opendssdirect.py` requieren `glibc`.
- El campo `circuit_id` expira en Redis a las 2 horas. Si el cliente recibe un 404 en un endpoint que antes funcionaba, debe subir el archivo DSS de nuevo.
- Las credenciales nunca se loguean ni se exponen en el endpoint `/health` (las URLs se sanean ocultando contraseñas).
