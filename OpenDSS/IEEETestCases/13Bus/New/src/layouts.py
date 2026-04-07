
from dash import dcc, html
import dash_bootstrap_components as dbc

def layout_root():
    return html.Div([
        dcc.Store(id="dss-path", storage_type="memory"),
        dcc.Store(id="app-mode", data="welcome", storage_type="memory"),
        dcc.Store(id="base-state", storage_type="memory"),
        dcc.Location(id="url"),
        html.Div(id="view-container")
    ])

def layout_welcome():
    return html.Div([
        html.H1("Dashboard OpenDSS", className="text-center mt-4"),
        html.P("Análisis de Red Eléctrica IEEE 13 Nodos", className="text-center text-muted mb-4"),
        dbc.Container([
            dbc.Card([
                dbc.CardHeader("Carga de Archivos OpenDSS", class_name="bg-primary text-white"),
                dbc.CardBody([
                    html.H5("Archivo Principal del Circuito", className="card-title"),
                    html.Small("Sube el archivo .zip con los archivos necesarios", className="text-muted"),
                    html.Div([
                        dcc.Upload(
                            id="upload-dss",
                            children=html.Div(["Arrastra o selecciona el archivo .zip"]),
                            multiple=False,
                            accept=".dss,.zip",
                            className="dashed-zone mt-2"
                        ),
                    ]),
                    html.Div(id="status-banner", className="alert alert-danger mt-3",
                             children="⚠️ Cargue al menos el archivo principal del circuito (.zip)"),
                    dbc.Button("Analizar archivo", id="btn-analizar", class_name="mt-2", color="primary", disabled=True),
                ])
            ], class_name="mb-4")
        ], fluid=True)
    ])

def layout_analysis():
    # The actual analysis content is populated via callbacks after clicking "Analizar archivo".
    return html.Div([
        dbc.Container([
            html.Div([
                html.H2("Perfil de Voltaje por Barra y Fase", className="text-center mb-4 mt-4"),
                dcc.Graph(id="grafico-voltajes")
            ], className="mb-4"),

            html.Div([
                html.H4("Límite máximo de generación distribuida sin causar violaciones", className="mt-4"),
                html.Div(id="tabla-limites")
            ], className="mb-4"),

            html.Hr(),

            html.Div([
                html.Label("Selecciona la barra para insertar GD:", className="form-label mt-3"),
                dcc.Dropdown(id="barra-gd", options=[], className="mb-2"),
                html.Div(id="info-barra", style={'marginBottom': '1em', 'fontWeight': 'bold'}),

                html.Label("Selecciona la fase disponible (opcional si GD trifásica o bifásica):", className="form-label"),
                dcc.Dropdown(id="fase-gd", value=None, multi=True, className="mb-2"),

                html.Label("Tipo de GD:", className="form-label"),
                dcc.Checklist(
                    id="tipo-gd",
                    options=[
                        {"label": "Trifásica", "value": "trifasica"},
                        {"label": "Bifásica", "value": "bifasica"}
                    ],
                    value=[],
                    inputStyle={"marginRight": "5px"},
                    labelStyle={"marginRight": "15px"},
                    className="mb-3"
                ),

                html.Label("Potencia GD (kW):", className="form-label"),
                dcc.Input(id="potencia-gd", type="number", min=0, max=10000000, value=100, className="form-control mb-3"),

                dbc.Button("Aplicar GD", id="btn-aplicar", n_clicks=0, color="primary")
            ]),

            html.Div(id="mensaje-validacion", className="mt-3"),

            html.Div([
                dcc.Graph(id="grafico-comparativo"),
                html.Div(id="tabla-violaciones", className="mt-4"),
                html.Div(id="tabla-perdidas", className="mt-4")
            ])
        ], fluid=True)
    ])
