import dash_bootstrap_components as dbc
from dash import html, dcc

def create_welcome_screen():
    return html.Div([
        dbc.Container([
            # Header
            dbc.Row([
                dbc.Col([
                    html.H1("Dashboard OpenDSS", className="text-center text-primary mb-4"),
                    html.P("Análisis de Red Eléctrica IEEE 13 Nodos", 
                          className="text-center text-muted lead")
                ], width=12)
            ], className="mb-5"),
            
            # Upload Section
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Carga de Archivos OpenDSS", className="bg-primary text-white"),
                        dbc.CardBody([
                            html.H5("Archivo Principal del Circuito", className="card-title"),
                            html.P("Sube el archivo IEEE13Nodeckt.dss", className="card-text text-muted"),
                            dcc.Upload(
                                id='upload-main-dss',
                                children=html.Div([
                                    'Arrastra o ',
                                    html.A('selecciona el archivo .dss')
                                ]),
                                style={
                                    'width': '100%',
                                    'height': '60px',
                                    'lineHeight': '60px',
                                    'borderWidth': '1px',
                                    'borderStyle': 'dashed',
                                    'borderRadius': '5px',
                                    'textAlign': 'center',
                                    'margin': '10px 0'
                                },
                                multiple=False
                            ),
                            html.Div(id='output-main-dss', className="mt-2")
                        ])
                    ], className="mb-4"),
                    
                    dbc.Card([
                        dbc.CardHeader("Archivos Opcionales", className="bg-secondary text-white"),
                        dbc.CardBody([
                            html.H6("Archivo de Códigos de Línea", className="card-title"),
                            html.P("IEEELineCodes.dss (opcional)", className="card-text text-muted small"),
                            dcc.Upload(
                                id='upload-linecodes-dss',
                                children=html.Div([
                                    'Arrastra o ',
                                    html.A('selecciona el archivo .dss')
                                ]),
                                style={
                                    'width': '100%',
                                    'height': '50px',
                                    'lineHeight': '50px',
                                    'borderWidth': '1px',
                                    'borderStyle': 'dashed',
                                    'borderRadius': '5px',
                                    'textAlign': 'center',
                                    'margin': '10px 0'
                                },
                                multiple=False
                            ),
                            html.Div(id='output-linecodes-dss', className="mt-2 small"),
                            
                            html.Hr(),
                            
                            html.H6("Coordenadas de Buses", className="card-title"),
                            html.P("IEEE13Node_BusXY.csv (opcional)", className="card-text text-muted small"),
                            dcc.Upload(
                                id='upload-busxy-csv',
                                children=html.Div([
                                    'Arrastra o ',
                                    html.A('selecciona el archivo .csv')
                                ]),
                                style={
                                    'width': '100%',
                                    'height': '50px',
                                    'lineHeight': '50px',
                                    'borderWidth': '1px',
                                    'borderStyle': 'dashed',
                                    'borderRadius': '5px',
                                    'textAlign': 'center',
                                    'margin': '10px 0'
                                },
                                multiple=False
                            ),
                            html.Div(id='output-busxy-csv', className="mt-2 small")
                        ])
                    ])
                ], md=8, className="mx-auto")
            ]),
            
            # Analyze Button
            dbc.Row([
                dbc.Col([
                    html.Div(id='output-file-upload', className="text-center mt-4")
                ], width=12)
            ]),
            
            # Information Section
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Información del Sistema", className="bg-info text-white"),
                        dbc.CardBody([
                            html.Ul([
                                html.Li("Análisis de perfil de voltajes"),
                                html.Li("Cálculo de pérdidas del sistema"),
                                html.Li("Límites de generación distribuida"),
                                html.Li("Detección de violaciones técnicas"),
                                html.Li("Visualización interactiva de resultados")
                            ])
                        ])
                    ], className="mt-5")
                ], md=6, className="mx-auto")
            ])
        ], fluid=True)
    ], className="p-3")