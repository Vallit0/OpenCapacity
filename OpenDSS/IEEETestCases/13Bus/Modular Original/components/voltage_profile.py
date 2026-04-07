from dash import dcc, html
import plotly.graph_objs as go
import dash_bootstrap_components as dbc

def create_voltage_profile(voltajes_df):
    """Crear componente de perfil de voltaje"""
    return html.Div([
        html.H2("Perfil de Voltaje por Barra y Fase", className="text-center mb-4 mt-4"),
        dcc.Graph(
            id='grafico-voltajes',
            figure=go.Figure(
                data=[go.Bar(x=voltajes_df["Barra.Fase"], y=voltajes_df["VoltajePU"])],
                layout=go.Layout(
                    yaxis=dict(title="Voltaje PU", range=[0.9, 1.1]),
                    xaxis=dict(title="Barra.Fase"),
                    height=500
                )
            ),
            className="mb-4"
        )
    ], className="container")