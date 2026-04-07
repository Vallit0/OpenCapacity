import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objs as go
import dss
import pandas as pd

# Inicializar OpenDSS
engine = dss.DSS
engine.Start(0)
text = engine.Text
circuit = engine.ActiveCircuit
solution = circuit.Solution

def reiniciar_circuito():
    text.Command = "Clear"
    text.Command = "Redirect IEEE13Nodeckt.dss"
    text.Command = "Solve"

reiniciar_circuito()

barras = circuit.AllBusNames
voltajes_dict = {}
barras_fase = {}
barras_fases_disponibles = {}

for barra in barras:
    circuit.SetActiveBus(barra)
    pu_volt = circuit.ActiveBus.puVoltages
    nodos = circuit.ActiveBus.Nodes
    barras_fases_disponibles[barra] = nodos
    fases = len(pu_volt) // 2
    barras_fase[barra] = fases
    for idx in range(len(nodos)):
        fase = nodos[idx]
        real = pu_volt[2*idx]
        imag = pu_volt[2*idx + 1]
        mag = round((real**2 + imag**2)**0.5, 6)
        key = f"{barra}.{fase}"
        voltajes_dict[key] = mag

all_keys = [f"{b}.{f}" for b in barras for f in [1, 2, 3]]
voltajes_completos = {k: voltajes_dict.get(k, None) for k in all_keys}
voltajes_df = pd.DataFrame({"Barra.Fase": voltajes_completos.keys(), "VoltajePU": voltajes_completos.values()})

limites_gd = []

for barra_gd in barras:
    circuit.SetActiveBus(barra_gd)
    nodos = circuit.ActiveBus.Nodes
    for fase in nodos:
        limite_kw = 0
        for kw in range(500, 200000, 500):
            reiniciar_circuito()
            circuit.SetActiveBus(barra_gd)
            kv_ln = circuit.ActiveBus.kVBase
            text.Command = f"New Generator.GD Bus1={barra_gd}.{fase} Phases=1 kV={kv_ln:.3f} kW={kw} kvar=0 Model=1"
            text.Command = "Solve"
            violacion = False
            for b in barras:
                circuit.SetActiveBus(b)
                pu = circuit.ActiveBus.puVoltages
                nodes_b = circuit.ActiveBus.Nodes
                for idx in range(len(nodes_b)):
                    f = nodes_b[idx]
                    real = pu[2*idx]
                    imag = pu[2*idx + 1]
                    mag = round((real**2 + imag**2)**0.5, 6)
                    if mag < 0.95 or mag > 1.05:
                        violacion = True
                        break
                if violacion:
                    break
            if violacion:
                break
            limite_kw = kw
        limites_gd.append({"Barra": barra_gd, "Fase": fase, "Max GD sin violacion (kW)": limite_kw})

limites_df = pd.DataFrame(limites_gd)
limites_pivot = limites_df.pivot(index='Barra', columns='Fase', values='Max GD sin violacion (kW)').sort_index().fillna('NULL')

app = dash.Dash(__name__)
app.title = "Dashboard OpenDSS"

external_stylesheets = ["https://cdn.jsdelivr.net/npm/bootswatch@5.3.3/dist/flatly/bootstrap.min.css"]
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
app.title = "Dashboard OpenDSS"

