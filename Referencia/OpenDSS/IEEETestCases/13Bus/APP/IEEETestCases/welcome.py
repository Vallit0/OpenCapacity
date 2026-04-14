from dash import Dash, dcc, html, Input, Output
import dash_bootstrap_components as dbc

app = Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])
app.title = "Welcome to the OpenDSS Simulation Dashboard"

app.layout = html.Div([
    dbc.Container([
        html.H1("Welcome to the OpenDSS Simulation Dashboard", className="text-center mt-5"),
        html.Div([
            dbc.Button("Start Simulation", id="start-button", color="primary", size="lg", className="mt-3"),
        ], className="text-center"),
    ])
])

@app.callback(
    Output("start-button", "n_clicks"),
    Input("start-button", "n_clicks")
)
def navigate_to_simulation(n_clicks):
    if n_clicks:
        return n_clicks  # This will be handled in app.py for navigation

if __name__ == '__main__':
    app.run_server(debug=True)