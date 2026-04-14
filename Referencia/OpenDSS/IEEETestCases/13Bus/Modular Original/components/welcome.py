from dash import html, dcc
import dash_bootstrap_components as dbc

def create_welcome_screen():
    return dbc.Container([
        dbc.Row(
            dbc.Col(
                html.H1("Sistema de Análisis de Red IEEE 13 Nodos", 
                       className="text-center text-primary mb-4 mt-5"),
                width=12
            )
        ),
        dbc.Row(
            dbc.Col(
                html.P("Esta herramienta permite analizar el impacto de la generación distribuida en la red IEEE 13 Node usando Python.", 
                      className="text-center lead"),
                width=10, className="mx-auto"
            )
        ),
        dbc.Row(
            dbc.Col(
                html.Div([
                    html.H4("Instrucciones:", className="mt-4"),
                    html.Ol([
                        html.Li("Cargue los archivos necesarios para la simulación IEEE 13 Node:"),
                        html.Ul([
                            html.Li("IEEE13Nodeckt.dss - Archivo principal del circuito (OBLIGATORIO)"),
                            html.Li("IEEELineCodes.dss - Archivo de códigos de línea (OPCIONAL, se usará uno por defecto)"),
                            html.Li("IEEE13Node_BusXY.csv - Archivo de coordenadas de buses (OPCIONAL)")
                        ]),
                        html.Li("Haga clic en 'Analizar Archivos' para procesarlos"),
                        html.Li("Explore los resultados y realice simulaciones con GD")
                    ])
                ], className="mt-4"),
                width=8, className="mx-auto"
            )
        ),
        dbc.Row(
            dbc.Col(
                html.Div([
                    # Upload para archivo principal DSS
                    html.H5("IEEE13Nodeckt.dss - Archivo Principal (OBLIGATORIO)", className="mt-4"),
                    dcc.Upload(
                        id='upload-main-dss',
                        children=html.Div([
                            html.I(className="fas fa-file-code me-2"),
                            'Arrastre y suelte o ',
                            html.A('seleccione IEEE13Nodeckt.dss', className="text-primary")
                        ]),
                        style={
                            'width': '100%',
                            'height': '80px',
                            'lineHeight': '80px',
                            'borderWidth': '2px',
                            'borderStyle': 'dashed',
                            'borderRadius': '8px',
                            'borderColor': '#0d6efd',
                            'textAlign': 'center',
                            'margin': '10px 0',
                            'cursor': 'pointer',
                            'backgroundColor': '#f8f9fa'
                        },
                        multiple=False
                    ),
                    html.Div(id='output-main-dss', className="text-center small"),
                    
                    # Upload para archivo de line codes DSS
                    html.H5("IEEELineCodes.dss - Códigos de Línea (OPCIONAL)", className="mt-4"),
                    dcc.Upload(
                        id='upload-linecodes-dss',
                        children=html.Div([
                            html.I(className="fas fa-file-code me-2"),
                            'Arrastre y suelte o ',
                            html.A('seleccione IEEELineCodes.dss', className="text-primary")
                        ]),
                        style={
                            'width': '100%',
                            'height': '80px',
                            'lineHeight': '80px',
                            'borderWidth': '2px',
                            'borderStyle': 'dashed',
                            'borderRadius': '8px',
                            'borderColor': '#6c757d',
                            'textAlign': 'center',
                            'margin': '10px 0',
                            'cursor': 'pointer',
                            'backgroundColor': '#f8f9fa'
                        },
                        multiple=False
                    ),
                    html.Div(id='output-linecodes-dss', className="text-center small text-muted"),
                    
                    # Upload para archivo CSV de coordenadas
                    html.H5("IEEE13Node_BusXY.csv - Coordenadas de Buses (OPCIONAL)", className="mt-4"),
                    dcc.Upload(
                        id='upload-busxy-csv',
                        children=html.Div([
                            html.I(className="fas fa-file-csv me-2"),
                            'Arrastre y suelte o ',
                            html.A('seleccione IEEE13Node_BusXY.csv', className="text-primary")
                        ]),
                        style={
                            'width': '100%',
                            'height': '80px',
                            'lineHeight': '80px',
                            'borderWidth': '2px',
                            'borderStyle': 'dashed',
                            'borderRadius': '8px',
                            'borderColor': '#6c757d',
                            'textAlign': 'center',
                            'margin': '10px 0',
                            'cursor': 'pointer',
                            'backgroundColor': '#f8f9fa'
                        },
                        multiple=False
                    ),
                    html.Div(id='output-busxy-csv', className="text-center small text-muted"),
                    
                    html.Div(id='output-file-upload', className="text-center mt-3"),
                ], className="mt-4"),
                width=10, className="mx-auto"
            )
        )
    ], fluid=True, className="py-5")