from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import dash

from .layouts import layout_welcome
from .core_dss import save_upload_to_temp, preparar_estado_base, figura_voltajes, html_tabla_limites, aplicar_gd

def _build_analysis_layout(state, dss_path):
    """Devuelve el layout completo de la pantalla de análisis con figuras y tablas pre-cargadas."""
    fig = figura_voltajes(state)
    tabla_limites = html_tabla_limites(state)
    opciones_barras = [{"label": b, "value": b} for b in state["barras"]]
    info = f"Circuito cargado desde: {dss_path}"

    return html.Div([
        dbc.Container([
            html.Div([
                html.H2("Perfil de Voltaje por Barra y Fase", className="text-center mb-4 mt-4"),
                dcc.Graph(id="grafico-voltajes", figure=fig)
            ], className="mb-4"),

            html.Div([
                html.H4("Límite máximo de generación distribuida sin causar violaciones", className="mt-4"),
                html.Div(id="tabla-limites", children=tabla_limites)
            ], className="mb-4"),

            html.Hr(),

            html.Div([
                html.Label("Selecciona la barra para insertar GD:", className="form-label mt-3"),
                dcc.Dropdown(id="barra-gd", options=opciones_barras, className="mb-2"),
                html.Div(id="info-barra", children=info, style={'marginBottom': '1em', 'fontWeight': 'bold'}),

                html.Label("Selecciona la fase disponible (opcional si GD trifásica o bifásica):", className="form-label"),
                dcc.Dropdown(id="fase-gd", value=None, multi=True, className="mb-2"),

                html.Label("Tipo de GD:", className="form-label"),
                dcc.Checklist(
                    id="tipo-gd",
                    options=[
                        {"label": "Trifásica", "value": "trifasica"},
                        {"label": "Bifásica", "value": "bifasica"}
                    ],
                    value=[],
                    inputStyle={"margin-right": "5px"},
                    labelStyle={"margin-right": "15px"},
                    className="mb-3"
                ),

                html.Label("Potencia GD (kW):", className="form-label"),
                dcc.Input(id="potencia-gd", type="number", min=0, max=10000000, value=100, className="form-control mb-3"),

                dbc.Button("Aplicar GD", id="btn-aplicar", n_clicks=0, color="primary")
            ]),

            html.Div(id="mensaje-validacion", className="mt-3"),

            html.Div([
                dcc.Graph(id="grafico-comparativo"),
                html.Div(id="tabla-violaciones", className="mt-4"),
                html.Div(id="tabla-perdidas", className="mt-4")
            ])
        ], fluid=True)
    ])

def register_callbacks(app):
    # Router: render view and, si es análisis, preconstruye toda la vista con IDs ya presentes
    @app.callback(
        Output("view-container", "children"),
        Output("base-state", "data"),
        Input("app-mode", "data"),
        State("dss-path", "data"),
        prevent_initial_call=False  # para que pinte bienvenida al inicio
    )
    def _render_view(mode, dss_path):
        if mode == "analysis" and dss_path:
            state = preparar_estado_base(dss_path)
            analysis_layout = _build_analysis_layout(state, dss_path)
            return analysis_layout, state
        # modo bienvenida (o si falta el path)
        return layout_welcome(), None

    # Carga del archivo: guarda en temp, muestra banner verde y habilita botón
    @app.callback(
        Output("status-banner", "children"),
        Output("status-banner", "className"),
        Output("btn-analizar", "disabled"),
        Output("dss-path", "data"),
        Input("upload-dss", "contents"),
        State("upload-dss", "filename"),
        prevent_initial_call=True
    )
    def _handle_upload(contents, filename):
        if not contents:
            raise dash.exceptions.PreventUpdate
        try:
            path = save_upload_to_temp(contents, filename)
            ok_text = "✓ Archivos necesarios cargados correctamente"
            ok_class = "alert alert-success mt-3"
            return ok_text, ok_class, False, path
        except Exception as e:
            return f"Error al procesar el archivo: {e}", "alert alert-danger mt-3", True, None

    # Cambiar a modo análisis
    @app.callback(
        Output("app-mode", "data"),
        Input("btn-analizar", "n_clicks"),
        prevent_initial_call=True
    )
    def _switch_to_analysis(n):
        if n:
            return "analysis"
        return "welcome"

    # Una vez en análisis, llenar opciones de fases según la barra seleccionada (usa base-state cacheado)
    @app.callback(
        Output("fase-gd", "options"),
        Output("fase-gd", "value"),
        Input("barra-gd", "value"),
        State("base-state", "data"),
        prevent_initial_call=True
    )
    def _update_fases(barra, state):
        if not barra or not state:
            return [], None
        fases = state.get("barras_fases_disponibles", {}).get(barra, [])
        return ([{"label": f"Fase {f}", "value": f} for f in fases], None)


    # Aplicar GD y actualizar gráficas/tablas
    @app.callback(
        Output("grafico-comparativo", "figure"),
        Output("tabla-violaciones", "children"),
        Output("tabla-perdidas", "children"),
        Output("mensaje-validacion", "children"),
        Input("btn-aplicar", "n_clicks"),
        State("barra-gd", "value"),
        State("fase-gd", "value"),
        State("potencia-gd", "value"),
        State("tipo-gd", "value"),
        State("dss-path", "data"),
        prevent_initial_call=True
    )
    def _aplicar_gd(n, barra, fases_sel, kw, tipo, dss_path):
        if not n:
            raise dash.exceptions.PreventUpdate
        if not dss_path:
            return go.Figure(), "Primero cargue el circuito.", "", ""
        fig, tabla_viol, tabla_perd, msg = aplicar_gd(dss_path, barra, tipo, fases_sel, kw or 0.0)
        return fig, tabla_viol, tabla_perd, msg