app.layout = html.Div([
    html.Div([
        html.H2("Perfil de Voltaje por Barra y Fase", className="text-center mb-4 mt-4"),
        dcc.Graph(id='grafico-voltajes',
                  figure=go.Figure(
                      data=[go.Bar(x=voltajes_df["Barra.Fase"], y=voltajes_df["VoltajePU"])],
                      layout=go.Layout(yaxis=dict(title="Voltaje PU"), xaxis=dict(title="Barra.Fase"))
                  ),
                  className="mb-4")
    ], className="container"),

    html.Div([
        html.H4("Límite máximo de generación distribuida sin causar violaciones", className="mt-4"),
        html.Div([
            html.Table([
                html.Thead([
                    html.Tr([html.Th("Barra")] + [html.Th(f"Fase {f}") for f in sorted(limites_pivot.columns)])
                ]),
                html.Tbody([
                    html.Tr([
                        html.Td(barra)
                    ] + [html.Td(limites_pivot.loc[barra][f]) if f in limites_pivot.columns else html.Td("NULL") for f in sorted(limites_pivot.columns)])
                    for barra in limites_pivot.index
                ])
            ], className="table table-bordered table-hover")
        ])
    ], className="container"),

    html.Hr(),

    html.Div([
        html.Label("Selecciona la barra para insertar GD:", className="form-label mt-3"),
        dcc.Dropdown(id='barra-gd', options=[{"label": b, "value": b} for b in barras], className="mb-2"),

        html.Div(id='info-barra', style={'marginBottom': '1em', 'fontWeight': 'bold'}),

        html.Label("Selecciona la fase disponible (opcional si GD trifásica o bifásica):", className="form-label"),
        dcc.Dropdown(id='fase-gd', value=None, multi=True, className="mb-2"),

        html.Label("Tipo de GD:", className="form-label"),
        dcc.Checklist(
            id='tipo-gd',
            options=[
                {"label": "Trifásica", "value": "trifasica"},
                {"label": "Bifásica", "value": "bifasica"}
            ],
            value=[],
            inputStyle={"margin-right": "5px"},
            labelStyle={"margin-right": "15px"},
            className="mb-3"
        ),

        html.Label("Potencia GD (kW):", className="form-label"),
        dcc.Input(id='potencia-gd', type='number', min=0, max=200000, #step=100, 
                  value=100, className="form-control mb-3"),

        html.Button("Aplicar GD", id='btn-aplicar', n_clicks=0, className="btn btn-primary")
    ], className="container"),

    html.Div(id='mensaje-validacion', style={'color': 'red'}, className="container mt-3"),

    html.Div([
        dcc.Graph(id='grafico-comparativo')
    ], className="container mt-4")
])

@app.callback(
    Output('fase-gd', 'options'),
    Output('fase-gd', 'value'),
    Output('info-barra', 'children'),
    Input('barra-gd', 'value')
)
def actualizar_fases(barra):
    if barra is None:
        return [], None, ""
    fases = barras_fases_disponibles.get(barra, [])
    info_texto = f"La barra '{barra}' tiene {len(fases)} fase(s): " + ", ".join(f"Fase {f}" for f in fases)
    return ([{"label": f"Fase {f}", "value": f} for f in fases], None, info_texto)


