# Endpoints — Ubicacion en el Codigo Existente

Mapa de cada endpoint propuesto en `ROAD_TO_BACKEND.md` hacia la funcion y archivo del proyecto actual donde ya existe la logica equivalente. El objetivo es **reorganizar, no reescribir**.

---

## Referencia rapida de archivos clave

| Alias | Ruta completa |
|---|---|
| `VFinal` | `OpenDSS/IEEETestCases/13Bus/Simulacion_DASH_VFinal.py` |
| `PowerBI` | `PROGRAMA DINAMICO/dss_powerbi.py.py` |
| `Modular/app` | `OpenDSS/IEEETestCases/13Bus/Modular/app.py` |
| `Modular/analyzer` | `OpenDSS/IEEETestCases/13Bus/Modular/analysis_module.py` |
| `Modular/engine` | `OpenDSS/IEEETestCases/13Bus/Modular/opendss/dss_engine.py` |
| `Modular/analysis` | `OpenDSS/IEEETestCases/13Bus/Modular/opendss/analysis.py` |
| `Modular/gd` | `OpenDSS/IEEETestCases/13Bus/Modular/opendss/gd_analysis.py` |
| `Modular/callbacks` | `OpenDSS/IEEETestCases/13Bus/Modular/components/callbacks.py` |
| `Modular/helpers` | `OpenDSS/IEEETestCases/13Bus/Modular/utils/helpers.py` |

---

## Grupo 1 — Gestion de Circuito

---

### `POST /api/v1/circuit/upload`

Sube, valida y compila un archivo DSS.

| Funcion | Archivo | Lineas | Notas |
|---|---|---|---|
| `handle_multiple_file_upload()` | `Modular/app` | 60-123 | Decodifica base64, valida extension, almacena en `dcc.Store` |
| `process_dss_files()` | `Modular/app` | 159-178 | Instancia `OpenDSSAnalyzer` y llama a `ejecutar_analisis_completo()` |
| `OpenDSSAnalyzer.reiniciar_circuito()` | `Modular/analyzer` | 36-81 | Escribe tempfile, ejecuta `Clear → Compile → Solve`, limpia tempfile |
| `load_dss_files()` | `Modular/engine` | 172-195 | Alternativa; preprocesa contenido y compila via `text.Command` |
| `preprocess_dss_content()` | `Modular/engine` | 156-164 | Elimina `redirect IEEELineCodes.dss` y `buscoords .csv` del contenido |
| `clean_dss_content()` | `Modular/engine` | 136-154 | Elimina el parametro `basekv` invalido de linecodes |
| `clean_dss_content()` | `Modular/helpers` | 3-23 | Version alternativa del mismo preprocesador |

---

### `GET /api/v1/circuit/{circuit_id}`

Retorna informacion basica del circuito compilado.

| Funcion | Archivo | Lineas | Notas |
|---|---|---|---|
| `OpenDSSAnalyzer.ejecutar_analisis_completo()` | `Modular/analyzer` | 206-248 | Retorna dict con clave `circuit_info` que contiene name, num_buses, num_elements, converged, total_power_kw/kvar |
| Variables globales: `barras`, `barras_fases_disponibles` | `VFinal` | 71-93 | Equivalente en la version monolitica; calculado al arrancar |

---

### `DELETE /api/v1/circuit/{circuit_id}`

Elimina el circuito de la sesion/cache.

| Funcion | Archivo | Lineas | Notas |
|---|---|---|---|
| `reiniciar_circuito()` | `VFinal` | 62-66 | Solo hace `Clear`; no hay logica de eliminacion de sesion en el codigo actual — **requiere implementacion nueva** (solo el comando Redis `DEL`) |

---

## Grupo 2 — Analisis Base

---

### `GET /api/v1/circuit/{circuit_id}/analysis/voltage-profile`

Perfil de voltajes PU de todas las barras en estado base.

| Funcion | Archivo | Lineas | Notas |
|---|---|---|---|
| `OpenDSSAnalyzer.obtener_perfil_voltajes()` | `Modular/analyzer` | 83-123 | Version con manejo de errores, logging y DataFrame completo con `None` para fases inexistentes |
| `obtener_perfil_voltajes(circuit)` | `Modular/analysis` | 3-28 | Version funcional standalone; recibe el objeto `circuit` como parametro |
| Variables globales `voltajes_dict`, `voltajes_df` | `VFinal` | 76-93 | Version inline sin funcion; calcula lo mismo al arrancar la app |

---

