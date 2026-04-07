import base64, os, re, tempfile, io, zipfile
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from dash import dcc, html
# Import dss only when needed
import dss

def _decode_upload(contents: str) -> bytes:
    if "," in contents:
        contents = contents.split(",", 1)[1]
    return base64.b64decode(contents)

def _extract_zip_to_temp(data: bytes) -> str:
    tempdir = Path(tempfile.gettempdir())
    case_dir = tempdir / ("opendss_case_" + next(tempfile._get_candidate_names()))
    case_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(case_dir)
    return str(case_dir)

def _find_main_dss_in_dir(dirpath: str) -> str | None:
    p = Path(dirpath)
    # heuristics: prefer names that include 'IEEE13Nodeckt' or 'Master' or similar
    candidates = sorted(p.rglob("*.dss"))
    priority = sorted([c for c in candidates if "ieee13" in c.name.lower() or "nodeckt" in c.name.lower() or "master" in c.name.lower()])
    if priority:
        return str(priority[0])
    return str(candidates[0]) if candidates else None

def _scan_redirects(dss_text: str) -> list[str]:
    # Capture lines like: Redirect something.dss (case-insensitive)
    redirects = re.findall(r'(?i)^\s*redirect\s+(.+)$', dss_text, flags=re.MULTILINE)
    # Clean quotes and spaces
    return [r.strip().strip('"').strip("'") for r in redirects]

def save_upload_to_temp(contents: str, filename: str) -> str:
    """
    Save uploaded file(s) to temp. If it's a ZIP, extract it and return detected main .dss path.
    If it's a single .dss, save it and return its path.
    """
    data = _decode_upload(contents)
    tempdir = Path(tempfile.gettempdir())

    if filename and filename.lower().endswith(".zip"):
        case_dir = _extract_zip_to_temp(data)
        main_dss = _find_main_dss_in_dir(case_dir)
        if not main_dss:
            raise RuntimeError("El ZIP no contiene archivos .dss.")
        return main_dss

    # Single .dss
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", filename or "circuit.dss")
    path = tempdir / safe_name
    path.write_bytes(data)
    return str(path)

def init_engine():
    engine = dss.DSS
    engine.Start(0)
    text = engine.Text
    circuit = engine.ActiveCircuit
    solution = circuit.Solution
    return engine, text, circuit, solution

def carga_valida(total_power_kw):
    if abs(total_power_kw) < 1e-3:
        return 1e-3
    return abs(total_power_kw)

def reiniciar_circuito_to_file(text, dss_file_path: str):
    # set working dir first so relative Redirects resolve
    p = Path(dss_file_path).resolve()
    text.Command = "Clear"
    text.Command = f'cd "{p.parent}"'
    text.Command = f'Redirect "{p.name}"'
    text.Command = "Solve"

def _verify_includes_exist(dss_file_path: str):
    # If user uploaded only the main .dss, make sure any Redirects are resolvable
    p = Path(dss_file_path)
    text = p.read_text(encoding="utf-8", errors="ignore")
    includes = _scan_redirects(text)
    missing = []
    for inc in includes:
        # Normalize path relative to main file
        inc_path = (p.parent / inc).resolve()
        if not inc_path.exists():
            missing.append(inc)
    return missing

def obtener_loss_table(circuit):
    elementos = []
    tipos = ["Lines", "Transformers", "Capacitors"]

    total_kw = round(circuit.Losses[0] / 1000, 6)
    total_kvar = round(circuit.Losses[1] / 1000, 6)
    carga_total_kw = round(circuit.TotalPower[0] / 1000, 6)

    for tipo in tipos:
        coleccion = getattr(circuit, tipo)
        nombres = list(coleccion.AllNames)
        for nombre in nombres:
            full_name = f"{tipo[:-1]}.{nombre}"
            circuit.SetActiveElement(full_name)
            try:
                perdidas = circuit.ActiveCktElement.Losses
                kw = round(perdidas[0] / 1000, 5)
                kvar = round(perdidas[1] / 1000, 5)
                porcentaje = round((kw / carga_total_kw) * 100, 2) if carga_total_kw else 0
            except Exception:
                kw = kvar = porcentaje = 0.0

            elementos.append([tipo, nombre, kw, porcentaje, kvar])

    resumen = {
        "Pérdidas Totales (kW)": f"{total_kw}",
        "Pérdidas Totales (kvar)": f"{total_kvar}",
        "Potencia Total de Carga (kW)": f"{carga_total_kw}",
    }

    columnas = ["Tipo", "Elemento", "kW Pérdida", "% of Power", "kvar Pérdida"]
    return pd.DataFrame(elementos, columns=columnas), resumen

