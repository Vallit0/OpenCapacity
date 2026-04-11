# Road to Backend — Migracion a FastAPI + Docker

Guia de migracion completa del sistema de analisis de Hosting Capacity desde la aplicacion Dash monolitica hacia una arquitectura backend REST desacoplada, containerizada y lista para produccion.

---

## Tabla de Contenidos

1. [Decision de Arquitectura](#1-decision-de-arquitectura)
2. [Por que Docker es obligatorio](#2-por-que-docker-es-obligatorio)
3. [Stack Tecnologico](#3-stack-tecnologico)
4. [Estimaciones de Tiempo por Request](#4-estimaciones-de-tiempo-por-request)
5. [Estructura del Proyecto Backend](#5-estructura-del-proyecto-backend)
6. [Catalogo Completo de Endpoints](#6-catalogo-completo-de-endpoints)
7. [Fase 1 — Configuracion del Entorno Docker](#7-fase-1--configuracion-del-entorno-docker)
8. [Fase 2 — Nucleo del Motor OpenDSS](#8-fase-2--nucleo-del-motor-opendss)
9. [Fase 3 — Cola de Tareas con Celery y Redis](#9-fase-3--cola-de-tareas-con-celery-y-redis)
10. [Fase 4 — API REST con FastAPI](#10-fase-4--api-rest-con-fastapi)
11. [Fase 5 — Persistencia con PostgreSQL](#11-fase-5--persistencia-con-postgresql)
12. [Fase 6 — Despliegue en Produccion](#12-fase-6--despliegue-en-produccion)
13. [Errores Conocidos y Como Manejarlos](#13-errores-conocidos-y-como-manejarlos)
14. [Guia de Migracion del Codigo Existente](#14-guia-de-migracion-del-codigo-existente)

---

## 1. Decision de Arquitectura

### El problema con la arquitectura actual

La aplicacion `Simulacion_DASH_VFinal.py` es funcional para uso local de un solo usuario, pero tiene tres problemas fundamentales que la hacen inviable en web:

**Problema 1 — Estado global del motor OpenDSS**

```python
# Estado global en Simulacion_DASH_VFinal.py (lineas 9-12)
engine = dss.DSS
engine.Start(0)
text = engine.Text
circuit = engine.ActiveCircuit
```

El motor OpenDSS vive como variable global del proceso. Si dos usuarios mandan requests simultaneos, ambos modifican el mismo circuito en memoria. El resultado es corrupcion de datos o crashes silenciosos.

**Problema 2 — La busqueda binaria bloquea el servidor**

La busqueda binaria que corre al arrancar la aplicacion puede tomar entre 3 y 15 minutos. Dash corre sobre Flask con un solo hilo por defecto. Durante ese tiempo, ninguna otra request puede ser atendida.

**Problema 3 — Sin separacion de responsabilidades**

El HTML, los callbacks, la logica de simulacion, el calculo de perdidas y la busqueda binaria estan todos en un solo archivo de 600 lineas. Cualquier cambio en la interfaz puede romper la logica de calculo.

### La arquitectura objetivo

```
┌─────────────────────────────────────────────────────────────────┐
│                        INTERNET / CLIENTE                        │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTPS
┌─────────────────────────────▼───────────────────────────────────┐
│                         NGINX (reverse proxy)                    │
│                    Termina SSL, balancea carga                   │
└──────────┬──────────────────────────────────┬───────────────────┘
           │ /api/*                            │ /*
┌──────────▼──────────┐             ┌──────────▼──────────────────┐
│    FastAPI (Python) │             │   Frontend (React / Next.js) │
│    Uvicorn ASGI     │             │   Plotly.js, Recharts         │
│    Puerto 8000      │             │   Puerto 3000 / estatico      │
└──────────┬──────────┘             └─────────────────────────────┘
           │
     ┌─────┴──────────────────────┐
     │                            │
┌────▼────────┐          ┌────────▼────────┐
│    Redis    │          │   PostgreSQL     │
│  (broker    │          │  (resultados,    │
│  + cache)   │          │   historial)     │
└────┬────────┘          └─────────────────┘
     │
┌────▼────────────────────────────────────┐
│           Celery Workers (N instancias)  │
│                                          │
│  Worker 1: su propia instancia OpenDSS   │
│  Worker 2: su propia instancia OpenDSS   │
│  Worker N: su propia instancia OpenDSS   │
└──────────────────────────────────────────┘
```

Cada componente vive en su propio container Docker. El motor OpenDSS solo existe dentro de los workers de Celery, jamas en el proceso de FastAPI. Cada worker tiene su propia instancia aislada.

---

## 2. Por que Docker es Obligatorio

### El problema de OpenDSS en produccion

`opendssdirect.py` es un wrapper Python que viene con binarios nativos compilados (`.so` en Linux, `.dylib` en macOS). Estos binarios tienen dependencias especificas del sistema operativo:

- `libgomp` (OpenMP runtime)
- `libstdc++`
- `libgcc_s`
- En algunas versiones: `libklu` (biblioteca de algebra lineal)

En un servidor limpio de produccion (Ubuntu 22.04 minimal, por ejemplo), estas dependencias pueden no estar instaladas. El error tipico es:

```
ImportError: libgomp.so.1: cannot open shared object file: No such file or directory
```

O peor, el import funciona pero el motor falla silenciosamente al resolver el circuito.

### Docker garantiza reproducibilidad

Con Docker se define exactamente el sistema operativo base, todas las dependencias del sistema y la version de Python de una sola vez. Luego ese mismo entorno corre identico en:

- MacBook del desarrollador
- Servidor de staging
- Servidor de produccion
- CI/CD pipeline

### Compatibilidad comprobada de opendssdirect.py

| Sistema Operativo | Arquitectura | Soporte |
|---|---|---|
| Ubuntu 20.04 / 22.04 | x86_64 | Completo |
| Debian 11 / 12 | x86_64 | Completo |
| macOS 12+ | arm64 (M1/M2) | Completo |
| macOS 12+ | x86_64 | Completo |
| Windows 10/11 | x86_64 | Completo |
| Alpine Linux | x86_64 | Problematico (ver seccion de errores) |

**Conclusion:** usar `python:3.11-slim-bookworm` (Debian 12 slim) como imagen base. Es la combinacion con menos problemas reportados para `opendssdirect.py`.

---

## 3. Stack Tecnologico

### Backend

| Componente | Tecnologia | Version | Razon |
|---|---|---|---|
| Framework API | FastAPI | 0.111+ | Asincrono nativo, tipado con Pydantic, OpenAPI automatico |
| Servidor ASGI | Uvicorn | 0.29+ | Servidor de produccion para FastAPI |
| Motor simulacion | opendssdirect.py | 0.8+ | Unica alternativa Python cross-platform para OpenDSS |
| Cola de tareas | Celery | 5.3+ | Estandar de la industria para Python, integra con Redis |
| Broker + Cache | Redis | 7.0+ | Rapido, simple, excelente soporte en Celery |
| Base de datos | PostgreSQL | 15+ | Para historial de simulaciones y resultados cacheados |
| ORM | SQLAlchemy | 2.0+ | Asincrono nativo, compatible con FastAPI |
| Validacion | Pydantic | 2.0+ | Incluido con FastAPI, validacion automatica de JSON |
| Proxy inverso | Nginx | 1.24+ | Terminar SSL, balancea carga, sirve archivos estaticos |

### Infraestructura

| Componente | Tecnologia | Razon |
|---|---|---|
| Containerizacion | Docker + Docker Compose | Reproducibilidad, aislamiento de OpenDSS |
| Orquestacion (prod) | Docker Swarm o Kubernetes | Escalar workers de Celery segun demanda |
| CI/CD | GitHub Actions | Automatizar build, test y deploy |

---

## 4. Estimaciones de Tiempo por Request

Esta seccion es critica para disenar correctamente cuales endpoints son sincronicos y cuales deben ser asincronicos.

### Base de calculo

Las mediciones se basan en el comportamiento observado del motor OpenDSS en el codigo existente:

- **Tiempo por `text.Command = "Solve"`:** 80-200ms en hardware moderno (depende de la complejidad del circuito)
- **Tiempo de reinicio del circuito (`Clear` + `Compile` + `Solve`):** 200-400ms
- **Iteraciones de busqueda binaria por barra-fase:** `log2(1,500,000) ≈ 21` iteraciones
- **Combinaciones barra-fase en IEEE 13 Nodos:** aproximadamente 35

### Tabla de tiempos estimados por endpoint

| Operacion | Tiempo Minimo | Tiempo Tipico | Tiempo Maximo | Tipo |
|---|---|---|---|---|
| `POST /circuit/upload` (solo compilar) | 300ms | 600ms | 1.5s | Sincronica |
| `GET /circuit/{id}/info` | 5ms | 10ms | 30ms | Sincronica |
| `GET /circuit/{id}/voltage-profile` | 50ms | 150ms | 400ms | Sincronica |
| `GET /circuit/{id}/losses` | 80ms | 200ms | 500ms | Sincronica |
| `POST /circuit/{id}/simulate` (1 GD) | 400ms | 800ms | 2s | Sincronica |
| `POST /circuit/{id}/hosting-capacity` (IEEE 13) | 3min | 7min | 15min | **Asincronica** |
| `GET /tasks/{id}/status` | 5ms | 10ms | 20ms | Sincronica |

### Desglose del calculo de Hosting Capacity

```
Para IEEE 13 Nodos (35 combinaciones barra-fase):

Por cada combinacion barra-fase:
  21 iteraciones binarias x (300ms reinicio + 100ms solve + 50ms verificacion)
  = 21 x 450ms = 9.45 segundos por barra-fase

Total: 35 combinaciones x 9.45s = 330 segundos ≈ 5.5 minutos (servidor de gama media)

Con hardware de produccion (4 cores, RAM suficiente):
  - Tiempo de solve baja a ~50ms
  - Total: 35 x 21 x (200ms + 50ms) = 183 segundos ≈ 3 minutos

Con hardware limitado (1 core, VPS basico):
  - Tiempo de solve puede subir a 300ms
  - Total: 35 x 21 x (400ms + 300ms) = 514 segundos ≈ 8.5 minutos
```

**Consecuencia directa de estas estimaciones:**

1. Cualquier endpoint que ejecute busqueda binaria **debe ser asincrono** con respuesta 202 y sistema de polling.
2. Los endpoints de consulta de voltajes, perdidas y simulacion puntual pueden ser sincronicos.
3. El endpoint de upload debe tener un timeout generoso (minimo 30 segundos) para circuitos complejos.

### Comparacion por tamano de circuito

| Circuito | Buses | Combinaciones barra-fase | Tiempo estimado |
|---|---|---|---|
| IEEE 13 Nodos (actual) | 16 | ~35 | 3-8 minutos |
| IEEE 34 Nodos | 34 | ~80 | 8-20 minutos |
| IEEE 123 Nodos | 123 | ~280 | 30-70 minutos |
| Circuito real (1000+ nodos) | 1000+ | 2000+ | Horas |

Para circuitos grandes se deberia implementar paralelizacion de la busqueda binaria usando multiples workers Celery en paralelo, dividiendo las barras entre workers.

---

## 5. Estructura del Proyecto Backend

```
hosting-capacity-backend/
│
├── docker/
│   ├── Dockerfile.api          # Imagen para FastAPI
│   ├── Dockerfile.worker       # Imagen para Celery workers
│   └── nginx/
│       └── nginx.conf          # Configuracion del proxy inverso
│
├── app/
│   ├── __init__.py
│   ├── main.py                 # Punto de entrada FastAPI
│   ├── config.py               # Configuracion via variables de entorno
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── circuit.py      # Endpoints de gestion de circuito
│   │   │   ├── analysis.py     # Endpoints de analisis (voltaje, perdidas)
│   │   │   ├── simulation.py   # Endpoints de simulacion con GD
│   │   │   ├── hosting.py      # Endpoints de hosting capacity
│   │   │   ├── tasks.py        # Endpoints de monitoreo de tareas
│   │   │   └── export.py       # Endpoints de exportacion
│   │   └── dependencies.py     # Dependencias compartidas (DB, Redis)
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── dss_engine.py       # Wrapper del motor OpenDSS
│   │   ├── circuit_analyzer.py # Logica de analisis del circuito
│   │   ├── gd_simulator.py     # Logica de simulacion con GD
│   │   └── hosting_solver.py   # Busqueda binaria de hosting capacity
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py          # Modelos Pydantic (request/response)
│   │   └── database.py         # Modelos SQLAlchemy (persistencia)
│   │
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_app.py       # Configuracion de Celery
│   │   └── hosting_task.py     # Tarea asincrona de hosting capacity
│   │
│   └── utils/
│       ├── __init__.py
│       ├── dss_preprocessor.py # Limpieza y preprocesamiento de archivos DSS
│       └── exporters.py        # Exportacion a Excel y JSON
│
├── tests/
│   ├── conftest.py
│   ├── test_circuit.py
│   ├── test_simulation.py
│   └── test_hosting.py
│
├── docker-compose.yml          # Orquestacion local
├── docker-compose.prod.yml     # Orquestacion produccion
├── requirements.txt
├── .env.example
└── README.md
```

---

## 6. Catalogo Completo de Endpoints

### Convencion de nomenclatura

Todos los endpoints siguen el prefijo `/api/v1/`. El versionado permite hacer cambios breaking sin romper clientes existentes.

---

### Grupo 1 — Circuito (`/api/v1/circuit`)

---

#### `POST /api/v1/circuit/upload`

Sube, valida y compila un archivo de circuito DSS. El circuito compilado se almacena en Redis con un TTL de 2 horas.

**Tipo:** Sincronica  
**Tiempo estimado:** 300ms - 1.5s  
**Content-Type:** `multipart/form-data`

**Campos del formulario:**

| Campo | Tipo | Requerido | Descripcion |
|---|---|---|---|
| `main_dss` | File | Si | Archivo principal del circuito (.dss) |
| `linecodes_dss` | File | No | Definiciones de codigos de linea (.dss) |
| `busxy_csv` | File | No | Coordenadas geograficas de barras (.csv) |

**Respuesta 201:**
```json
{
  "circuit_id": "ckt_7f3a21b4e9c0",
  "circuit_info": {
    "name": "IEEE13Nodeckt",
    "num_buses": 16,
    "num_elements": 58,
    "converged": true,
    "total_power_kw": -3466.1,
    "total_power_kvar": -1990.6
  },
  "buses": ["650", "rg60", "632", "633", "634", "645", "646", "670", "671", "675", "680", "684", "611", "652", "692", "rg70"],
  "buses_phases": {
    "650": [1, 2, 3],
    "634": [1, 2, 3],
    "645": [2, 3],
    "611": [3],
    "652": [1]
  },
  "expires_at": "2025-04-07T16:00:00Z",
  "preprocessing_warnings": [
    "Se elimino referencia a IEEELineCodes.dss (resuelto automaticamente)"
  ]
}
```

**Respuesta 400:**
```json
{
  "error": "INVALID_DSS_FORMAT",
  "message": "Error de compilacion en el archivo DSS",
  "detail": "Linea 34: elemento 'Line.INEXISTENTE' referencia bus 'bus999' que no existe en el circuito"
}
```

**Respuesta 422:**
```json
{
  "error": "CIRCUIT_DID_NOT_CONVERGE",
  "message": "El circuito cargo correctamente pero el solucionador no convergio",
  "suggestion": "Verifique que el circuito tenga una fuente definida y que las cargas sean validas"
}
```

---

#### `GET /api/v1/circuit/{circuit_id}`

Retorna la informacion basica del circuito. Util para verificar que el circuito sigue activo antes de lanzar calculos largos.

**Tipo:** Sincronica  
**Tiempo estimado:** 5-30ms

**Respuesta 200:**
```json
{
  "circuit_id": "ckt_7f3a21b4e9c0",
  "name": "IEEE13Nodeckt",
  "num_buses": 16,
  "num_elements": 58,
  "converged": true,
  "total_power_kw": -3466.1,
  "total_power_kvar": -1990.6,
  "buses_phases": { ... },
  "lines": [
    {
      "name": "650632",
      "phases": 3,
      "norm_amps": 400.0,
      "emerg_amps": 600.0,
      "bus1": "650",
      "bus2": "632"
    }
  ],
  "expires_at": "2025-04-07T16:00:00Z"
}
```

**Respuesta 404:**
```json
{
  "error": "CIRCUIT_NOT_FOUND",
  "message": "El circuit_id no existe o ha expirado",
  "suggestion": "Vuelva a cargar el archivo DSS mediante POST /api/v1/circuit/upload"
}
```

---

#### `DELETE /api/v1/circuit/{circuit_id}`

Elimina el circuito de Redis antes de que expire. Libera memoria.

**Respuesta 204:** sin cuerpo

---

### Grupo 2 — Analisis Base (`/api/v1/circuit/{circuit_id}/analysis`)

---

#### `GET /api/v1/circuit/{circuit_id}/analysis/voltage-profile`

Calcula y retorna el perfil de voltajes en por unidad del estado base (sin GD).

**Tipo:** Sincronica  
**Tiempo estimado:** 50-400ms

**Query parameters:**

| Parametro | Tipo | Default | Descripcion |
|---|---|---|---|
| `phase` | int | null | Filtrar por fase (1, 2 o 3). Si no se especifica, retorna todas. |
| `only_violations` | bool | false | Retornar solo barras fuera del rango 0.95-1.05 PU |

**Respuesta 200:**
```json
{
  "circuit_id": "ckt_7f3a21b4e9c0",
  "state": "base",
  "voltage_profile": [
    { "bus_phase": "650.1", "voltage_pu": 1.000000, "in_range": true },
    { "bus_phase": "650.2", "voltage_pu": 1.000000, "in_range": true },
    { "bus_phase": "632.1", "voltage_pu": 1.021456, "in_range": true },
    { "bus_phase": "634.1", "voltage_pu": 0.994521, "in_range": true },
    { "bus_phase": "611.3", "voltage_pu": 1.049812, "in_range": true },
    { "bus_phase": "652.1", "voltage_pu": 0.972340, "in_range": true }
  ],
  "limits": { "lower": 0.95, "upper": 1.05 },
  "violations_count": 0,
  "summary": {
    "min_voltage_pu": 0.972340,
    "max_voltage_pu": 1.049812,
    "avg_voltage_pu": 1.008450
  }
}
```

---

#### `GET /api/v1/circuit/{circuit_id}/analysis/losses`

Retorna la tabla de perdidas del sistema en estado base, desglosada por elemento.

**Tipo:** Sincronica  
**Tiempo estimado:** 80-500ms

**Respuesta 200:**
```json
{
  "circuit_id": "ckt_7f3a21b4e9c0",
  "state": "base",
  "summary": {
    "total_losses_kw": 87.34,
    "total_losses_kvar": 42.15,
    "total_load_kw": 3466.10,
    "loss_percentage": 2.52
  },
  "elements": [
    {
      "type": "Lines",
      "element": "650632",
      "losses_kw": 12.450,
      "losses_kvar": 6.230,
      "losses_pct": 0.36
    },
    {
      "type": "Transformers",
      "element": "Sub",
      "losses_kw": 34.120,
      "losses_kvar": 16.780,
      "losses_pct": 0.98
    },
    {
      "type": "Transformers",
      "element": "XFM1",
      "losses_kw": 8.560,
      "losses_kvar": 4.120,
      "losses_pct": 0.25
    }
  ]
}
```

---

#### `GET /api/v1/circuit/{circuit_id}/analysis/lines`

Retorna informacion de todas las lineas del circuito, incluyendo sus limites de corriente y potencia.

**Tipo:** Sincronica  
**Tiempo estimado:** 20-100ms

**Respuesta 200:**
```json
{
  "circuit_id": "ckt_7f3a21b4e9c0",
  "lines": [
    {
      "name": "650632",
      "phases": 3,
      "bus1": "650",
      "bus2": "632",
      "norm_amps": 400.0,
      "emerg_amps": 600.0,
      "kv_base": 4.16,
      "s_nominal_kva": 2884.0,
      "current_base_amps": [185.3, 184.1, 186.7, 0.0],
      "loading_pct_base": 46.3
    }
  ]
}
```

---

### Grupo 3 — Simulacion con GD (`/api/v1/circuit/{circuit_id}/simulate`)

---

#### `POST /api/v1/circuit/{circuit_id}/simulate`

Aplica una GD al circuito y retorna el analisis comparativo completo.

**Tipo:** Sincronica  
**Tiempo estimado:** 400ms - 2s

**Body (JSON):**
```json
{
  "bus": "634",
  "phases": [1, 2, 3],
  "connection_type": "three_phase",
  "power_kw": 500.0,
  "power_kvar": 0.0
}
```

**Campos del body:**

| Campo | Tipo | Requerido | Descripcion | Valores |
|---|---|---|---|---|
| `bus` | string | Si | Nombre de la barra de conexion | Cualquier barra del circuito |
| `phases` | List[int] | Si | Fases a utilizar | Subconjunto de fases disponibles |
| `connection_type` | string | Si | Tipo de conexion | `single_phase`, `two_phase`, `three_phase` |
| `power_kw` | float | Si | Potencia activa en kW | 0.0 - 150,000.0 |
| `power_kvar` | float | No | Potencia reactiva en kvar (default 0) | Cualquier valor real |

**Respuesta 200:**
```json
{
  "circuit_id": "ckt_7f3a21b4e9c0",
  "simulation_id": "sim_a3b1c9d2e5f6",
  "input": {
    "bus": "634",
    "phases": [1, 2, 3],
    "connection_type": "three_phase",
    "power_kw": 500.0,
    "power_kvar": 0.0
  },
  "converged": true,
  "voltage_comparison": [
    {
      "bus_phase": "634.1",
      "voltage_base_pu": 0.994521,
      "voltage_with_gd_pu": 1.012430,
      "delta_pu": 0.017909,
      "in_range_base": true,
      "in_range_with_gd": true
    },
    {
      "bus_phase": "650.1",
      "voltage_base_pu": 1.000000,
      "voltage_with_gd_pu": 1.009812,
      "delta_pu": 0.009812,
      "in_range_base": true,
      "in_range_with_gd": true
    }
  ],
  "losses": {
    "base_kw": 87.34,
    "with_gd_kw": 72.81,
    "delta_kw": -14.53,
    "base_kvar": 42.15,
    "with_gd_kvar": 35.90,
    "delta_kvar": -6.25
  },
  "violations": {
    "voltage": [],
    "current": [],
    "power": []
  },
  "summary": {
    "has_violations": false,
    "voltage_violations_count": 0,
    "current_violations_count": 0,
    "power_violations_count": 0,
    "losses_change_pct": -16.64
  }
}
```

**Respuesta con violaciones:**
```json
{
  ...
  "violations": {
    "voltage": [
      {
        "bus_phase": "652.1",
        "voltage_pu": 0.941200,
        "limit_lower": 0.95,
        "limit_upper": 1.05,
        "exceeded": "lower"
      }
    ],
    "current": [
      {
        "line": "650632",
        "phase": 1,
        "current_a": 412.50,
        "limit_a": 400.0,
        "exceeded_pct": 3.13
      }
    ],
    "power": [
      {
        "line": "650632",
        "phase": 1,
        "power_kva": 2971.8,
        "limit_kva": 2884.0,
        "exceeded_pct": 3.05
      }
    ]
  },
  "summary": {
    "has_violations": true,
    "voltage_violations_count": 1,
    "current_violations_count": 1,
    "power_violations_count": 1
  }
}
```

**Respuesta 400 — Incompatibilidad de fases:**
```json
{
  "error": "PHASE_INCOMPATIBILITY",
  "message": "La barra '611' solo tiene disponible la fase 3. No es posible conectar una GD trifasica.",
  "bus": "611",
  "available_phases": [3],
  "requested_phases": [1, 2, 3]
}
```

**Respuesta 400 — Tipo de conexion inconsistente:**
```json
{
  "error": "CONNECTION_TYPE_MISMATCH",
  "message": "Se especificaron 2 fases pero el tipo de conexion es 'three_phase'",
  "suggestion": "Use 'two_phase' o agregue la tercera fase"
}
```

---

### Grupo 4 — Hosting Capacity (`/api/v1/circuit/{circuit_id}/hosting-capacity`)

---

#### `POST /api/v1/circuit/{circuit_id}/hosting-capacity`

Inicia el calculo de hosting capacity para todas las barras del circuito. Operacion asincronica.

**Tipo:** Asincronica (202 Accepted)  
**Tiempo de proceso:** 3-15 minutos (ver seccion 4)

**Body (JSON):**
```json
{
  "max_power_kw": 1500000,
  "check_voltage": true,
  "check_current": true,
  "check_power": true,
  "buses": null
}
```

| Campo | Tipo | Requerido | Default | Descripcion |
|---|---|---|---|---|
| `max_power_kw` | float | No | 1500000 | Limite superior de busqueda binaria |
| `check_voltage` | bool | No | true | Incluir violaciones de voltaje como criterio |
| `check_current` | bool | No | true | Incluir violaciones de corriente |
| `check_power` | bool | No | true | Incluir violaciones de potencia |
| `buses` | List[str] | No | null (todos) | Limitar calculo a un subconjunto de barras |

**Respuesta 202:**
```json
{
  "task_id": "task_b7c4d1e8f2a3",
  "status": "queued",
  "circuit_id": "ckt_7f3a21b4e9c0",
  "total_combinations": 35,
  "estimated_duration_seconds": 420,
  "poll_url": "/api/v1/tasks/task_b7c4d1e8f2a3/status",
  "created_at": "2025-04-07T14:30:00Z"
}
```

---

#### `GET /api/v1/circuit/{circuit_id}/hosting-capacity`

Retorna los resultados del ultimo calculo completado de hosting capacity para el circuito.

**Tipo:** Sincronica  
**Tiempo estimado:** 10-50ms (lectura de base de datos)

**Respuesta 200:**
```json
{
  "circuit_id": "ckt_7f3a21b4e9c0",
  "calculated_at": "2025-04-07T14:37:15Z",
  "results": [
    { "bus": "650", "phase": 1, "max_gd_kw": 125000, "limiting_constraint": "voltage" },
    { "bus": "650", "phase": 2, "max_gd_kw": 118500, "limiting_constraint": "current" },
    { "bus": "650", "phase": 3, "max_gd_kw": 122300, "limiting_constraint": "voltage" },
    { "bus": "634", "phase": 1, "max_gd_kw": 87500,  "limiting_constraint": "voltage" },
    { "bus": "611", "phase": 3, "max_gd_kw": 42100,  "limiting_constraint": "power" }
  ],
  "pivot": {
    "650": { "1": 125000, "2": 118500, "3": 122300 },
    "634": { "1": 87500,  "2": 91200,  "3": 89100  },
    "611": { "3": 42100 }
  },
  "summary": {
    "total_combinations": 35,
    "max_hosting_kw": 125000,
    "min_hosting_kw": 8200,
    "avg_hosting_kw": 76400,
    "most_constrained_bus": "611",
    "least_constrained_bus": "650"
  }
}
```

**Respuesta 404 — Calculo no realizado aun:**
```json
{
  "error": "HOSTING_CAPACITY_NOT_CALCULATED",
  "message": "No existe un calculo de hosting capacity para este circuito",
  "suggestion": "Ejecute POST /api/v1/circuit/{circuit_id}/hosting-capacity para iniciar el calculo"
}
```

---

#### `GET /api/v1/circuit/{circuit_id}/hosting-capacity/{bus}`

Retorna el hosting capacity para una barra especifica, con detalle por fase.

**Respuesta 200:**
```json
{
  "circuit_id": "ckt_7f3a21b4e9c0",
  "bus": "634",
  "phases": [
    {
      "phase": 1,
      "max_gd_kw": 87500,
      "limiting_constraint": "voltage",
      "violation_at_max": {
        "type": "voltage",
        "bus_phase": "652.1",
        "value": 0.941
      }
    },
    {
      "phase": 2,
      "max_gd_kw": 91200,
      "limiting_constraint": "current",
      "violation_at_max": {
        "type": "current",
        "line": "650632",
        "value_a": 401.2,
        "limit_a": 400.0
      }
    }
  ]
}
```

---

### Grupo 5 — Tareas Asincronas (`/api/v1/tasks`)

---

#### `GET /api/v1/tasks/{task_id}/status`

Consulta el estado de una tarea en ejecucion o completada.

**Tipo:** Sincronica  
**Tiempo estimado:** 5-20ms

**Respuesta 200 (en cola):**
```json
{
  "task_id": "task_b7c4d1e8f2a3",
  "status": "queued",
  "position_in_queue": 2,
  "created_at": "2025-04-07T14:30:00Z"
}
```

**Respuesta 200 (en ejecucion):**
```json
{
  "task_id": "task_b7c4d1e8f2a3",
  "status": "running",
  "progress_pct": 45,
  "current_step": "Calculando barra 634, fase 2 (16/35 combinaciones)",
  "buses_completed": 15,
  "buses_total": 35,
  "started_at": "2025-04-07T14:30:05Z",
  "elapsed_seconds": 190,
  "estimated_remaining_seconds": 230
}
```

**Respuesta 200 (completado):**
```json
{
  "task_id": "task_b7c4d1e8f2a3",
  "status": "completed",
  "progress_pct": 100,
  "result_url": "/api/v1/circuit/ckt_7f3a21b4e9c0/hosting-capacity",
  "started_at": "2025-04-07T14:30:05Z",
  "completed_at": "2025-04-07T14:37:15Z",
  "duration_seconds": 430
}
```

**Respuesta 200 (error):**
```json
{
  "task_id": "task_b7c4d1e8f2a3",
  "status": "failed",
  "error_code": "ENGINE_ERROR",
  "error_message": "El motor OpenDSS lanzo una excepcion en la barra '680', fase 3",
  "failed_at": "2025-04-07T14:32:10Z",
  "partial_results_available": true,
  "partial_results_url": "/api/v1/tasks/task_b7c4d1e8f2a3/partial-results"
}
```

---

#### `DELETE /api/v1/tasks/{task_id}`

Cancela una tarea en cola o en ejecucion.

**Respuesta 200:**
```json
{
  "task_id": "task_b7c4d1e8f2a3",
  "status": "cancelled",
  "cancelled_at": "2025-04-07T14:31:00Z"
}
```

---

### Grupo 6 — Exportacion (`/api/v1/circuit/{circuit_id}/export`)

---

#### `GET /api/v1/circuit/{circuit_id}/export/excel`

Exporta los resultados a un archivo Excel con multiples hojas de calculo.

**Query parameters:**

| Parametro | Tipo | Default | Descripcion |
|---|---|---|---|
| `include_voltage_profile` | bool | true | Hoja con perfil de voltaje base |
| `include_losses` | bool | true | Hoja con tabla de perdidas |
| `include_hosting_capacity` | bool | true | Hoja con hosting capacity (requiere calculo previo) |
| `include_violations` | bool | true | Hoja con violaciones de la ultima simulacion |
| `simulation_id` | string | null | Incluir resultados de una simulacion especifica |

**Respuesta 200:**
- Content-Type: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- Content-Disposition: `attachment; filename="hosting_capacity_IEEE13.xlsx"`

**Estructura del Excel:**
- Hoja `Circuito`: informacion general del circuito
- Hoja `Voltajes_Base`: perfil de voltajes sin GD
- Hoja `Perdidas_Base`: tabla de perdidas sin GD
- Hoja `Hosting_Capacity`: pivot de maxima GD por barra y fase
- Hoja `Simulacion_Voltajes`: comparativo de voltajes de la ultima simulacion
- Hoja `Simulacion_Perdidas`: comparativo de perdidas de la ultima simulacion
- Hoja `Violaciones`: violaciones detectadas en la ultima simulacion

---

#### `GET /api/v1/circuit/{circuit_id}/export/json`

Exporta todos los resultados disponibles en formato JSON.

**Respuesta 200:**
```json
{
  "circuit_id": "ckt_7f3a21b4e9c0",
  "exported_at": "2025-04-07T14:40:00Z",
  "circuit_info": { ... },
  "voltage_profile": [ ... ],
  "losses": { ... },
  "hosting_capacity": { ... },
  "simulations": [ ... ]
}
```

---

### Resumen completo de endpoints

| Metodo | Endpoint | Tipo | Tiempo est. |
|---|---|---|---|
| POST | `/api/v1/circuit/upload` | Sinc. | 300ms-1.5s |
| GET | `/api/v1/circuit/{id}` | Sinc. | 5-30ms |
| DELETE | `/api/v1/circuit/{id}` | Sinc. | 5ms |
| GET | `/api/v1/circuit/{id}/analysis/voltage-profile` | Sinc. | 50-400ms |
| GET | `/api/v1/circuit/{id}/analysis/losses` | Sinc. | 80-500ms |
| GET | `/api/v1/circuit/{id}/analysis/lines` | Sinc. | 20-100ms |
| POST | `/api/v1/circuit/{id}/simulate` | Sinc. | 400ms-2s |
| POST | `/api/v1/circuit/{id}/hosting-capacity` | Asinc. | Inmediato (202) |
| GET | `/api/v1/circuit/{id}/hosting-capacity` | Sinc. | 10-50ms |
| GET | `/api/v1/circuit/{id}/hosting-capacity/{bus}` | Sinc. | 10-30ms |
| GET | `/api/v1/tasks/{task_id}/status` | Sinc. | 5-20ms |
| DELETE | `/api/v1/tasks/{task_id}` | Sinc. | 5ms |
| GET | `/api/v1/circuit/{id}/export/excel` | Sinc. | 200ms-1s |
| GET | `/api/v1/circuit/{id}/export/json` | Sinc. | 50-200ms |

---

## 7. Fase 1 — Configuracion del Entorno Docker

### 7.1 Imagen base para el worker con OpenDSS

El archivo `Dockerfile.worker` es el mas critico porque contiene OpenDSS.

```dockerfile
# docker/Dockerfile.worker
FROM python:3.11-slim-bookworm

# Instalar dependencias del sistema requeridas por opendssdirect
# libgomp1 es el runtime de OpenMP que OpenDSS necesita
# libgfortran5 y libopenblas son necesarios para el solucionador lineal
RUN apt-get update && apt-get install -y \
    libgomp1 \
    libgfortran5 \
    libopenblas0 \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar solo requirements primero para aprovechar cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Verificar que opendssdirect funciona correctamente
# Este paso detecta problemas de dependencias en tiempo de build, no en runtime
RUN python -c "import opendssdirect as dss; dss.Basic.Start(0); print('OpenDSS OK')"

COPY app/ ./app/

CMD ["celery", "-A", "app.tasks.celery_app", "worker", 
     "--loglevel=info", 
     "--concurrency=1",
     "--queues=hosting_capacity,simulation"]
```

**Por que `--concurrency=1`:** OpenDSS no es thread-safe. Cada proceso worker debe tener exactamente una instancia del motor. Con concurrency=1 y multiples replicas del container, se obtiene paralelismo real sin colisiones.

### 7.2 Imagen para la API

```dockerfile
# docker/Dockerfile.api
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", 
     "--host", "0.0.0.0", 
     "--port", "8000",
     "--workers", "4",
     "--timeout-keep-alive", "65"]
```

### 7.3 Docker Compose para desarrollo local

```yaml
# docker-compose.yml
version: "3.9"

services:

  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/hosting_capacity
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    volumes:
      - ./app:/app/app  # Hot reload en desarrollo
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    environment:
      - REDIS_URL=redis://redis:6379/0
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/hosting_capacity
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
    depends_on:
      redis:
        condition: service_healthy
    # Un worker por replica; escalar con: docker-compose up --scale worker=3
    deploy:
      replicas: 2

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: hosting_capacity
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

  flower:
    image: mher/flower:2.0
    command: celery flower --broker=redis://redis:6379/1
    ports:
      - "5555:5555"
    depends_on:
      - redis
    # Flower es el dashboard de monitoreo de Celery, solo para desarrollo

volumes:
  postgres_data:
```

### 7.4 Variables de entorno

```bash
# .env.example
# API
SECRET_KEY=cambiar_en_produccion
ALLOWED_ORIGINS=http://localhost:3000,https://midominio.com
API_V1_PREFIX=/api/v1

# Base de datos
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/hosting_capacity

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# OpenDSS
CIRCUIT_TTL_SECONDS=7200         # Tiempo de vida del circuito en Redis (2 horas)
MAX_POWER_KW_LIMIT=10000000      # Limite absoluto de potencia GD aceptado por la API

# Celery
CELERY_TASK_TIMEOUT_SECONDS=3600 # Timeout de 1 hora para la busqueda binaria
CELERY_WORKER_CONCURRENCY=1      # NUNCA cambiar a mas de 1 por worker (OpenDSS no es thread-safe)
```

---

## 8. Fase 2 — Nucleo del Motor OpenDSS

### 8.1 Wrapper del motor

El principio fundamental: **el motor nunca se inicializa fuera de los workers de Celery.** La API de FastAPI nunca importa ni toca `opendssdirect`.

```python
# app/core/dss_engine.py

import opendssdirect as dss
import tempfile
import os
import re
from typing import Optional, List, Dict, Tuple

class DSSEngine:
    """
    Encapsula completamente el motor OpenDSS.
    Una instancia de esta clase = un motor OpenDSS aislado.
    Nunca compartir una instancia entre threads o requests.
    """

    def __init__(self):
        self._engine = dss.DSS
        self._engine.Start(0)
        self._text = self._engine.Text
        self._circuit = self._engine.ActiveCircuit
        self._solution = self._circuit.Solution
        self._circuit_loaded = False

    def load_circuit(self, dss_content: str, linecodes_content: Optional[str] = None) -> Dict:
        """
        Carga un circuito DSS desde string. Usa archivo temporal para evitar
        dependencias de ruta del sistema de archivos.
        """
        temp_dir = tempfile.mkdtemp(prefix="dss_circuit_")
        try:
            # Preprocesar el contenido
            processed = self._preprocess(dss_content)
            
            # Si hay linecodes externos, escribirlos primero
            if linecodes_content:
                lc_path = os.path.join(temp_dir, "linecodes.dss")
                with open(lc_path, "w", encoding="utf-8") as f:
                    f.write(linecodes_content)
                # Inyectar redirect al inicio del archivo principal
                processed = f"Redirect {lc_path}\n" + processed

            main_path = os.path.join(temp_dir, "circuit.dss")
            with open(main_path, "w", encoding="utf-8") as f:
                f.write(processed)

            self._text.Command = "Clear"
            self._text.Command = f"Compile {main_path}"
            self._solution.Solve()

            if not self._solution.Converged:
                raise ValueError("El circuito no convergio. Verifique la definicion del circuito.")

            self._circuit_loaded = True
            return self._get_circuit_info()

        finally:
            # Siempre limpiar archivos temporales
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _preprocess(self, content: str) -> str:
        """Elimina referencias externas que no se pueden resolver en el servidor."""
        # Eliminar redirect a IEEELineCodes.dss (se inyectan por separado)
        content = re.sub(r'(?i).*redirect\s+.*ieeelinecodes.*\.dss.*\n?', '', content)
        # Eliminar buscoords (opcional, no afecta la simulacion)
        content = re.sub(r'(?i).*buscoords.*\.csv.*\n?', '', content)
        # Eliminar basekv de linecodes (parametro invalido en esta version)
        content = re.sub(
            r'(new\s+linecode[^\n]*)\bbasekv\s*=\s*[\d.]+\s*',
            r'\1',
            content,
            flags=re.IGNORECASE
        )
        return content

    def _get_circuit_info(self) -> Dict:
        return {
            "name": self._circuit.Name,
            "num_buses": len(self._circuit.AllBusNames),
            "num_elements": self._circuit.NumElements,
            "converged": self._solution.Converged,
            "total_power_kw": self._circuit.TotalPower[0] / 1000,
            "total_power_kvar": self._circuit.TotalPower[1] / 1000,
        }

    def get_voltage_profile(self) -> List[Dict]:
        """Obtiene voltajes PU de todas las barras y fases."""
        results = []
        for bus in self._circuit.AllBusNames:
            self._circuit.SetActiveBus(bus)
            pu_voltages = self._circuit.ActiveBus.puVoltages
            nodes = self._circuit.ActiveBus.Nodes
            for idx, node in enumerate(nodes):
                real = pu_voltages[2 * idx]
                imag = pu_voltages[2 * idx + 1]
                mag = round((real**2 + imag**2)**0.5, 6)
                results.append({
                    "bus_phase": f"{bus}.{node}",
                    "bus": bus,
                    "phase": node,
                    "voltage_pu": mag,
                    "in_range": 0.95 <= mag <= 1.05
                })
        return results

    def get_losses(self) -> Tuple[List[Dict], Dict]:
        """Calcula perdidas por elemento del circuito."""
        total_kw = round(self._circuit.Losses[0] / 1000, 6)
        total_kvar = round(self._circuit.Losses[1] / 1000, 6)
        total_load_kw = abs(round(self._circuit.TotalPower[0] / 1000, 6))
        total_load_kw = max(total_load_kw, 1e-3)

        elements = []
        for tipo in ["Lines", "Transformers", "Capacitors"]:
            collection = getattr(self._circuit, tipo)
            for name in list(collection.AllNames):
                try:
                    self._circuit.SetActiveElement(f"{tipo[:-1]}.{name}")
                    losses = self._circuit.ActiveCktElement.Losses
                    kw = round(losses[0] / 1000, 5)
                    kvar = round(losses[1] / 1000, 5)
                    pct = round((kw / total_load_kw) * 100, 2)
                except Exception:
                    kw = kvar = pct = 0.0

                elements.append({
                    "type": tipo,
                    "element": name,
                    "losses_kw": kw,
                    "losses_kvar": kvar,
                    "losses_pct": pct
                })

        summary = {
            "total_losses_kw": total_kw,
            "total_losses_kvar": total_kvar,
            "total_load_kw": total_load_kw,
            "loss_percentage": round((total_kw / total_load_kw) * 100, 2)
        }
        return elements, summary

    def apply_gd(self, bus: str, phases: List[int], power_kw: float, power_kvar: float = 0.0):
        """Aplica un generador distribuido al circuito y resuelve."""
        self._circuit.SetActiveBus(bus)
        kv_ln = self._circuit.ActiveBus.kVBase

        n_phases = len(phases)
        if n_phases == 3:
            kv = kv_ln * (3**0.5)
            self._text.Command = (
                f"New Generator.GD Bus1={bus} Phases=3 "
                f"kV={kv:.3f} kW={power_kw} kvar={power_kvar} Model=1"
            )
        elif n_phases == 2:
            kv = kv_ln * 2
            phases_str = ".".join(str(p) for p in phases)
            self._text.Command = (
                f"New Generator.GD Bus1={bus}.{phases_str} Phases=2 "
                f"kV={kv:.3f} kW={power_kw} kvar={power_kvar} Model=1"
            )
        else:
            self._text.Command = (
                f"New Generator.GD Bus1={bus}.{phases[0]} Phases=1 "
                f"kV={kv_ln:.3f} kW={power_kw} kvar={power_kvar} Model=1"
            )

        self._text.Command = "Solve"

        if not self._solution.Converged:
            raise ValueError(
                f"El circuito no convergio con GD de {power_kw} kW en barra {bus}"
            )

    def remove_gd(self):
        """Elimina el generador GD si existe."""
        generators = list(self._circuit.Generators.AllNames)
        if any(g.lower() == "gd" for g in generators):
            self._text.Command = "Remove Generator.GD"

    def check_violations(self) -> Dict:
        """Verifica todos los tipos de violaciones del estado actual del circuito."""
        voltage_violations = []
        current_violations = []
        power_violations = []

        # Voltaje
        for bus in self._circuit.AllBusNames:
            self._circuit.SetActiveBus(bus)
            pu = self._circuit.ActiveBus.puVoltages
            nodes = self._circuit.ActiveBus.Nodes
            for idx, node in enumerate(nodes):
                real = pu[2 * idx]
                imag = pu[2 * idx + 1]
                mag = round((real**2 + imag**2)**0.5, 6)
                if mag < 0.95 or mag > 1.05:
                    voltage_violations.append({
                        "bus_phase": f"{bus}.{node}",
                        "voltage_pu": mag,
                        "exceeded": "lower" if mag < 0.95 else "upper"
                    })

        # Corriente y potencia
        for name in list(self._circuit.Lines.AllNames):
            self._circuit.Lines.Name = name
            self._circuit.SetActiveElement(f"Line.{name}")
            mags = self._circuit.ActiveCktElement.CurrentsMagAng[::2]

            norm_amps = self._circuit.Lines.EmergAmps or 1.0
            bus1 = self._circuit.Lines.Bus1.split(".")[0]
            self._circuit.SetActiveBus(bus1)
            kv_base = self._circuit.ActiveBus.kVBase or 1.0
            n_phases = self._circuit.Lines.Phases
            kv = kv_base * 1.732 if n_phases > 1 else kv_base
            s_nom = kv * norm_amps

            for i, mag in enumerate(mags):
                if mag > norm_amps:
                    current_violations.append({
                        "line": name,
                        "phase": i + 1,
                        "current_a": round(mag, 2),
                        "limit_a": round(norm_amps, 2),
                        "exceeded_pct": round((mag / norm_amps - 1) * 100, 2)
                    })
                s_real = (1.732 * kv * mag) if n_phases > 1 else (kv * mag)
                if s_real > s_nom:
                    power_violations.append({
                        "line": name,
                        "phase": i + 1,
                        "power_kva": round(s_real, 2),
                        "limit_kva": round(s_nom, 2),
                        "exceeded_pct": round((s_real / s_nom - 1) * 100, 2)
                    })

        return {
            "voltage": voltage_violations,
            "current": current_violations,
            "power": power_violations
        }

    def reset_circuit(self, dss_content: str, linecodes_content: Optional[str] = None):
        """Recarga el circuito desde el estado base. Usar dentro de la busqueda binaria."""
        self.load_circuit(dss_content, linecodes_content)
```

---

## 9. Fase 3 — Cola de Tareas con Celery y Redis

### 9.1 Configuracion de Celery

```python
# app/tasks/celery_app.py

from celery import Celery
from app.config import settings

celery_app = Celery(
    "hosting_capacity",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.hosting_task"]
)

celery_app.conf.update(
    # Serializar resultados como JSON (no pickle, por seguridad)
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timeout de 1 hora para la busqueda binaria en circuitos grandes
    task_time_limit=3600,
    task_soft_time_limit=3300,  # 5 minutos antes del hard limit, lanzar SoftTimeLimitExceeded

    # Un worker maneja una tarea a la vez (critico para OpenDSS)
    worker_concurrency=1,

    # Guardar resultados por 24 horas
    result_expires=86400,

    # Configuracion de reintentos
    task_max_retries=2,
    task_default_retry_delay=30,

    # Rutas de tareas por tipo
    task_routes={
        "app.tasks.hosting_task.calculate_hosting_capacity": {"queue": "hosting_capacity"},
        "app.tasks.hosting_task.run_simulation": {"queue": "simulation"},
    }
)
```

### 9.2 Tarea de Hosting Capacity

```python
# app/tasks/hosting_task.py

from celery import current_task
from celery.exceptions import SoftTimeLimitExceeded
from app.tasks.celery_app import celery_app
from app.core.dss_engine import DSSEngine
import redis
import json
import time

@celery_app.task(
    bind=True,
    name="app.tasks.hosting_task.calculate_hosting_capacity",
    max_retries=2,
    soft_time_limit=3300,
    time_limit=3600
)
def calculate_hosting_capacity(
    self,
    circuit_id: str,
    dss_content: str,
    linecodes_content: str | None,
    max_power_kw: float,
    check_voltage: bool,
    check_current: bool,
    check_power: bool,
    target_buses: list | None
):
    """
    Tarea Celery que ejecuta la busqueda binaria completa.
    Corre en el proceso worker, con su propia instancia de OpenDSS.
    """
    engine = DSSEngine()
    circuit_info = engine.load_circuit(dss_content, linecodes_content)
    
    barras = target_buses or list(engine._circuit.AllBusNames)
    results = []
    total_combinations = 0
    completed_combinations = 0

    # Calcular total de combinaciones para el progreso
    for bus in barras:
        engine._circuit.SetActiveBus(bus)
        total_combinations += len(engine._circuit.ActiveBus.Nodes)

    # Pre-cache de informacion de lineas (se reutiliza en cada iteracion)
    lines_info = _get_lines_info(engine)

    for bus_idx, bus in enumerate(barras):
        engine._circuit.SetActiveBus(bus)
        nodes = sorted(engine._circuit.ActiveBus.Nodes)
        kv_ln = engine._circuit.ActiveBus.kVBase

        for phase in nodes:
            try:
                max_kw = _binary_search(
                    engine=engine,
                    dss_content=dss_content,
                    linecodes_content=linecodes_content,
                    bus=bus,
                    phase=phase,
                    kv_ln=kv_ln,
                    lines_info=lines_info,
                    max_power_kw=max_power_kw,
                    check_voltage=check_voltage,
                    check_current=check_current,
                    check_power=check_power
                )

                limiting = _determine_limiting_constraint(
                    engine, dss_content, linecodes_content, bus, phase, kv_ln, max_kw, lines_info
                )

                results.append({
                    "bus": bus,
                    "phase": phase,
                    "max_gd_kw": max_kw,
                    "limiting_constraint": limiting
                })

            except SoftTimeLimitExceeded:
                # El tiempo limite esta por alcanzarse, guardar resultados parciales
                _save_partial_results(circuit_id, results)
                raise

            except Exception as e:
                # Error en una barra especifica, continuar con las demas
                results.append({
                    "bus": bus,
                    "phase": phase,
                    "max_gd_kw": None,
                    "limiting_constraint": None,
                    "error": str(e)
                })

            completed_combinations += 1

            # Actualizar progreso cada combinacion
            current_task.update_state(
                state="PROGRESS",
                meta={
                    "progress_pct": round(completed_combinations / total_combinations * 100),
                    "current_step": f"Calculando barra {bus}, fase {phase} ({completed_combinations}/{total_combinations})",
                    "buses_completed": bus_idx,
                    "buses_total": len(barras)
                }
            )

    return {
        "circuit_id": circuit_id,
        "results": results,
        "total_combinations": len(results)
    }


def _binary_search(engine, dss_content, linecodes_content, bus, phase, kv_ln, lines_info, max_power_kw, check_voltage, check_current, check_power) -> float:
    """Busqueda binaria del maximo kW sin violaciones."""
    low = 0
    high = int(max_power_kw)
    best_kw = 0

    while low <= high:
        mid = (low + high) // 2
        engine.reset_circuit(dss_content, linecodes_content)
        engine._text.Command = (
            f"New Generator.GD Bus1={bus}.{phase} Phases=1 "
            f"kV={kv_ln:.3f} kW={mid} kvar=0 Model=1"
        )
        engine._text.Command = "Solve"

        if not engine._solution.Converged:
            high = mid - 1
            continue

        violations = engine.check_violations()
        has_violation = (
            (check_voltage and len(violations["voltage"]) > 0) or
            (check_current and len(violations["current"]) > 0) or
            (check_power and len(violations["power"]) > 0)
        )

        if not has_violation:
            best_kw = mid
            low = mid + 1
        else:
            high = mid - 1

    return best_kw


def _determine_limiting_constraint(engine, dss_content, linecodes_content, bus, phase, kv_ln, max_kw, lines_info) -> str:
    """Determina cual fue la restriccion limitante para el valor max_kw+1."""
    test_kw = max_kw + 1
    engine.reset_circuit(dss_content, linecodes_content)
    engine._text.Command = (
        f"New Generator.GD Bus1={bus}.{phase} Phases=1 "
        f"kV={kv_ln:.3f} kW={test_kw} kvar=0 Model=1"
    )
    engine._text.Command = "Solve"
    violations = engine.check_violations()

    if violations["voltage"]:
        return "voltage"
    if violations["current"]:
        return "current"
    if violations["power"]:
        return "power"
    return "none"


def _get_lines_info(engine) -> list:
    lines = []
    for name in list(engine._circuit.Lines.AllNames):
        engine._circuit.Lines.Name = name
        norm_amps = engine._circuit.Lines.EmergAmps or 1.0
        bus1 = engine._circuit.Lines.Bus1.split(".")[0]
        engine._circuit.SetActiveBus(bus1)
        kv_base = engine._circuit.ActiveBus.kVBase or 1.0
        n_phases = engine._circuit.Lines.Phases
        kv = kv_base * 1.732 if n_phases > 1 else kv_base
        lines.append((name, norm_amps, round(kv * norm_amps, 2)))
    return lines


def _save_partial_results(circuit_id: str, results: list):
    """Guarda resultados parciales en Redis en caso de timeout."""
    from app.config import settings
    r = redis.from_url(settings.REDIS_URL)
    r.setex(
        f"partial_results:{circuit_id}",
        3600,
        json.dumps(results)
    )
```

---

## 10. Fase 4 — API REST con FastAPI

### 10.1 Punto de entrada

```python
# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.routes import circuit, analysis, simulation, hosting, tasks, export

app = FastAPI(
    title="Hosting Capacity API",
    description="API REST para analisis de capacidad de alojamiento de generacion distribuida",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(circuit.router,    prefix="/api/v1/circuit",   tags=["Circuito"])
app.include_router(analysis.router,   prefix="/api/v1/circuit",   tags=["Analisis"])
app.include_router(simulation.router, prefix="/api/v1/circuit",   tags=["Simulacion"])
app.include_router(hosting.router,    prefix="/api/v1/circuit",   tags=["Hosting Capacity"])
app.include_router(tasks.router,      prefix="/api/v1/tasks",     tags=["Tareas"])
app.include_router(export.router,     prefix="/api/v1/circuit",   tags=["Exportacion"])

@app.get("/api/v1/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}
```

### 10.2 Esquemas Pydantic

```python
# app/models/schemas.py

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from enum import Enum

class ConnectionType(str, Enum):
    single_phase = "single_phase"
    two_phase = "two_phase"
    three_phase = "three_phase"

class SimulateGDRequest(BaseModel):
    bus: str = Field(..., description="Nombre de la barra de conexion")
    phases: List[int] = Field(..., min_length=1, max_length=3, description="Fases a utilizar (1, 2 o 3)")
    connection_type: ConnectionType
    power_kw: float = Field(..., ge=0, le=150000, description="Potencia activa en kW")
    power_kvar: float = Field(default=0.0, description="Potencia reactiva en kvar")

    @field_validator("phases")
    @classmethod
    def validate_phases(cls, v):
        if not all(p in [1, 2, 3] for p in v):
            raise ValueError("Las fases deben ser 1, 2 o 3")
        if len(v) != len(set(v)):
            raise ValueError("No se pueden repetir fases")
        return sorted(v)

    @field_validator("connection_type")
    @classmethod
    def validate_connection_consistency(cls, v, info):
        if "phases" in info.data:
            n = len(info.data["phases"])
            expected = {"single_phase": 1, "two_phase": 2, "three_phase": 3}
            if n != expected[v]:
                raise ValueError(
                    f"connection_type '{v}' requiere {expected[v]} fase(s) pero se especificaron {n}"
                )
        return v

class HostingCapacityRequest(BaseModel):
    max_power_kw: float = Field(default=1500000, gt=0)
    check_voltage: bool = True
    check_current: bool = True
    check_power: bool = True
    buses: Optional[List[str]] = None
```

### 10.3 Router de Circuito

```python
# app/api/routes/circuit.py

from fastapi import APIRouter, UploadFile, File, HTTPException, status
import redis
import uuid
import json
from app.config import settings
from app.core.dss_engine import DSSEngine

router = APIRouter()

def get_redis():
    return redis.from_url(settings.REDIS_URL, decode_responses=True)

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_circuit(
    main_dss: UploadFile = File(...),
    linecodes_dss: UploadFile = File(None),
    busxy_csv: UploadFile = File(None)
):
    if not main_dss.filename.endswith(".dss"):
        raise HTTPException(400, detail="El archivo principal debe tener extension .dss")

    dss_content = (await main_dss.read()).decode("utf-8")
    linecodes_content = None
    if linecodes_dss:
        linecodes_content = (await linecodes_dss.read()).decode("utf-8")

    # Validar el circuito intentando compilarlo
    # Esto ocurre en el proceso de la API; no es un calculo largo (solo compilacion + solve inicial)
    try:
        engine = DSSEngine()
        circuit_info = engine.load_circuit(dss_content, linecodes_content)
    except ValueError as e:
        raise HTTPException(422, detail={"error": "CIRCUIT_DID_NOT_CONVERGE", "message": str(e)})
    except Exception as e:
        raise HTTPException(400, detail={"error": "INVALID_DSS_FORMAT", "message": str(e)})

    # Guardar en Redis con TTL
    circuit_id = f"ckt_{uuid.uuid4().hex[:12]}"
    r = get_redis()
    r.setex(
        f"circuit:{circuit_id}:dss",
        settings.CIRCUIT_TTL_SECONDS,
        dss_content
    )
    if linecodes_content:
        r.setex(
            f"circuit:{circuit_id}:linecodes",
            settings.CIRCUIT_TTL_SECONDS,
            linecodes_content
        )

    # Obtener informacion de buses y fases
    buses_phases = {}
    for bus in engine._circuit.AllBusNames:
        engine._circuit.SetActiveBus(bus)
        buses_phases[bus] = list(engine._circuit.ActiveBus.Nodes)

    import datetime
    expires_at = (
        datetime.datetime.utcnow() + 
        datetime.timedelta(seconds=settings.CIRCUIT_TTL_SECONDS)
    ).isoformat() + "Z"

    return {
        "circuit_id": circuit_id,
        "circuit_info": circuit_info,
        "buses": list(engine._circuit.AllBusNames),
        "buses_phases": buses_phases,
        "expires_at": expires_at
    }
```

---

## 11. Fase 5 — Persistencia con PostgreSQL

Los resultados del calculo de hosting capacity pueden tardar minutos en generarse. Una vez calculados, deben persistirse en base de datos para no recalcular en cada request.

```python
# app/models/database.py

from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime

class Base(DeclarativeBase):
    pass

class CircuitRecord(Base):
    __tablename__ = "circuits"

    id = Column(String, primary_key=True)
    name = Column(String)
    num_buses = Column(Integer)
    num_elements = Column(Integer)
    total_power_kw = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class HostingCapacityResult(Base):
    __tablename__ = "hosting_capacity_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    circuit_id = Column(String, ForeignKey("circuits.id"))
    task_id = Column(String, unique=True)
    bus = Column(String)
    phase = Column(Integer)
    max_gd_kw = Column(Float)
    limiting_constraint = Column(String)
    calculated_at = Column(DateTime, default=datetime.utcnow)

class SimulationRecord(Base):
    __tablename__ = "simulations"

    id = Column(String, primary_key=True)
    circuit_id = Column(String, ForeignKey("circuits.id"))
    bus = Column(String)
    phases = Column(JSON)
    connection_type = Column(String)
    power_kw = Column(Float)
    power_kvar = Column(Float)
    losses_base_kw = Column(Float)
    losses_with_gd_kw = Column(Float)
    has_violations = Column(Boolean)
    violations = Column(JSON)
    voltage_comparison = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
```

---

## 12. Fase 6 — Despliegue en Produccion

### 12.1 Docker Compose de produccion

```yaml
# docker-compose.prod.yml
version: "3.9"

services:

  nginx:
    image: nginx:1.24-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - api

  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    environment:
      - REDIS_URL=${REDIS_URL}
      - DATABASE_URL=${DATABASE_URL}
      - CELERY_BROKER_URL=${CELERY_BROKER_URL}
      - CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND}
      - SECRET_KEY=${SECRET_KEY}
      - ALLOWED_ORIGINS=${ALLOWED_ORIGINS}
    deploy:
      replicas: 2
      restart_policy:
        condition: on-failure
        max_attempts: 3

  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    environment:
      - REDIS_URL=${REDIS_URL}
      - DATABASE_URL=${DATABASE_URL}
      - CELERY_BROKER_URL=${CELERY_BROKER_URL}
      - CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND}
    deploy:
      replicas: 3  # 3 calculos de hosting capacity en paralelo
      restart_policy:
        condition: on-failure

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  redis_data:
  postgres_data:
```

### 12.2 Configuracion de Nginx

```nginx
# docker/nginx/nginx.conf

upstream api_backend {
    server api:8000;
}

server {
    listen 80;
    server_name midominio.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name midominio.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # Archivos estaticos del frontend
    location / {
        root /var/www/html;
        try_files $uri $uri/ /index.html;
    }

    # API Backend
    location /api/ {
        proxy_pass http://api_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;  # Timeout generoso para upload de circuitos grandes
        
        # Para el upload de archivos grandes
        client_max_body_size 50M;
    }

    # WebSocket para actualizaciones de progreso (si se implementa)
    location /ws/ {
        proxy_pass http://api_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;  # 1 hora para tareas largas
    }
}
```

### 12.3 Estrategia de escalado

Para escalar horizontalmente los workers de Celery y procesar multiples calculos en paralelo:

```bash
# Escalar a 5 workers (5 calculos de hosting capacity simultaneos)
docker-compose -f docker-compose.prod.yml up --scale worker=5

# Ver estado de los workers
docker-compose exec worker celery -A app.tasks.celery_app inspect active

# Ver cola de tareas pendientes
docker-compose exec worker celery -A app.tasks.celery_app inspect reserved
```

---

## 13. Errores Conocidos y Como Manejarlos

### Error 1 — `libgomp.so.1: cannot open shared object file`

**Causa:** Falta el runtime OpenMP en la imagen Docker.

**Solucion:**
```dockerfile
RUN apt-get update && apt-get install -y libgomp1
```

**Por que ocurre en Alpine Linux:** Alpine usa `musl libc` en lugar de `glibc`. Los binarios de `opendssdirect.py` estan compilados para `glibc`. **No usar Alpine como imagen base para el worker.**

---

### Error 2 — El circuito no converge con GD de alta potencia

**Causa:** Cuando la potencia inyectada es muy alta, el solucionador iterativo de OpenDSS no logra encontrar una solucion estable.

**Como detectarlo:** `engine._solution.Converged` retorna `False`.

**Solucion en la busqueda binaria:**

```python
engine._text.Command = "Solve"
if not engine._solution.Converged:
    # Tratar como violacion: reducir potencia
    high = mid - 1
    continue
```

**Configuracion avanzada del solucionador:**

```python
# Aumentar el numero maximo de iteraciones antes de declarar no-convergencia
engine._text.Command = "Set MaxIter=100"
engine._text.Command = "Set Tolerance=0.0001"
```

---

### Error 3 — `AttributeError: module 'dss' has no attribute 'DSS'`

**Causa:** Se instalo `opendssdirect` pero el codigo usa `import dss` (paquete diferente), o viceversa.

**Verificacion:**

```python
# Forma correcta con opendssdirect (recomendado)
import opendssdirect as dss
dss.Basic.Start(0)

# Forma correcta con el paquete dss
import dss
engine = dss.DSS
engine.Start(0)
```

**Solucion:** estandarizar en `opendssdirect` en todo el proyecto y nunca mezclar los dos paquetes.

---

### Error 4 — Estado corrupto entre requests en el mismo worker

**Causa:** Un request anterior fallo a mitad de la busqueda binaria y dejo el circuito con un generador GD ya aplicado. El siguiente request parte de un estado invalido.

**Solucion:** el metodo `reset_circuit` siempre recarga el circuito completo desde el contenido DSS original, garantizando estado limpio.

```python
# En cada iteracion de la busqueda binaria:
engine.reset_circuit(dss_content, linecodes_content)
# Nunca confiar en el estado previo del motor
```

---

### Error 5 — Timeout de Celery en circuitos grandes

**Causa:** Un circuito con 500+ nodos puede requerir mas de 1 hora de calculo.

**Soluciones:**

1. Aumentar `task_time_limit` en la configuracion de Celery para esos circuitos.
2. Implementar paralelizacion: dividir las barras entre multiples tareas Celery y agregar resultados.
3. Implementar checkpointing: guardar resultados parciales en Redis cada N barras.

```python
# Checkpointing cada 5 barras procesadas
if bus_idx % 5 == 0:
    _save_partial_results(circuit_id, results)
```

---

### Error 6 — `Remove Generator.GD` falla si el generador no existe

**Causa:** El codigo intenta remover un generador que no fue creado (primer request, o despues de un `reset_circuit`).

**Solucion:**

```python
def remove_gd(self):
    generators = [g.lower() for g in list(self._circuit.Generators.AllNames)]
    if "gd" in generators:
        self._text.Command = "Remove Generator.GD"
    # Si no existe, no hacer nada
```

---

### Error 7 — Rutas relativas en archivos DSS

**Causa:** El archivo `.dss` contiene `Redirect IEEELineCodes.dss` o `BusCoords IEEE13Node_BusXY.csv` con rutas relativas que no existen en el servidor.

**Solucion:** el preprocesador `_preprocess` en `DSSEngine` elimina estas referencias automaticamente y gestiona los archivos adjuntos por separado.

```python
content = re.sub(r'(?i).*redirect\s+.*ieeelinecodes.*\.dss.*\n?', '', content)
content = re.sub(r'(?i).*buscoords.*\.csv.*\n?', '', content)
```

---

### Error 8 — Redis se queda sin memoria

**Causa:** Los contenidos DSS y resultados acumulados llenan la memoria de Redis.

**Soluciones:**

```bash
# Configurar limite de memoria y politica de eviccion en docker-compose
command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
```

Los circuitos tienen TTL de 2 horas. Los resultados de hosting capacity se persisten en PostgreSQL y se eliminan de Redis tras la escritura en base de datos.

---

## 14. Guia de Migracion del Codigo Existente

### Paso 1 — Extraer la logica de calculo del archivo Dash

El archivo `Simulacion_DASH_VFinal.py` mezcla logica de calculo con definicion de layout HTML. La migracion consiste en mover cada bloque de calculo al modulo correspondiente del backend:

| Codigo en VFinal.py | Destino en backend |
|---|---|
| Variables globales del motor (lineas 9-12) | `DSSEngine.__init__()` |
| `obtener_loss_table()` | `DSSEngine.get_losses()` |
| `reiniciar_circuito()` | `DSSEngine.reset_circuit()` |
| Captura de voltajes base (lineas 76-93) | `DSSEngine.get_voltage_profile()` |
| Pre-cache de lineas (lineas 100-112) | `DSSEngine._get_lines_info()` |
| Busqueda binaria (lineas 114-181) | `tasks/hosting_task.py::_binary_search()` |
| Callback `actualizar_grafico` | `api/routes/simulation.py::simulate_gd()` |

### Paso 2 — Reemplazar `text.Command = "Redirect ..."` por carga desde string

```python
# ANTES (VFinal.py)
text.Command = "Clear"
text.Command = "Redirect IEEE13Nodeckt.dss"
text.Command = "Solve"

# DESPUES (DSSEngine)
def reset_circuit(self, dss_content: str, ...):
    # Escribe a tempfile, compila, resuelve, limpia tempfile
```

### Paso 3 — Secuencia de comandos Docker para primer arranque

```bash
# 1. Clonar el proyecto backend
git clone https://github.com/usuario/hosting-capacity-backend
cd hosting-capacity-backend

# 2. Copiar variables de entorno
cp .env.example .env
# Editar .env con valores reales

# 3. Construir las imagenes (la primera vez tarda ~5 minutos por la compilacion de opendssdirect)
docker-compose build

# 4. Iniciar todos los servicios
docker-compose up -d

# 5. Verificar que el worker tiene OpenDSS funcionando
docker-compose logs worker | grep "OpenDSS OK"

# 6. Verificar que la API responde
curl http://localhost:8000/api/v1/health

# 7. Ver la documentacion interactiva de la API
# Abrir http://localhost:8000/api/docs en el navegador

# 8. Escalar workers para produccion
docker-compose up --scale worker=3 -d
```

---

*Documento generado: 2026-04-07*  
*Version del informe: 1.0*
