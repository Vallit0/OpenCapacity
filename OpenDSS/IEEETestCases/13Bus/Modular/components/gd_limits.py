from dash import html
import dash_bootstrap_components as dbc
import pandas as pd

def create_gd_limits_table(limites_gd):
    """Crear tabla de límites de GD"""
    if limites_gd.empty:
        return html.Div()
    
    limites_pivot = limites_gd.pivot(
        index='Barra', 
        columns='Fase', 
        values='Max GD sin violacion (kW)'
    ).sort_index().fillna('NULL')
    
    fases_ordenadas = sorted(limites_pivot.columns)
    
    return html.Div([
        html.H4("Límite máximo de generación distribuida sin causar violaciones", className="mt-4 mb-4"),
        dbc.Card([
            dbc.CardBody([
                html.Div([
                    dbc.Table([
                        html.Thead([
                            html.Tr([html.Th("Barra", className="text-center")] + 
                                   [html.Th(f"Fase {f}", className="text-center") for f in fases_ordenadas])
                        ], className="table-dark"),
                        html.Tbody([
                            html.Tr([
                                html.Td(barra, className="fw-bold")
                            ] + [
                                html.Td(
                                    limites_pivot.loc[barra][f] if f in limites_pivot.columns else "NULL", 
                                    className="text-center"
                                ) for f in fases_ordenadas
                            ]) for barra in limites_pivot.index
                        ])
                    ], className="table table-bordered table-hover table-striped")
                ], style={'overflowX': 'auto'})
            ])
        ])
    ], className="container")