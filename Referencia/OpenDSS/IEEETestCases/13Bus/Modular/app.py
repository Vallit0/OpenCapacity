import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
from components import welcome, layout
from analysis_module import OpenDSSAnalyzer
import json
import base64
import os
import tempfile

external_stylesheets = [dbc.themes.FLATLY]
app = dash.Dash(__name__, 
                external_stylesheets=external_stylesheets,
                suppress_callback_exceptions=True)
app.title = "Dashboard OpenDSS - Análisis de Red IEEE 13 Nodos"

# Layout inicial
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='analysis-data'),
    dcc.Store(id='dss-file-store', data={}),
    dcc.Interval(id='process-interval', interval=1000, disabled=True, n_intervals=0),
    html.Div(id='page-content')
])

# Callback para cambiar entre pantallas
@app.callback(
    Output('page-content', 'children'),
    [Input('url', 'pathname')],
    [State('analysis-data', 'data')]
)
def display_page(pathname, analysis_data):
    if pathname == '/analyze' and analysis_data:
        return layout.create_layout(analysis_data)
    elif pathname == '/analyze':
        return html.Div([
            dbc.Spinner(size="lg", color="primary", 
                       children=html.Div([
                           html.H3("Procesando archivos OpenDSS...", className="text-center mt-4"),
                           html.P("Esto puede tomar varios segundos.", className="text-center text-muted")
                       ]))
        ], className="text-center mt-5")
    else:
        return welcome.create_welcome_screen()

# Callbacks para manejar la subida de archivos
@app.callback(
    [Output('output-main-dss', 'children'),
     Output('output-linecodes-dss', 'children'),
     Output('output-busxy-csv', 'children'),
     Output('dss-file-store', 'data')],
    [Input('upload-main-dss', 'contents'),
     Input('upload-linecodes-dss', 'contents'),
     Input('upload-busxy-csv', 'contents')],
    [State('upload-main-dss', 'filename'),
     State('upload-linecodes-dss', 'filename'),
     State('upload-busxy-csv', 'filename'),
     State('dss-file-store', 'data')]
)
def handle_multiple_file_upload(main_content, linecodes_content, busxy_content, 
                               main_filename, linecodes_filename, busxy_filename, 
                               existing_data):
    ctx = callback_context
    if not ctx.triggered:
        return "", "", "", existing_data or {}
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    file_data = existing_data.copy() if existing_data else {}
    
    def decode_content(content, filename):
        """Decodificar contenido subido"""
        try:
            content_type, content_string = content.split(',')
            decoded = base64.b64decode(content_string)
            return decoded.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Error al procesar {filename}: {str(e)}")
    
    try:
        if trigger_id == 'upload-main-dss' and main_content:
            if not main_filename.lower().endswith('.dss'):
                return (dbc.Alert("❌ El archivo debe tener extensión .dss", color="danger", className="py-1"), 
                        "", "", file_data)
            
            content = decode_content(main_content, main_filename)
            file_data['main_dss'] = {'content': content, 'filename': main_filename}
            return (dbc.Alert(f"✓ {main_filename}", color="success", className="py-1"), 
                    "", "", file_data)
                    
        elif trigger_id == 'upload-linecodes-dss' and linecodes_content:
            if not linecodes_filename.lower().endswith('.dss'):
                return ("", 
                        dbc.Alert("❌ El archivo debe tener extensión .dss", color="danger", className="py-1"), 
                        "", file_data)
            
            content = decode_content(linecodes_content, linecodes_filename)
            file_data['linecodes_dss'] = {'content': content, 'filename': linecodes_filename}
            return ("", 
                    dbc.Alert(f"✓ {linecodes_filename}", color="success", className="py-1"), 
                    "", file_data)
                    
        elif trigger_id == 'upload-busxy-csv' and busxy_content:
            if not busxy_filename.lower().endswith('.csv'):
                return ("", "", 
                        dbc.Alert("❌ El archivo debe tener extensión .csv", color="danger", className="py-1"), 
                        file_data)
            
            content = decode_content(busxy_content, busxy_filename)
            file_data['busxy_csv'] = {'content': content, 'filename': busxy_filename}
            return ("", "", 
                    dbc.Alert(f"✓ {busxy_filename}", color="success", className="py-1"), 
                    file_data)
                    
    except Exception as e:
        error_alert = dbc.Alert(f"Error: {str(e)}", color="danger", className="py-1")
        if trigger_id == 'upload-main-dss':
            return error_alert, "", "", file_data
        elif trigger_id == 'upload-linecodes-dss':
            return "", error_alert, "", file_data
        elif trigger_id == 'upload-busxy-csv':
            return "", "", error_alert, file_data
    
    return "", "", "", file_data

# Callback para habilitar el botón de análisis
@app.callback(
    Output('output-file-upload', 'children'),
    [Input('dss-file-store', 'data')]
)
def enable_analyze_button(file_data):
    if file_data and 'main_dss' in file_data:
        return html.Div([
            dbc.Alert("✓ Archivos necesarios cargados correctamente", color="success"),
            dbc.Button("Analizar Archivos", id="btn-analyze", color="primary", size="lg", className="mt-2")
        ])
    return dbc.Alert("⚠️ Cargue al menos el archivo principal del circuito (.dss)", color="danger")

# Callback para el botón de análisis
@app.callback(
    [Output('url', 'pathname'),
     Output('process-interval', 'disabled')],
    [Input('btn-analyze', 'n_clicks')],
    [State('dss-file-store', 'data')],
    prevent_initial_call=True
)
def navigate_to_analysis(n_clicks, file_data):
    if n_clicks and file_data and 'main_dss' in file_data:
        return '/analyze', False
    return dash.no_update, True

# Callback para procesar los archivos DSS
app.callback(
    [Output('analysis-data', 'data'),
     Output('process-interval', 'disabled', allow_duplicate=True)],
    [Input('process-interval', 'n_intervals')],
    [State('dss-file-store', 'data')],
    prevent_initial_call=True
)
def process_dss_files(n_intervals, file_data):
    if n_intervals == 1 and file_data and 'main_dss' in file_data:
        try:
            print("🔄 Iniciando procesamiento de archivos DSS...")
            analyzer = OpenDSSAnalyzer()
            
            # Solo procesar, no usar yield para outputs que no existen
            analysis_results = analyzer.ejecutar_analisis_completo(
                file_data['main_dss']['content']
            )
            
            print("✅ Análisis completado exitosamente")
            return analysis_results, True
            
        except Exception as e:
            error_msg = f"Error al procesar los archivos: {str(e)}"
            print(f"❌ {error_msg}")
            error_data = {'error': error_msg}
            return error_data, True
    
    return dash.no_update, dash.no_update
# Importar callbacks modulares
from components import callbacks
callbacks.register_callbacks(app)

if __name__ == '__main__':
    app.run(debug=True, threaded=True)