def preparar_estado_base(dss_file_path: str):
    # Guard: si el archivo principal hace Redirect a otros .dss que no existen, avisar claro
    missing = _verify_includes_exist(dss_file_path)
    if missing:
        raise RuntimeError(
            "Faltan archivos referenciados por el circuito (Redirect): "
            + ", ".join(missing)
            + ". Sube un ZIP con el caso completo o asegúrate de que esos archivos existan junto al .dss principal."
        )

    engine, text, circuit, solution = init_engine()
    reiniciar_circuito_to_file(text, dss_file_path)

    # Pérdidas base (sin GD)
    perdidas_sin_gd_df, resumen_sin_gd = obtener_loss_table(circuit)

    barras = list(circuit.AllBusNames)
    voltajes_dict = {}
    barras_fases_disponibles = {}

    for barra in barras:
        circuit.SetActiveBus(barra)
        pu_volt = circuit.ActiveBus.puVoltages
        nodos = circuit.ActiveBus.Nodes
        barras_fases_disponibles[barra] = list(nodos)
        for idx in range(len(nodos)):
            fase = nodos[idx]
            real = pu_volt[2*idx]
            imag = pu_volt[2*idx + 1]
            mag = round((real**2 + imag**2)**0.5, 6)
            key = f"{barra}.{fase}"
            voltajes_dict[key] = mag

    all_keys = [f"{b}.{f}" for b in barras for f in [1, 2, 3]]
    voltajes_completos = {k: voltajes_dict.get(k, None) for k in all_keys}
    voltajes_df = pd.DataFrame({"Barra.Fase": list(voltajes_completos.keys()),
                                "VoltajePU": list(voltajes_completos.values())})

    lineas_info = []
    for nombre in circuit.Lines.AllNames:
        circuit.Lines.Name = nombre
        fases = circuit.Lines.Phases
        norm_amps = circuit.Lines.EmergAmps or 1.0
        bus1 = circuit.Lines.Bus1.split('.')[0]
        circuit.SetActiveBus(bus1)
        kv_base = circuit.ActiveBus.kVBase or 1.0
        kv = kv_base * 1.732 if fases > 1 else kv_base
        s_nom = kv * norm_amps
        lineas_info.append((nombre, float(norm_amps), round(float(s_nom), 2)))

    limites_gd = []
    for barra_gd in barras:
        circuit.SetActiveBus(barra_gd)
        nodos = sorted(list(circuit.ActiveBus.Nodes))
        kv_ln = circuit.ActiveBus.kVBase
        num_fases = len(nodos)

        if num_fases == 3:
            tipo_gd = "trifasica"
            kv = kv_ln * (3**0.5)
        elif num_fases == 2:
            tipo_gd = "bifasica"
            kv = kv_ln * 2
        else:
            tipo_gd = "monofasica"
            kv = kv_ln

        low, high = 0, 1000000
        best_kw = 0

        while low <= high:
            mid = (low + high) // 2
            reiniciar_circuito_to_file(text, dss_file_path)

            if tipo_gd == "trifasica":
                text.Command = f"New Generator.GD Bus1={barra_gd} Phases=3 kV={kv:.3f} kW={mid} kvar=0 Model=1"
            elif tipo_gd == "bifasica":
                fases_str = ".".join(str(f) for f in nodos)
                text.Command = f"New Generator.GD Bus1={barra_gd}.{fases_str} Phases=2 kV={kv:.3f} kW={mid} kvar=0 Model=1"
            else:
                text.Command = f"New Generator.GD Bus1={barra_gd}.{nodos[0]} Phases=1 kV={kv:.3f} kW={mid} kvar=0 Model=1"
            text.Command = "Solve"

            violacion_voltaje = False
            for b in barras:
                circuit.SetActiveBus(b)
                pu = circuit.ActiveBus.puVoltages
                for i in range(len(circuit.ActiveBus.Nodes)):
                    mag = round((pu[2*i]**2 + pu[2*i+1]**2)**0.5, 6)
                    if mag < 0.95 or mag > 1.05:
                        violacion_voltaje = True
                        break
                if violacion_voltaje:
                    break

            violacion_corriente = False
            violacion_potencia = False
            for nombre, norm_amps, s_nom in lineas_info:
                circuit.Lines.Name = nombre
                circuit.SetActiveElement(f"Line.{nombre}")
                mags = circuit.ActiveCktElement.CurrentsMagAng[::2]
                bus1 = circuit.Lines.Bus1.split('.')[0]
                circuit.SetActiveBus(bus1)
                kv_base = circuit.ActiveBus.kVBase or 1.0
                fases_linea = circuit.Lines.Phases
                for mag in mags:
                    if mag > norm_amps:
                        violacion_corriente = True
                    s_real = (1.732 * kv_base * mag) if fases_linea > 1 else (kv_base * mag)
                    if s_real > s_nom:
                        violacion_potencia = True
                if violacion_corriente or violacion_potencia:
                    break

            if not (violacion_voltaje or violacion_corriente or violacion_potencia):
                best_kw = mid
                low = mid + 1
            else:
                high = mid - 1

        if num_fases == 1:
            limites_gd.append({"Barra": barra_gd, "Fase": nodos[0], "Max GD sin violacion (kW)": best_kw})
        else:
            for fase in nodos:
                limites_gd.append({"Barra": barra_gd, "Fase": fase, "Max GD sin violacion (kW)": best_kw})

    limites_df = pd.DataFrame(limites_gd)
    if not limites_df.empty:
        limites_pivot = limites_df.pivot(index='Barra', columns='Fase',
                                         values='Max GD sin violacion (kW)').sort_index().fillna('NULL')
        limites_pivot_dict = limites_pivot.to_dict()
    else:
        limites_pivot_dict = {}

    return {
        "barras": barras,
        "barras_fases_disponibles": barras_fases_disponibles,
        "voltajes": voltajes_df.to_dict("records"),
        "limites_pivot": limites_pivot_dict,
        "perdidas_sin_gd_df": perdidas_sin_gd_df.to_dict("records"),
        "resumen_sin_gd": resumen_sin_gd,
        "lineas_info": lineas_info,
    }

