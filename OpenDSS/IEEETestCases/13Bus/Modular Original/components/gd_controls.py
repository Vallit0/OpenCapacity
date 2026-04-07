from dash import dcc, html
import dash_bootstrap_components as dbc

def create_gd_controls(barras, barras_fases_disponibles):
    """Crear controles para aplicar GD"""
    return html.Div([
        html.H4("Simular Generación Distribuida", className="mb-4"),
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Label("Selecciona la barra para insertar GD:", className="form-label"),
                        dcc.Dropdown(
                            id='barra-gd', 
                            options=[{"label": b, "value": b} for b in barras],
                            className="mb-3"
                        ),
                    ], width=6),
                    dbc.Col([
                        html.Label("Potencia GD (kW):", className="form-label"),
                        dcc.Input(
                            id='potencia-gd', 
                            type='number', 
                            min=0, 
                            max=10000000, 
                            value=100, 
                            className="form-control mb-3"
                        ),
                    ], width=6)
                ]),
                
                dbc.Row([
                    dbc.Col([
                        html.Div(id='info-barra', style={'marginBottom': '1em', 'fontWeight': 'bold'}),
                    ], width=12)
                ]),
                
                dbc.Row([
                    dbc.Col([
                        html.Label("Tipo de GD:", className="form-label"),
                        dbc.RadioItems(
                            id='tipo-gd',
                            options=[
                                {"label": "Trifásica", "value": "trifasica"},
                                {"label": "Bifásica", "value": "bifasica"},
                                {"label": "Monofásica", "value": "monofasica"}
                            ],
                            value="monofasica",
                            inline=True,
                            className="mb-3"
                        ),
                    ], width=6),
                    dbc.Col([
                        html.Label("Selecciona la fase:", className="form-label"),
                        dcc.Dropdown(
                            id='fase-gd', 
                            value=None,
                            multi=False,
                            className="mb-3"
                        ),
                    ], width=6)
                ]),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Button(
                            "Aplicar GD", 
                            id='btn-aplicar', 
                            n_clicks=0, 
                            color="primary",
                            size="lg",
                            className="w-100"
                        )
                    ], width=12)
                ])
            ])
        ])
    ], className="container")