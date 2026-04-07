from dash import dcc, html, Input, Output, State, callback_context
import plotly.graph_objs as go
from utils.helpers import carga_valida, aplicar_generador
import plotly.graph_objects as go
import pandas as pd
from analysis_module import OpenDSSAnalyzer

def register_callbacks(app):
    @app.callback(
        Output('fase-gd', 'options'),
        Output('fase-gd', 'value'),
        Output('info-barra', 'children'),
        Input('barra-gd', 'value'),
        State('analysis-data', 'data')
    )
    def actualizar_fases(barra, analysis_data):
        if not barra or 'error' in analysis_data:
            return [], None, ""
        
        barras_fases_disponibles = analysis_data.get('barras_fases_disponibles', {})
        fases = barras_fases_disponibles.get(barra, [])
        
        info_texto = f"Barra '{barra}': {len(fases)} fase(s) disponibles"
        options = [{"label": f"Fase {f}", "value": f} for f in fases]
        
        return options, None, info_texto

    @app.callback(
        Output('grafico-comparativo', 'figure'),
        Output('mensaje-validacion', 'children'),
        Output('tabla-violaciones', 'children'),
        Output('tabla-perdidas', 'children'),
        Input('btn-aplicar', 'n_clicks'),
        State('barra-gd', 'value'),
        State('fase-gd', 'value'),
        State('potencia-gd', 'value'),
        State('analysis-data', 'data'),
        prevent_initial_call=True
    )
    def simular_gd(n_clicks, barra, fase, potencia, analysis_data):
        if n_clicks == 0 or not barra or not fase or not potencia:
            return go.Figure(), "", "", ""
        
        if 'error' in analysis_data:
            return go.Figure(), "Error en los datos de análisis", "", ""
        
        try:
            # Crear analizador y cargar datos
            analyzer = OpenDSSAnalyzer()
            main_content = analysis_data.get('original_dss_content', '')
            
            if not main_content:
                return go.Figure(), "No se encontró contenido DSS", "", ""
            
            # Ejecutar simulación con GD
            analyzer.reiniciar_circuito(main_content)
            
            # Aplicar GD
            analyzer.circuit.SetActiveBus(barra)
            kv_ln = analyzer.circuit.ActiveBus.kVBase
            fases_disponibles = analyzer.circuit.ActiveBus.Nodes
            
            if len(fases_disponibles) == 3:
                # GD trifásica
                kv = kv_ln * (3**0.5)
                analyzer.text.Command = f"New Generator.GD Bus1={barra} Phases=3 kV={kv:.3f} kW={potencia} kvar=0 Model=1"
            elif len(fases_disponibles) == 2:
                # GD bifásica
                kv = kv_ln * 2
                fases_str = ".".join(str(f) for f in fases_disponibles)
                analyzer.text.Command = f"New Generator.GD Bus1={barra}.{fases_str} Phases=2 kV={kv:.3f} kW={potencia} kvar=0 Model=1"
            else:
                # GD monofásica
                analyzer.text.Command = f"New Generator.GD Bus1={barra}.{fase} Phases=1 kV={kv_ln:.3f} kW={potencia} kvar=0 Model=1"
            
            analyzer.text.Command = "Solve"
            
            # Obtener resultados
            voltajes_con_gd = analyzer.obtener_perfil_voltajes()
            perdidas_con_gd_df, resumen_con_gd = analyzer.obtener_loss_table()
            
            # Crear gráfico comparativo
            fig = go.Figure()
            
            # Datos originales (sin GD)
            voltajes_sin_gd = analysis_data.get('voltajes_df', [])
            if voltajes_sin_gd and voltajes_con_gd is not None:
                df_sin_gd = pd.DataFrame(voltajes_sin_gd)
                df_con_gd = voltajes_con_gd
                
                fig.add_trace(go.Bar(
                    x=df_sin_gd['Barra.Fase'],
                    y=df_sin_gd['VoltajePU'],
                    name='Sin GD',
                    marker_color='blue'
                ))
                
                fig.add_trace(go.Bar(
                    x=df_con_gd['Barra.Fase'],
                    y=df_con_gd['VoltajePU'],
                    name='Con GD',
                    marker_color='orange'
                ))
            
            fig.update_layout(
                title="Comparación de Voltajes con/sin GD",
                yaxis_title="Voltaje PU",
                xaxis_title="Barra.Fase",
                barmode='group'
            )
            
            # Verificar violaciones
            violaciones = []
            for barra_name in analyzer.barras:
                analyzer.circuit.SetActiveBus(barra_name)
                pu = analyzer.circuit.ActiveBus.puVoltages
                for mag in [round((pu[2*i]**2 + pu[2*i+1]**2)**0.5, 6) for i in range(len(analyzer.circuit.ActiveBus.Nodes))]:
                    if mag < 0.95 or mag > 1.05:
                        violaciones.append({
                            'Barra': barra_name,
                            'Voltaje': mag,
                            'Tipo': 'Bajo' if mag < 0.95 else 'Alto'
                        })
            
            # Crear tabla de violaciones
            if violaciones:
                tabla_violaciones = [
                    html.H5("Violaciones de Voltaje Detectadas"),
                    html.Table([
                        html.Thead(html.Tr([
                            html.Th("Barra"), html.Th("Voltaje PU"), html.Th("Tipo")
                        ])),
                        html.Tbody([
                            html.Tr([
                                html.Td(v['Barra']),
                                html.Td(f"{v['Voltaje']:.6f}"),
                                html.Td(v['Tipo'])
                            ]) for v in violaciones
                        ])
                    ], className="table table-bordered table-sm")
                ]
            else:
                tabla_violaciones = html.P("No se detectaron violaciones de voltaje", 
                                         className="text-success")
            
            # Crear tabla de pérdidas comparativa
            perdidas_sin_gd_df = analysis_data.get('perdidas_sin_gd_df', [])
            if perdidas_sin_gd_df and perdidas_con_gd_df is not None:
                df_comparativo = pd.merge(
                    pd.DataFrame(perdidas_sin_gd_df),
                    perdidas_con_gd_df,
                    on=['Tipo', 'Elemento'],
                    suffixes=('_sin_gd', '_con_gd')
                )
                
                tabla_perdidas = [
                    html.H5("Comparación de Pérdidas"),
                    html.Table([
                        html.Thead(html.Tr([
                            html.Th("Elemento"), html.Th("kW Sin GD"), html.Th("kW Con GD")
                        ])),
                        html.Tbody([
                            html.Tr([
                                html.Td(f"{row['Tipo']}.{row['Elemento']}"),
                                html.Td(f"{row['kW Pérdida_sin_gd']}"),
                                html.Td(f"{row['kW Pérdida_con_gd']}")
                            ]) for _, row in df_comparativo.iterrows()
                        ])
                    ], className="table table-bordered table-sm")
                ]
            else:
                tabla_perdidas = html.P("No se pudieron comparar las pérdidas", 
                                      className="text-warning")
            
            return fig, "", tabla_violaciones, tabla_perdidas
            
        except Exception as e:
            return go.Figure(), f"Error en la simulación: {str(e)}", "", ""