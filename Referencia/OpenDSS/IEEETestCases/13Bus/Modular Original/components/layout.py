from dash import html
import dash_bootstrap_components as dbc
from . import voltage_profile, gd_limits, gd_controls, results
import pandas as pd

def create_layout(analysis_data):
    # Verificar si hay error en el análisis
    if 'error' in analysis_data:
        return dbc.Container([
            dbc.Alert(analysis_data['error'], color="danger"),
            dbc.Button("Volver", href="/", color="primary")
        ])
    
    # Reconstruir DataFrames desde los datos almacenados
    voltajes_df = pd.DataFrame(analysis_data['voltajes_df'])
    limites_gd = pd.DataFrame(analysis_data['limites_gd'])
    perdidas_sin_gd_df = pd.DataFrame(analysis_data['perdidas_sin_gd_df'])
    
    return html.Div([
        # Navbar
        dbc.Navbar(
            dbc.Container([
                html.A(
                    dbc.Row([
                        dbc.Col(html.I(className="fas fa-bolt me-2")),
                        dbc.Col(dbc.NavbarBrand("Análisis de Red Eléctrica")),
                    ], align="center", className="g-0"),
                    href="/",
                    style={"textDecoration": "none"},
                ),
                dbc.NavbarToggler(id="navbar-toggler"),
            ]),
            color="primary",
            dark=True,
        ),
        
        # Contenido principal
        dbc.Container([
            voltage_profile.create_voltage_profile(voltajes_df),
            gd_limits.create_gd_limits_table(limites_gd),
            html.Hr(),
            gd_controls.create_gd_controls(analysis_data['barras'], analysis_data['barras_fases_disponibles']),
            html.Div(id='mensaje-validacion', style={'color': 'red'}, className="container mt-3"),
            results.create_results_section()
        ], fluid=True, className="py-4")
    ])