import dash
from dash import dcc, html
from src.layouts import layout_root
from src.callbacks import register_callbacks

external_stylesheets = ["https://cdn.jsdelivr.net/npm/bootswatch@5.3.3/dist/flatly/bootstrap.min.css"]
app = dash.Dash(
    __name__,
    external_stylesheets=external_stylesheets,
    suppress_callback_exceptions=True
)
app.title = "Dashboard OpenDSS (Modular)"

# Layout principal
app.layout = layout_root()

# Validation layout para que Dash conozca TODOS los IDs posibles
app.validation_layout = html.Div([
    # Stores base
    dcc.Store(id="dss-path"),
    dcc.Store(id="app-mode"),
    dcc.Store(id="base-state"),
    dcc.Location(id="url"),
    html.Div(id="view-container"),
    # IDs de bienvenida
    html.Div(id="status-banner"),
    dcc.Upload(id="upload-dss"),
    html.Button(id="btn-analizar"),
    # IDs de análisis
    dcc.Graph(id="grafico-voltajes"),
    html.Div(id="tabla-limites"),
    dcc.Dropdown(id="barra-gd"),
    html.Div(id="info-barra"),
    dcc.Dropdown(id="fase-gd"),
    dcc.Checklist(id="tipo-gd"),
    dcc.Input(id="potencia-gd"),
    html.Button(id="btn-aplicar"),
    html.Div(id="mensaje-validacion"),
    dcc.Graph(id="grafico-comparativo"),
    html.Div(id="tabla-violaciones"),
    html.Div(id="tabla-perdidas"),
])

# Registrar callbacks (después de fijar validation_layout)
register_callbacks(app)

if __name__ == "__main__":
    app.run(debug=True)