### `GET /api/v1/circuit/{circuit_id}/analysis/losses`

Tabla de perdidas por elemento (Lines, Transformers, Capacitors).

| Funcion | Archivo | Lineas | Notas |
|---|---|---|---|
| `obtener_loss_table()` | `VFinal` | 20-60 | Version standalone; opera sobre estado global del motor |
| `OpenDSSAnalyzer.obtener_loss_table()` | `Modular/analyzer` | 125-171 | Version con manejo de errores por elemento; actualiza `self.resumen_sin_gd` |

Ambas retornan: `DataFrame(["Tipo", "Elemento", "kW Perdida", "% of Power", "kvar Perdida"])` + dict resumen.

---

### `GET /api/v1/circuit/{circuit_id}/analysis/lines`

Informacion de lineas: fases, limites de corriente y potencia nominal.

| Funcion | Archivo | Lineas | Notas |
|---|---|---|---|
| Pre-cache de lineas (bloque inline) | `VFinal` | 100-112 | Llena la lista global `lineas_info` con `(nombre, norm_amps, s_nom)` al arrancar |
| Bloque equivalente dentro de `analizar_limites_gd()` | `Modular/gd` | 8-19 | Mismo calculo; encapsulado dentro de la funcion de analisis GD |

No existe una funcion dedicada y standalone para este endpoint — **el bloque de calculo debe extraerse** de `VFinal` lineas 100-112 como funcion propia.

---

## Grupo 3 — Simulacion con GD

---

### `POST /api/v1/circuit/{circuit_id}/simulate`

Aplica una GD al circuito y retorna analisis comparativo completo (voltajes, perdidas, violaciones).

| Funcion | Archivo | Lineas | Notas |
|---|---|---|---|
| `actualizar_grafico()` (callback) | `VFinal` | 310-594 | Logica completa: valida fases, captura base, aplica GD, verifica violaciones, compara perdidas, genera figuras. Es la funcion mas completa. |
| `simular_gd()` (callback) | `Modular/callbacks` | 40-178 | Version modular; usa `OpenDSSAnalyzer`; logica equivalente pero separada del layout |
| `ejecutar_simulacion()` | `PowerBI` | 44-79 | Version para Power BI; retorna dict JSON estructurado — **la mas cercana al contrato REST** |
| `aplicar_generador()` | `Modular/helpers` | 32-49 | Funcion auxiliar standalone para crear el `Generator.GD`; reutilizable directamente |
| `agregar_generacion_distribuida()` | `PowerBI` | 31-42 | Alternativa; detecta automaticamente el numero de fases de la barra |

**Sub-logica de deteccion de violaciones dentro de `actualizar_grafico()`:**

| Logica | Archivo | Lineas |
|---|---|---|
| Violaciones de voltaje (< 0.95 o > 1.05 PU) | `VFinal` | 419-425 |
| Violaciones de corriente (> NormAmps) | `VFinal` | 363-375 |
| Violaciones de potencia (> S_nominal) | `VFinal` | 378-398 |
| `verificar_violaciones_voltaje()` | `Modular/gd` | 87-99 |
| `verificar_violaciones_corriente_potencia()` | `Modular/gd` | 101-133 |

---

## Grupo 4 — Hosting Capacity

---

### `POST /api/v1/circuit/{circuit_id}/hosting-capacity` (dispara tarea asincrona)

Inicia la busqueda binaria de hosting capacity para todas las barras.

| Funcion | Archivo | Lineas | Notas |
|---|---|---|---|
| Busqueda binaria (bloque inline global) | `VFinal` | 114-181 | Implementacion completa y funcional; corre al arrancar la app, no en un endpoint. Verifica voltaje y corriente. |
| `analizar_limites_gd(circuit, text)` | `Modular/gd` | 4-79 | Version encapsulada con verificacion de voltaje + corriente + potencia. **La mas completa y lista para extraer como tarea Celery.** |
| `_binary_search()` (sub-logica interna) | `Modular/gd` | 46-68 | El loop `while low <= high` con reinicio de circuito y chequeo de violaciones |
| `OpenDSSAnalyzer.analizar_limites_gd()` | `Modular/analyzer` | 173-204 | Version **simplificada** (valor fijo 1000 kW); NO usa busqueda binaria real — no apta para produccion |

---

### `GET /api/v1/circuit/{circuit_id}/hosting-capacity`

Retorna la tabla completa de hosting capacity calculada.

