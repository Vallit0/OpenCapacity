from dash import Dash, html, dcc
from dash.dependencies import Input, Output

# Initialize the Dash app
app = Dash(__name__)

# Define the layout for the welcome page
app.layout = html.Div([
    html.H1("Welcome to the OpenDSS Simulation Dashboard", className="text-center"),
    html.Div([
        html.P("This application allows you to simulate and analyze power distribution systems."),
        html.Button("Start Simulation", id='start-button', className="btn btn-primary")
    ], className="text-center")
])

# Define the callback to navigate to the simulation page
@app.callback(
    Output('start-button', 'n_clicks'),
    Input('start-button', 'n_clicks')
)
def navigate_to_simulation(n_clicks):
    if n_clicks:
        return dcc.Location(href='/simulacion', id='simulacion-link')
    return None

# Import the simulation page
import Simulacion_DASH_VFinal_2

if __name__ == '__main__':
    app.run(debug=True)