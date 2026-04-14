# IEEE 13 Bus — Dashboard de Hosting Capacity

Dashboard interactivo para analisis de capacidad de alojamiento de generacion distribuida sobre el circuito IEEE 13 Nodos, usando OpenDSS como motor de simulacion y Dash como interfaz web.

---

## Requisitos del sistema

- macOS (Apple Silicon M1/M2/M3 o Intel)
- Python 3.11 (recomendado; 3.13 tiene conflictos con algunas dependencias)
- El archivo `IEEE13Nodeckt.dss` debe estar en este mismo directorio

---

## Instalacion y primer arranque

Todos los comandos se ejecutan desde este directorio (`13Bus/`).

### 1. Crear el entorno virtual

```bash
python3 -m venv venv
source venv/bin/activate
```

Verificar que el entorno esta activo:

```bash
which python
# debe mostrar: .../13Bus/venv/bin/python
```

### 2. Instalar dependencias

```bash
pip install "opendssdirect.py" dash dash-bootstrap-components plotly pandas
```

> **Importante:** instalar `opendssdirect.py` (con ese nombre exacto, incluidas las comillas). Este paquete actualiza automaticamente el paquete `dss` a la version correcta (`dss-python >= 0.15`). Si se instala solo `dss==0.8` sin `opendssdirect.py`, el motor no funciona en macOS.

### 3. Verificar que OpenDSS funciona

```bash
python -c "
import dss
engine = dss.DSS
engine.Start(0)
text = engine.Text
text.Command = 'Clear'
text.Command = 'Redirect IEEE13Nodeckt.dss'
text.Command = 'Solve'
circuit = engine.ActiveCircuit
print('Buses:', len(circuit.AllBusNames))
print('Converged:', circuit.Solution.Converged)
print('OK - OpenDSS funciona correctamente')
"
```

Salida esperada:
```
Buses: 16
Converged: True
OK - OpenDSS funciona correctamente
```

### 4. Arrancar la aplicacion

```bash
python Simulacion_DASH_VFinal.py
```

Abrir en el navegador: [http://127.0.0.1:8050](http://127.0.0.1:8050)

> **Advertencia:** al arrancar, la aplicacion ejecuta automaticamente la busqueda binaria de hosting capacity para todas las barras del circuito. Esto puede tardar entre **3 y 10 minutos** segun el hardware. Durante ese tiempo la terminal no muestra progreso y el navegador puede aparecer cargando. Es comportamiento normal.

---

## Arranques posteriores

Una vez instalado el entorno, para volver a correr la aplicacion:

```bash
cd /ruta/al/proyecto/OpenDSS/IEEETestCases/13Bus
source venv/bin/activate
python Simulacion_DASH_VFinal.py
```

---

## Si el puerto 8050 ya esta en uso

```bash
lsof -ti :8050 | xargs kill -9
python Simulacion_DASH_VFinal.py
```

---

## Dependencias instaladas

| Paquete | Version instalada | Uso |
|---|---|---|
| `opendssdirect.py` | 0.9.4 | Motor de simulacion OpenDSS (cross-platform) |
| `dss-python` | 0.15.7 | Backend nativo de OpenDSS (instalado por opendssdirect) |
| `dss-python-backend` | 0.14.5 | Binarios compilados para macOS arm64/x86_64 |
| `dash` | 4.1.0 | Framework web del dashboard |
| `dash-bootstrap-components` | 2.0.4 | Componentes Bootstrap para Dash |
| `plotly` | 6.6.0 | Graficos interactivos |
| `pandas` | 3.0.2 | Manipulacion de datos |
| `cffi` | 2.0.0 | Interfaz C para los binarios de OpenDSS |

---

## Cambios realizados al codigo para compatibilidad con macOS

### Archivo modificado: `Simulacion_DASH_VFinal.py`

#### Cambio 1 — Linea 597: parametros de arranque del servidor

**Problema:** con `debug=True`, Dash lanza un proceso hijo para el hot-reloader que en macOS genera semaforos que no se liberan correctamente al cerrar. Ademas, el modo threaded por defecto de Flask provoca un crash `illegal hardware instruction` en Apple Silicon porque el motor OpenDSS se inicializa en el hilo principal y los callbacks lo llaman desde hilos secundarios; OpenDSS no es thread-safe.

**Antes:**
```python
if __name__ == '__main__':
    app.run(debug=True)
```

**Despues:**
```python
if __name__ == '__main__':
    app.run(debug=False, use_reloader=False, threaded=False)
```

| Parametro | Valor | Razon |
|---|---|---|
| `debug=False` | False | Elimina el proceso hijo del hot-reloader; evita el warning de semaforos en macOS |
| `use_reloader=False` | False | Desactiva explicitamente el file watcher que causa el proceso extra |
| `threaded=False` | False | Fuerza atencion de requests en el hilo principal donde vive el motor OpenDSS; evita el crash `illegal hardware instruction` en Apple Silicon |

> **Nota para el backend en produccion:** `threaded=False` hace que la app atienda un solo request a la vez. Esto es aceptable para uso local pero no para produccion con multiples usuarios. La arquitectura FastAPI + Celery planificada resuelve esto correctamente usando procesos separados en lugar de threads.

---

## Estructura de archivos relevantes

```
13Bus/
├── IEEE13Nodeckt.dss          # Definicion del circuito (no modificar)
├── Simulacion_DASH_VFinal.py  # Aplicacion principal (modificada, ver arriba)
├── venv/                      # Entorno virtual Python (no subir a git)
├── README.md                  # Este archivo
└── Modular/                   # Version modular alternativa (ver abajo)
```

---

## Version alternativa: Modular (arranque rapido)

Si se quiere explorar la interfaz sin esperar el calculo de hosting capacity, la version Modular arranca en segundos y permite subir el archivo DSS desde el navegador. Los limites de GD que muestra son aproximados (1000 kW fijo por barra), no calculados por busqueda binaria.

```bash
cd Modular
python app.py
```

Abrir en: [http://127.0.0.1:8050](http://127.0.0.1:8050)

Esta version requiere el mismo entorno virtual y dependencias de la version principal.
