from dash import dcc, html, Input, Output, State, callback_context
import plotly.graph_objs as go
import pandas as pd
from opendss import dss_engine, analysis
from utils.helpers import carga_valida, aplicar_generador
import dss
import dash_bootstrap_components as dbc

def register_callbacks(app):
    # Callback para actualizar fases disponibles
    @app.callback(
        [Output('fase-gd', 'options'),
         Output('fase-gd', 'value'),
         Output('info-barra', 'children')],
        [Input('barra-gd', 'value'),
         Input('tipo-gd', 'value')],
        [State('analysis-data', 'data')]
    )
    def actualizar_fases(barra, tipo_gd, analysis_data):
        if barra is None or not analysis_data:
            return [], None, ""
            
        barras_fases_disponibles = analysis_data['barras_fases_disponibles']
        fases = barras_fases_disponibles.get(barra, [])
        
        info_texto = f"La barra '{barra}' tiene {len(fases)} fase(s): " + ", ".join(f"Fase {f}" for f in fases)
        
        # Si es trifásica, no mostrar selector de fases
        if tipo_gd == "trifasica":
            return [], None, info_texto + " (GD trifásica usará todas las fases)"
        
        return ([{"label": f"Fase {f}", "value": f} for f in fases], None, info_texto)

    # Callback principal para aplicar GD y mostrar resultados
    @app.callback(
        [Output('grafico-comparativo', 'figure'),
         Output('mensaje-validacion', 'children'),
         Output('tabla-violaciones', 'children'),
         Output('tabla-perdidas', 'children')],
        [Input('btn-aplicar', 'n_clicks')],
        [State('barra-gd', 'value'),
         State('fase-gd', 'value'),
         State('potencia-gd', 'value'),
         State('tipo-gd', 'value'),
         State('analysis-data', 'data')]
    )
    def actualizar_grafico(n_clicks, barra, fase_seleccionada, kw, tipo_gd, analysis_data):
        if n_clicks == 0 or not analysis_data or not barra or not kw:
            return go.Figure(), "", "", ""
        
        # Inicializar OpenDSS
        engine, text, circuit, solution = dss_engine.initialize_dss()
        
        # Cargar datos del análisis
        voltajes_sin_gd = analysis_data['voltajes_df']
        perdidas_sin_gd_df = pd.DataFrame(analysis_data['perdidas_sin_gd_df'])
        resumen_sin_gd = analysis_data['resumen_sin_gd']
        barras = analysis_data['barras']
        barras_fases_disponibles = analysis_data['barras_fases_disponibles']
        
        # Obtener información de la barra seleccionada
        circuit.SetActiveBus(barra)
        fases_disponibles = sorted(circuit.ActiveBus.Nodes)
        kv_ln = circuit.ActiveBus.kVBase
        kv_ll = kv_ln * (3**0.5) if len(fases_disponibles) > 1 else kv_ln
        
        # Validaciones
        if tipo_gd == "trifasica" and fases_disponibles != [1, 2, 3]:
            return go.Figure(), "La barra seleccionada no tiene disponibles las 3 fases necesarias para una GD trifásica.", "", ""
        
        if tipo_gd == "bifasica" and (fase_seleccionada is None or len(fase_seleccionada) != 2):
            return go.Figure(), "Debe seleccionar exactamente dos fases válidas disponibles en la barra para una GD bifásica.", "", ""
        
        if tipo_gd == "monofasica" and fase_seleccionada is None:
            return go.Figure(), "Debe seleccionar una fase para la GD monofásica.", "", ""
        
        # Preparar fases según el tipo de GD
        if tipo_gd == "trifasica":
            fases_a_usar = [1, 2, 3]
        elif tipo_gd == "bifasica":
            fases_a_usar = fase_seleccionada
        else:
            fases_a_usar = [fase_seleccionada]
        
        # Aplicar generador
        try:
            aplicar_generador(text, barra, fases_a_usar, kw, tipo_gd, kv_ln, kv_ll)
        except Exception as e:
            return go.Figure(), f"Error al aplicar la GD: {str(e)}", "", ""
        
        # Obtener voltajes con GD
        voltajes_con_gd = analysis.obtener_perfil_voltajes(circuit)
        
        # Detectar violaciones de voltaje
        violaciones = []
        for _, row in voltajes_con_gd.iterrows():
            voltaje = row['VoltajePU']
            if voltaje is not None and (voltaje < 0.95 or voltaje > 1.05):
                violaciones.append({
                    "Barra.Fase": row['Barra.Fase'],
                    "Voltaje con GD (PU)": round(voltaje, 6)
                })
        
        violaciones_df = pd.DataFrame(violaciones)
        
        # Crear tabla de violaciones
        if not violaciones_df.empty:
            tabla_html = html.Div([
                dbc.Alert(f"Se detectaron {len(violaciones_df)} violaciones de voltaje", color="warning"),
                dbc.Table([
                    html.Thead(html.Tr([
                        html.Th("Barra.Fase"), 
                        html.Th("Voltaje (PU)")
                    ])),
                    html.Tbody([
                        html.Tr([
                            html.Td(fila["Barra.Fase"]),
                            html.Td(f"{fila['Voltaje con GD (PU)']:.6f}")
                        ]) for _, fila in violaciones_df.iterrows()
                    ])
                ], bordered=True, hover=True, responsive=True)
            ])
        else:
            tabla_html = dbc.Alert("No se detectaron violaciones de voltaje con la GD aplicada.", color="success")
        
        # Obtener pérdidas con GD
        perdidas_con_gd_df, resumen_con_gd = analysis.obtener_loss_table(circuit)
        
        # Crear gráfico comparativo
        fig = go.Figure()
        
        # Agrupar voltajes por fase
        for fase in [1, 2, 3]:
            # Filtrar por fase
            sin_gd_fase = voltajes_sin_gd[voltajes_sin_gd['Barra.Fase'].str.endswith(f'.{fase}')]
            con_gd_fase = voltajes_con_gd[voltajes_con_gd['Barra.Fase'].str.endswith(f'.{fase}')]
            
            if not sin_gd_fase.empty:
                fig.add_trace(go.Scatter(
                    x=sin_gd_fase["Barra.Fase"],
                    y=sin_gd_fase["VoltajePU"],
                    name=f"Fase {fase} - Sin GD",
                    mode='lines+markers',
                    line=dict(dash='dash')
                ))
            
            if not con_gd_fase.empty:
                fig.add_trace(go.Scatter(
                    x=con_gd_fase["Barra.Fase"],
                    y=con_gd_fase["VoltajePU"],
                    name=f"Fase {fase} - Con GD",
                    mode='lines+markers'
                ))
        
        # Añadir líneas de límites
        fig.add_hline(y=1.05, line_dash="dot", line_color="red", annotation_text="Límite Superior (1.05 PU)")
        fig.add_hline(y=0.95, line_dash="dot", line_color="red", annotation_text="Límite Inferior (0.95 PU)")
        
        fig.update_layout(
            title="Comparación de Voltajes con y sin GD",
            xaxis_title="Barra.Fase",
            yaxis_title="Voltaje (PU)",
            height=500,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        # Crear tabla de pérdidas comparativa
        try:
            perdidas_sin_kw = float(resumen_sin_gd["Pérdidas Totales (kW)"])
            perdidas_con_kw = float(resumen_con_gd["Pérdidas Totales (kW)"])
            diferencia = perdidas_con_kw - perdidas_sin_kw
            porcentaje = (diferencia / carga_valida(perdidas_sin_kw)) * 100
            
            color_alert = "success" if diferencia < 0 else "warning"
            icono = "arrow-down" if diferencia < 0 else "arrow-up"
            
            tabla_perdidas = html.Div([
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Pérdidas sin GD"),
                            dbc.CardBody([
                                html.H4(f"{perdidas_sin_kw:.2f} kW", className="card-title")
                            ])
                        ])
                    ], width=4),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Pérdidas con GD"),
                            dbc.CardBody([
                                html.H4(f"{perdidas_con_kw:.2f} kW", className="card-title")
                            ])
                        ])
                    ], width=4),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Diferencia"),
                            dbc.CardBody([
                                html.H4(f"{diferencia:+.2f} kW", className="card-title"),
                                html.P(f"{porcentaje:+.1f}%", className="card-text")
                            ])
                        ], color=color_alert, inverse=True)
                    ], width=4)
                ]),
                dbc.Alert(
                    [
                        html.I(className=f"fas fa-{icono} me-2"),
                        f"Las pérdidas {'disminuyeron' if diferencia < 0 else 'aumentaron'} en {abs(diferencia):.2f} kW ({abs(porcentaje):.1f}%)"
                    ],
                    color=color_alert,
                    className="mt-3"
                )
            ])
        except:
            tabla_perdidas = dbc.Alert("Error al calcular las pérdidas", color="danger")
        
        return fig, "", tabla_html, tabla_perdidas