def figura_voltajes(state):
    df = pd.DataFrame(state["voltajes"])
    fig = go.Figure(
        data=[go.Bar(x=df["Barra.Fase"], y=df["VoltajePU"])],
        layout=go.Layout(yaxis=dict(title="Voltaje PU"), xaxis=dict(title="Barra.Fase"))
    )
    return fig

def html_tabla_limites(state):
    from dash import html
    if not state.get("limites_pivot"):
        return html.P("No se calcularon límites.", className="text-muted")

    import pandas as pd
    limites_pivot = pd.DataFrame(state["limites_pivot"])
    limites_pivot = limites_pivot.sort_index(axis=0).sort_index(axis=1)
    headers = ["Barra"] + [f"Fase {f}" for f in limites_pivot.columns]

    body_rows = []
    for barra in limites_pivot.index:
        row = [html.Td(barra)]
        for f in limites_pivot.columns:
            row.append(html.Td(limites_pivot.loc[barra][f]))
        body_rows.append(html.Tr(row))

    table = html.Table([
        html.Thead(html.Tr([html.Th(h) for h in headers])),
        html.Tbody(body_rows)
    ], className="table table-bordered table-hover")
    return table


def aplicar_gd(dss_file_path: str, barra: str, tipo: list, fases_sel, kw: float):
    """
    Aplica una GD según selecciones del usuario y devuelve:
      - fig_comparativo (go.Figure)
      - tabla_violaciones (html element)
      - tabla_perdidas (html element)
      - mensaje (str) si hay validaciones
    """
    from dash import html
    engine, text, circuit, solution = init_engine()

    # 1) Estado base (sin GD)
    reiniciar_circuito_to_file(text, dss_file_path)
    barras = list(circuit.AllBusNames)

    # Capturar voltajes base por fase
    base_por_fase = {1: {}, 2: {}, 3: {}}
    for b in barras:
        circuit.SetActiveBus(b)
        pu = circuit.ActiveBus.puVoltages
        nodes_b = circuit.ActiveBus.Nodes
        for idx in range(len(nodes_b)):
            f = nodes_b[idx]
            real = pu[2*idx]
            imag = pu[2*idx + 1]
            mag = round((real**2 + imag**2)**0.5, 6)
            key = f"{b}.{f}"
            base_por_fase[f][key] = mag

    perdidas_sin_gd_df, resumen_sin_gd = obtener_loss_table(circuit)

    # 2) Validar inputs
    if not barra:
        return go.Figure(), html.P("Seleccione una barra."), html.P(""), "Seleccione una barra."
    circuit.SetActiveBus(barra)
    fases_disponibles = sorted(list(circuit.ActiveBus.Nodes))
    kv_ln = circuit.ActiveBus.kVBase
    kv_ll = kv_ln * (3**0.5) if len(fases_disponibles) > 1 else kv_ln

    # Normaliza tipo
    tipo = tipo or []
    if "trifasica" in tipo:
        if fases_disponibles != [1, 2, 3]:
            return go.Figure(), html.P("La barra seleccionada no tiene 3 fases disponibles para GD trifásica.", className="text-danger"), html.P(""), "Barra sin 3 fases."
        bus_spec = f"{barra}"
        phases = 3
        kv = kv_ll
    elif "bifasica" in tipo:
        if not isinstance(fases_sel, (list, tuple)) or len(fases_sel) != 2 or not all(f in fases_disponibles for f in fases_sel):
            return go.Figure(), html.P("Debe seleccionar exactamente dos fases válidas para GD bifásica.", className="text-danger"), html.P(""), "Fases inválidas."
        fases_str = ".".join(str(f) for f in fases_sel)
        bus_spec = f"{barra}.{fases_str}"
        phases = 2
        kv = kv_ll
    else:
        # monofásica
        if not fases_disponibles:
            return go.Figure(), html.P("La barra no tiene fases disponibles.", className="text-danger"), html.P(""), "Sin fases."
        fase = fases_sel if isinstance(fases_sel, int) else (fases_sel[0] if fases_sel else fases_disponibles[0])
        if fase not in fases_disponibles:
            fase = fases_disponibles[0]
        bus_spec = f"{barra}.{fase}"
        phases = 1
        kv = kv_ln

    # 3) Aplicar GD y resolver
    reiniciar_circuito_to_file(text, dss_file_path)
    # elimina preexistente si la hubiera
    try:
        text.Command = "Edit Generator.GD enabled=no"
    except Exception:
        pass
    text.Command = f'New Generator.GD Bus1={bus_spec} Phases={phases} kV={kv:.3f} kW={float(kw)} kvar=0.0 Model=1'
    text.Command = "Solve"

    # 4) Estado con GD
    gd_por_fase = {1: {}, 2: {}, 3: {}}
    for b in barras:
        circuit.SetActiveBus(b)
        pu = circuit.ActiveBus.puVoltages
        nodes_b = circuit.ActiveBus.Nodes
        for idx in range(len(nodes_b)):
            f = nodes_b[idx]
            real = pu[2*idx]
            imag = pu[2*idx + 1]
            mag = round((real**2 + imag**2)**0.5, 6)
            key = f"{b}.{f}"
            gd_por_fase[f][key] = mag

    perdidas_con_gd_df, resumen_con_gd = obtener_loss_table(circuit)

    # 5) Violaciones de voltaje, corriente y potencia
    violaciones = []
    for fase_i in [1, 2, 3]:
        for key, valor in gd_por_fase[fase_i].items():
            if valor is None:
                continue
            if valor < 0.95 or valor > 1.05:
                violaciones.append({"Barra.Fase": key, "Voltaje con GD (PU)": valor})
    violaciones_df = pd.DataFrame(violaciones)

    # Corriente/potencia
    violaciones_corriente = []
    violaciones_potencia = []
    # Inferir lineas_info de nuevo (similar a preparar_estado_base)
    lineas_info = []
    for nombre in circuit.Lines.AllNames:
        circuit.Lines.Name = nombre
        fases = circuit.Lines.Phases
        norm_amps = circuit.Lines.EmergAmps or 1.0
        bus1 = circuit.Lines.Bus1.split('.')[0]
        circuit.SetActiveBus(bus1)
        kv_base = circuit.ActiveBus.kVBase or 1.0
        kv_nom = kv_base * 1.732 if fases > 1 else kv_base
        s_nom = kv_nom * norm_amps
        lineas_info.append((nombre, float(norm_amps), round(float(s_nom), 2)))

    for nombre, norm_amps, s_nom in lineas_info:
        circuit.Lines.Name = nombre
        circuit.SetActiveElement(f"Line.{nombre}")
        mags = circuit.ActiveCktElement.CurrentsMagAng[::2]
        bus1 = circuit.Lines.Bus1.split('.')[0]
        circuit.SetActiveBus(bus1)
        kv_base = circuit.ActiveBus.kVBase or 1.0
        fases_linea = circuit.Lines.Phases
        for i, mag in enumerate(mags):
            if mag > norm_amps:
                violaciones_corriente.append({
                    "Línea": nombre, "Fase": i+1, "Corriente (A)": round(mag,2), "Límite (A)": round(norm_amps,2)
                })
            s_real = (1.732 * kv_base * mag) if fases_linea > 1 else (kv_base * mag)
            if s_real > s_nom:
                violaciones_potencia.append({
                    "Línea": nombre, "Fase": i+1, "Potencia (kVA)": round(s_real,2), "Límite (kVA)": round(s_nom,2)
                })

    # 6) Armar salidas
    # Figura comparativa (por fase) base vs GD con límites 0.95–1.05
    fig = go.Figure()
    for fase_i in [1,2,3]:
        if not base_por_fase[fase_i] and not gd_por_fase[fase_i]:
            continue
        df_base = pd.DataFrame({"Barra.Fase": list(base_por_fase[fase_i].keys()), "Sin GD": list(base_por_fase[fase_i].values())})
        df_gd = pd.DataFrame({"Barra.Fase": list(gd_por_fase[fase_i].keys()), "Con GD": list(gd_por_fase[fase_i].values())})
        df = pd.merge(df_base, df_gd, on="Barra.Fase", how="outer")
        df = df.sort_values("Barra.Fase")
        fig.add_bar(x=df["Barra.Fase"], y=df["Sin GD"], name=f"Fase {fase_i} - Sin GD")
        fig.add_bar(x=df["Barra.Fase"], y=df["Con GD"], name=f"Fase {fase_i} - Con GD")
    fig.add_hline(y=1.05, line_dash="dash", annotation_text="1.05 pu", annotation_position="top left")
    fig.add_hline(y=0.95, line_dash="dash", annotation_text="0.95 pu", annotation_position="bottom left")
    fig.update_layout(barmode="group", title="Comparativo Voltaje PU (Sin GD vs Con GD)", yaxis_title="Voltaje PU")

    # Tabla de violaciones de voltaje
    if not violaciones_df.empty:
        tabla_volt = html.Table([
            html.Thead(html.Tr([html.Th(c) for c in violaciones_df.columns])),
            html.Tbody([html.Tr([html.Td(str(v)) for v in row]) for row in violaciones_df.values])
        ], className="table table-bordered table-hover")
    else:
        tabla_volt = html.P("No se detectaron violaciones de voltaje con la GD aplicada.", className="text-muted")

    # Tabla de pérdidas y resumen (con y sin GD)
    resumen_fig = go.Figure()
    resumen_fig.add_bar(name="Con GD", x=["Pérdidas kW","Pérdidas kvar"],
                        y=[float(resumen_con_gd["Pérdidas Totales (kW)"]), float(resumen_con_gd["Pérdidas Totales (kvar)"])])
    resumen_fig.add_bar(name="Sin GD", x=["Pérdidas kW","Pérdidas kvar"],
                        y=[float(resumen_sin_gd["Pérdidas Totales (kW)"]), float(resumen_sin_gd["Pérdidas Totales (kvar)"])])
    resumen_fig.update_layout(barmode="group", title="Resumen de Pérdidas Totales")

    tabla_perdidas = html.Div([
        html.H5("Resumen del Sistema con GD"),
        html.Ul([html.Li([html.Strong(k + ": "), str(v)]) for k, v in resumen_con_gd.items()]),
        html.H5("Resumen del Sistema sin GD"),
        html.Ul([html.Li([html.Strong(k + ": "), str(v)]) for k, v in resumen_sin_gd.items()]),
        dcc.Graph(figure=resumen_fig)
    ])

    # Combinar violaciones corriente y potencia
    bloques = []
    if violaciones_corriente:
        vcd = pd.DataFrame(violaciones_corriente)
        bloques.append(html.Div([
            html.H5("Violaciones de Corriente"),
            html.Table([html.Thead(html.Tr([html.Th(c) for c in vcd.columns])),
                        html.Tbody([html.Tr([html.Td(str(v)) for v in row]) for row in vcd.values])],
                       className="table table-bordered table-hover")
        ]))
    if violaciones_potencia:
        vpd = pd.DataFrame(violaciones_potencia)
        bloques.append(html.Div([
            html.H5("Violaciones de Potencia"),
            html.Table([html.Thead(html.Tr([html.Th(c) for c in vpd.columns])),
                        html.Tbody([html.Tr([html.Td(str(v)) for v in row]) for row in vpd.values])],
                       className="table table-bordered table-hover")
        ]))
    tabla_violaciones = html.Div(bloques) if bloques else html.P("No se detectaron violaciones de corriente/potencia.", className="text-muted")

    return fig, tabla_volt if bloques==[] else html.Div([tabla_volt, html.Hr(), tabla_violaciones]), tabla_perdidas, ""
