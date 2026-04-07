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

voltajes_df = pd.DataFrame({"Barra.Fase": voltajes_dict.keys(), "VoltajePU": voltajes_dict.values()})

limites_gd = []

for barra_gd in barras:
    circuit.SetActiveBus(barra_gd)
    nodos = circuit.ActiveBus.Nodes
    for fase in nodos:
        limite_kw = 0
        #Aquí se define el valor mínimo y máximo para encontrar el límite antes de generar violaciones en el sistema al insertar una GD en intérvalos de 200
        for kw in range(0, 40000, 200):
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

app = dash.Dash(__name__)
app.title = "Dashboard OpenDSS"

app.layout = html.Div([
    html.Div(id='info-barra', style={'marginBottom': '1em', 'fontWeight': 'bold'}),
    html.H2("Perfil de Voltaje por Barra y Fase"),
    dcc.Graph(id='grafico-voltajes',
              figure=go.Figure(
                  data=[go.Bar(x=voltajes_df["Barra.Fase"], y=voltajes_df["VoltajePU"])],
                  layout=go.Layout(yaxis=dict(title="Voltaje PU"), xaxis=dict(title="Barra.Fase"))
              )
    ),
    html.H4("Límite máximo de generación distribuida sin causar violaciones"),
    html.Div([
        html.Table([
            html.Thead([
                html.Tr([html.Th(col) for col in limites_df.columns])
            ]),
            html.Tbody([
                html.Tr([
                    html.Td(limites_df.iloc[i][col]) for col in limites_df.columns
                ]) for i in range(len(limites_df))
            ])
        ])
    ]),
    html.Hr(),
    html.Div([
        html.Label("Selecciona la barra para insertar GD:"),
        dcc.Dropdown(id='barra-gd', options=[{"label": b, "value": b} for b in barras], value=barras[0]),
        html.Label("Selecciona la fase disponible (opcional si GD trifásica o bifásica):"),
        dcc.Dropdown(id='fase-gd', value=None),
        html.Label("Tipo de GD:"),
        dcc.Checklist(
            id='tipo-gd',
            options=[
                {"label": "Trifásica", "value": "trifasica"},
                {"label": "Bifásica", "value": "bifasica"}
            ],
            value=[]
        ),
        html.Label("Potencia GD (kW):"),
        dcc.Slider(id='potencia-gd', min=500, max=20000, step=500, value=100, marks={i: str(i) for i in range(500, 20000, 500)}),
        html.Button("Aplicar GD", id='btn-aplicar', n_clicks=0)
    ]),
    html.Div(id='mensaje-validacion', style={'color': 'red'}),
    dcc.Graph(id='grafico-comparativo')
])

@app.callback(
    Output('fase-gd', 'options'),
    Output('fase-gd', 'value'),
    Output('info-barra', 'children'),
    Input('barra-gd', 'value')
)
def actualizar_fases(barra):
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
        if len(fases_disponibles) != 2:
            return go.Figure(), "La barra seleccionada no tiene exactamente dos fases necesarias para una GD bifásica."

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
            fases_str = ".".join(str(f) for f in fases_disponibles)
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
        if not base_por_fase[fase] or not gd_por_fase[fase]:
            continue
        df_base = pd.DataFrame({"Barra.Fase": base_por_fase[fase].keys(), "Sin GD": base_por_fase[fase].values()})
        df_gd = pd.DataFrame({"Barra.Fase": gd_por_fase[fase].keys(), "Con GD": gd_por_fase[fase].values()})
        df_merge = df_base.merge(df_gd, on="Barra.Fase")
        fig.add_trace(go.Scatter(x=df_merge["Barra.Fase"], y=df_merge["Sin GD"], mode='lines+markers', name=f"Fase {fase} - Sin GD"))
        fig.add_trace(go.Scatter(x=df_merge["Barra.Fase"], y=df_merge["Con GD"], mode='lines+markers', name=f"Fase {fase} - Con GD"))
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