@app.callback(
    Output('grafico-comparativo', 'figure'),
    Output('mensaje-validacion', 'children'),
    Input('btn-aplicar', 'n_clicks'),
    State('barra-gd', 'value'),
    State('fase-gd', 'value'),
    State('potencia-gd', 'value'),
    State('tipo-gd', 'value')
)
def actualizar_grafico(n_clicks, barra, fase_seleccionada, kw, tipo):
    if n_clicks == 0 or ("trifasica" not in tipo and "bifasica" not in tipo and fase_seleccionada is None):
        return go.Figure(), ""

    reiniciar_circuito()
    circuit.SetActiveBus(barra)
    fases_disponibles = sorted(circuit.ActiveBus.Nodes)

    if "trifasica" in tipo:
        if fases_disponibles != [1, 2, 3]:
            return go.Figure(), "La barra seleccionada no tiene disponibles las 3 fases necesarias para una GD trifásica."
    elif "bifasica" in tipo:
        if not (len(fase_seleccionada) == 2 and all(f in fases_disponibles for f in fase_seleccionada)):
            return go.Figure(), "Debe seleccionar exactamente dos fases válidas disponibles en la barra para una GD bifásica."
        if abs(fase_seleccionada[0] - fase_seleccionada[1]) != 1:
            return go.Figure(), "Las fases seleccionadas para la GD bifásica deben ser contiguas (por ejemplo, 1-2 o 2-3)."

    '''base_por_fase = {1: {}, 2: {}, 3: {}}
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

    kv_ln = circuit.ActiveBus.kVBase'''

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

    # Capturar pérdidas sin GD (antes de aplicar la fuente)
    perdidas_sin_gd = circuit.Losses[0] / 1000  # Watts a kW

    kv_ln = circuit.ActiveBus.kVBase

    kv_ll = kv_ln * (3**0.5) if len(fases_disponibles) > 1 else kv_ln

    if any(g.lower() == 'gd' for g in circuit.Generators.AllNames):
        try:
            text.Command = "Remove Generator.GD"
        except dss._cffi_api_util.DSSException as e:
            if "not found" not in str(e).lower():
                raise
    try:
        if "trifasica" in tipo:
            text.Command = f"New Generator.GD Bus1={barra} Phases=3 kV={kv_ll:.3f} kW={kw} kvar=0 Model=1"
        elif "bifasica" in tipo:
            fases_str = ".".join(str(f) for f in fase_seleccionada)
            text.Command = f"New Generator.GD Bus1={barra}.{fases_str} Phases=2 kV={kv_ll:.3f} kW={kw} kvar=0 Model=1"
        else:
            text.Command = f"New Generator.GD Bus1={barra}.{fase_seleccionada} Phases=1 kV={kv_ln:.3f} kW={kw} kvar=0 Model=1"
        text.Command = "Solve"

    # Aquí sí se capturan correctamente las pérdidas con GD
        perdidas_con_gd = circuit.Losses[0] / 1000

    except Exception as e:
        return go.Figure(), f"Error al aplicar la GD: {str(e)}"


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

    fig = go.Figure()
    for fase in [1, 2, 3]:
        if not base_por_fase[fase] and not gd_por_fase[fase]:
            continue

        df_base = pd.DataFrame({"Barra.Fase": base_por_fase[fase].keys(), "Sin GD": base_por_fase[fase].values()})
        df_gd = pd.DataFrame({"Barra.Fase": gd_por_fase[fase].keys(), "Con GD": gd_por_fase[fase].values()})
        df_all_keys = pd.DataFrame({"Barra.Fase": [f"{b}.{fase}" for b in barras]})

        df_base = df_all_keys.merge(df_base, on="Barra.Fase", how="left")
        df_gd = df_all_keys.merge(df_gd, on="Barra.Fase", how="left")
        df_merge = df_base.merge(df_gd, on="Barra.Fase")
        fig.add_trace(go.Bar(x=df_merge["Barra.Fase"], y=df_merge["Sin GD"], name=f"Fase {fase} - Sin GD"))
        fig.add_trace(go.Bar(x=df_merge["Barra.Fase"], y=df_merge["Con GD"], name=f"Fase {fase} - Con GD"))
        fig.add_trace(go.Scatter(x=df_merge["Barra.Fase"], y=[1.05]*len(df_merge), mode='lines', name=f'Fase {fase} - Límite Superior', line=dict(color='red', dash='dash')))
        fig.add_trace(go.Scatter(x=df_merge["Barra.Fase"], y=[0.95]*len(df_merge), mode='lines', name=f'Fase {fase} - Límite Inferior', line=dict(color='red', dash='dash')))

    fig.update_layout(title="Comparativo Voltaje PU por Fase", yaxis_title="Voltaje PU")

    # Mostrar pérdidas obtenidas correctamente arriba después del Solve

    fig.add_annotation(
        text=f"Pérdidas sin GD: {perdidas_sin_gd:.2f} kW",
        xref="paper", yref="paper",
        x=0, y=1.1, showarrow=False, font=dict(size=12)
    )
    fig.add_annotation(
        text=f"Pérdidas con GD: {perdidas_con_gd:.2f} kW",
        xref="paper", yref="paper",
        x=0, y=1.05, showarrow=False, font=dict(size=12)
    )
    return fig, ""

if __name__ == '__main__':
    app.run(debug=True)
