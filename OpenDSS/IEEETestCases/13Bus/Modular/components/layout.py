import dash_bootstrap_components as dbc
from dash import html, dcc
import plotly.graph_objects as go

def create_layout(analysis_data):
    if 'error' in analysis_data:
        return html.Div([
            dbc.Alert(f"Error en el análisis: {analysis_data['error']}", color="danger"),
            dbc.Button("Volver al inicio", href="/", color="primary")
        ], className="container mt-4")
    
    # Extraer datos del análisis
    voltajes_df = analysis_data.get('voltajes_df', [])
    limites_gd = analysis_data.get('limites_gd', [])
    perdidas_sin_gd_df = analysis_data.get('perdidas_sin_gd_df', [])
    resumen_sin_gd = analysis_data.get('resumen_sin_gd', {})
    barras = analysis_data.get('barras', [])
    barras_fases_disponibles = analysis_data.get('barras_fases_disponibles', {})
    circuit_info = analysis_data.get('circuit_info', {})
    
    # Crear tabla de límites GD
    limites_pivot_data = {}
    for item in limites_gd:
        barra = item['Barra']
        fase = item['Fase']
        valor = item['Max GD sin violacion (kW)']
        
        if barra not in limites_pivot_data:
            limites_pivot_data[barra] = {}
        limites_pivot_data[barra][fase] = valor
    
    # Crear gráfico de voltajes
    fig_voltajes = go.Figure()
    if voltajes_df:
        fig_voltajes.add_trace(go.Bar(
            x=[item['Barra.Fase'] for item in voltajes_df],
            y=[item['VoltajePU'] for item in voltajes_df],
            name="Voltaje PU"
        ))
        fig_voltajes.update_layout(
            title="Perfil de Voltaje por Barra y Fase",
            yaxis_title="Voltaje PU",
            xaxis_title="Barra.Fase",
            showlegend=False
        )
        fig_voltajes.add_hline(y=1.05, line_dash="dash", line_color="red", annotation_text="Límite Superior")
        fig_voltajes.add_hline(y=0.95, line_dash="dash", line_color="red", annotation_text="Límite Inferior")
    
    return html.Div([
        # Header
        dbc.Navbar(
            dbc.Container([
                dbc.NavbarBrand("Dashboard OpenDSS - Resultados del Análisis", className="ms-2"),
                dbc.Button("Volver al Inicio", href="/", color="light", className="me-2")
            ]),
            color="primary",
            dark=True
        ),
        
        dbc.Container([
            # Información del Circuito
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Información del Circuito", className="bg-primary text-white"),
                        dbc.CardBody([
                            html.Ul([
                                html.Li(f"Nombre: {circuit_info.get('name', 'N/A')}"),
                                html.Li(f"Número de buses: {circuit_info.get('num_buses', 0)}"),
                                html.Li(f"Número de elementos: {circuit_info.get('num_elements', 0)}"),
                                html.Li(f"Convergió: {'Sí' if circuit_info.get('converged', False) else 'No'}"),
                                html.Li(f"Potencia total: {circuit_info.get('total_power_kw', 0):.2f} kW"),
                                html.Li(f"Potencia reactiva: {circuit_info.get('total_power_kvar', 0):.2f} kvar")
                            ])
                        ])
                    ])
                ], md=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Resumen de Pérdidas", className="bg-success text-white"),
                        dbc.CardBody([
                            html.Ul([
                                html.Li([html.Strong(k + ": "), f"{v}"]) 
                                for k, v in resumen_sin_gd.items()
                            ])
                        ])
                    ])
                ], md=6)
            ], className="mb-4"),
            
            # Gráfico de Voltajes
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Perfil de Voltajes", className="bg-info text-white"),
                        dbc.CardBody([
                            dcc.Graph(
                                id='grafico-voltajes',
                                figure=fig_voltajes,
                                style={'height': '400px'}
                            )
                        ])
                    ])
                ], width=12)
            ], className="mb-4"),
            
            # Límites de GD
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Límites de Generación Distribuida", 
                                     className="bg-warning text-dark"),
                        dbc.CardBody([
                            html.Div([
                                html.Table([
                                    html.Thead([
                                        html.Tr([html.Th("Barra")] + 
                                               [html.Th(f"Fase {f}") for f in [1, 2, 3]])
                                    ]),
                                    html.Tbody([
                                        html.Tr([
                                            html.Td(barra)
                                        ] + [
                                            html.Td(limites_pivot_data.get(barra, {}).get(f, "N/A"))
                                            for f in [1, 2, 3]
                                        ]) for barra in sorted(limites_pivot_data.keys())
                                    ])
                                ], className="table table-bordered table-hover table-sm")
                            ], style={'maxHeight': '300px', 'overflowY': 'auto'})
                        ])
                    ])
                ], width=12)
            ], className="mb-4"),
            
            # Tabla de Pérdidas
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Pérdidas por Elemento", className="bg-secondary text-white"),
                        dbc.CardBody([
                            html.Div([
                                html.Table([
                                    html.Thead([
                                        html.Tr([html.Th(col) for col in 
                                                ['Tipo', 'Elemento', 'kW Pérdida', '% of Power', 'kvar Pérdida']])
                                    ]),
                                    html.Tbody([
                                        html.Tr([
                                            html.Td(str(item[col])) for col in 
                                            ['Tipo', 'Elemento', 'kW Pérdida', '% of Power', 'kvar Pérdida']
                                        ]) for item in perdidas_sin_gd_df
                                    ])
                                ], className="table table-striped table-hover table-sm")
                            ], style={'maxHeight': '400px', 'overflowY': 'auto'})
                        ])
                    ])
                ], width=12)
            ], className="mb-4"),
            
            # Simulación de GD
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Simulación de Generación Distribuida", 
                                     className="bg-danger text-white"),
                        dbc.CardBody([
                            html.Div([
                                html.Label("Selecciona la barra para insertar GD:", 
                                         className="form-label"),
                                dcc.Dropdown(
                                    id='barra-gd',
                                    options=[{"label": b, "value": b} for b in barras],
                                    className="mb-3"
                                ),
                                
                                html.Div(id='info-barra', 
                                       style={'marginBottom': '1em', 'fontWeight': 'bold'}),
                                
                                html.Label("Selecciona la fase:", className="form-label"),
                                dcc.Dropdown(
                                    id='fase-gd',
                                    className="mb-3"
                                ),
                                
                                html.Label("Potencia GD (kW):", className="form-label"),
                                dcc.Input(
                                    id='potencia-gd',
                                    type='number',
                                    min=0,
                                    value=100,
                                    className="form-control mb-3"
                                ),
                                
                                dbc.Button("Aplicar GD", id='btn-aplicar', 
                                         color="primary", className="mb-3"),
                                
                                html.Div(id='mensaje-validacion', 
                                       style={'color': 'red', 'marginTop': '1em'})
                            ])
                        ])
                    ])
                ], md=6),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Resultados de la Simulación", 
                                     className="bg-success text-white"),
                        dbc.CardBody([
                            dcc.Graph(id='grafico-comparativo'),
                            html.Div(id='tabla-violaciones'),
                            html.Div(id='tabla-perdidas')
                        ])
                    ])
                ], md=6)
            ])
        ], fluid=True)
    ])