| Funcion / Variable | Archivo | Lineas | Notas |
|---|---|---|---|
| `limites_gd` (lista global) | `VFinal` | 95, 181 | Resultado de la busqueda binaria; `List[{"Barra", "Fase", "Max GD sin violacion (kW)"}]` |
| `limites_df`, `limites_pivot` | `VFinal` | 209-210 | DataFrame y tabla pivot lista para mostrar |
| Retorno de `analizar_limites_gd()` | `Modular/gd` | 73-78 | Mismo formato de lista |
| Clave `limites_gd` en retorno de `ejecutar_analisis_completo()` | `Modular/analyzer` | 229 | Almacenado en `dcc.Store` en la version Modular |

---

### `GET /api/v1/circuit/{circuit_id}/hosting-capacity/{bus}`

Hosting capacity filtrado por una barra especifica.

| Funcion / Variable | Archivo | Lineas | Notas |
|---|---|---|---|
| Misma fuente que el endpoint anterior, filtrado por `barra == bus` | `VFinal` | 181 | No existe funcion separada; es un filtro sobre `limites_gd` |
| `violaciones_corriente_por_barra_fase` | `VFinal` | 96, 183-207 | Dict con las violaciones de corriente del caso limite por cada (barra, fase) |

---

## Grupo 5 — Tareas Asincronas

---

### `GET /api/v1/tasks/{task_id}/status`
### `DELETE /api/v1/tasks/{task_id}`

No existe equivalente en el codigo actual. El codigo actual es sincrono: la busqueda binaria bloquea el hilo principal al arrancar.

**Logica a migrar:** el bloque `VFinal` lineas 114-181 (o `Modular/gd analizar_limites_gd()`) debe moverse a una tarea Celery. El sistema de polling y estado de tarea es nuevo.

---

## Grupo 6 — Exportacion

---

### `GET /api/v1/circuit/{circuit_id}/export/excel`

Exporta resultados a archivo Excel.

| Funcion | Archivo | Lineas | Notas |
|---|---|---|---|
| Bloque `pd.ExcelWriter` | `PowerBI` | 92-100 | Escribe tres hojas: `Voltajes`, `Perdidas`, `Violaciones` en `resultados_temp.xlsx` — logica directamente reutilizable |

---

### `GET /api/v1/circuit/{circuit_id}/export/json`

Exporta resultados a JSON.

| Funcion | Archivo | Lineas | Notas |
|---|---|---|---|
| `print(json.dumps(...))` | `PowerBI` | 103-107 | Serializa voltajes, perdidas y violaciones; es stdout pero el dict es reutilizable |
| Retorno de `ejecutar_simulacion()` | `PowerBI` | 61-78 | Dict estructurado con `config`, `voltajes`, `perdidas`, `violaciones` — **contrato JSON mas limpio del proyecto** |
| Retorno de `ejecutar_analisis_completo()` | `Modular/analyzer` | 227-244 | Dict completo con todos los resultados del analisis base |

---

## Resumen de cobertura

| Endpoint | Logica existe | Archivo mas completo | Estado |
|---|---|---|---|
| `POST /circuit/upload` | Si | `Modular/app` + `Modular/analyzer` | Listo para extraer |
| `GET /circuit/{id}` | Si | `Modular/analyzer` L206-248 | Listo para extraer |
| `DELETE /circuit/{id}` | No | — | Solo requiere `DEL` en Redis |
| `GET /analysis/voltage-profile` | Si | `Modular/analyzer` L83-123 | Listo para extraer |
| `GET /analysis/losses` | Si | `Modular/analyzer` L125-171 | Listo para extraer |
| `GET /analysis/lines` | Parcial | `VFinal` L100-112 (inline) | Requiere extraer como funcion |
| `POST /simulate` | Si | `VFinal` L310-594 | Requiere separar logica de calculo del HTML |
| `POST /hosting-capacity` (async) | Si | `Modular/gd` L4-79 | Requiere mover a tarea Celery |
| `GET /hosting-capacity` | Si | `VFinal` L209-210 | Listo para extraer |
| `GET /hosting-capacity/{bus}` | Parcial | `VFinal` L181 | Filtro simple sobre lista existente |
| `GET /tasks/{id}/status` | No | — | Nuevo; lo provee Celery nativo |
| `DELETE /tasks/{id}` | No | — | Nuevo; `celery.control.revoke()` |
| `GET /export/excel` | Si | `PowerBI` L92-100 | Listo para extraer |
| `GET /export/json` | Si | `PowerBI` L61-78 | Listo para extraer |
