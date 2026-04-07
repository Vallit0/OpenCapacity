from dash import dcc, html
import dash_bootstrap_components as dbc

def create_results_section():
    """Crear sección de resultados"""
    return html.Div([
        html.Hr(),
        html.H3("Resultados de la Simulación", className="text-center mb-4"),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Comparación de Voltajes"),
                    dbc.CardBody([
                        dcc.Graph(id='grafico-comparativo')
                    ])
                ], className="mb-4")
            ], width=12)
        ]),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Violaciones Detectadas"),
                    dbc.CardBody([
                        html.Div(id='tabla-violaciones')
                    ])
                ])
            ], width=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Análisis de Pérdidas"),
                    dbc.CardBody([
                        html.Div(id='tabla-perdidas')
                    ])
                ])
            ], width=6)
        ])
    ], className="container mt-4")