import dss
import pandas as pd
from . import analysis, gd_analysis
import os
import tempfile
import shutil
import re

# Contenido por defecto para IEEELineCodes.DSS
# Contenido por defecto para IEEELineCodes.DSS (extraído del archivo proporcionado)
DEFAULT_LINECODES = """
! this file was corrected 9/16/2010 to match the values in Kersting's files

! These line codes are used in the 123-bus circuit

New linecode.1 nphases=3 BaseFreq=60
~ rmatrix = [0.086666667 | 0.029545455 0.088371212 | 0.02907197 0.029924242 0.087405303]
~ xmatrix = [0.204166667 | 0.095018939 0.198522727 | 0.072897727 0.080227273 0.201723485]
~ cmatrix = [2.851710072 | -0.920293787  3.004631862 | -0.350755566  -0.585011253 2.71134756]

New linecode.2 nphases=3 BaseFreq=60
~ rmatrix = [0.088371212 | 0.02992424  0.087405303 | 0.029545455 0.02907197 0.086666667]
~ xmatrix = [0.198522727 | 0.080227273  0.201723485 | 0.095018939 0.072897727 0.204166667]
~ cmatrix = [3.004631862 | -0.585011253 2.71134756 | -0.920293787  -0.350755566  2.851710072]

New linecode.3 nphases=3 BaseFreq=60
~ rmatrix = [0.087405303 | 0.02907197 0.086666667  | 0.029924242 0.029545455 0.088371212]
~ xmatrix = [0.201723485 | 0.072897727 0.204166667 | 0.080227273 0.095018939 0.198522727]
~ cmatrix = [2.71134756  | -0.350755566 2.851710072 | -0.585011253 -0.920293787 3.004631862]

New linecode.4 nphases=3 BaseFreq=60
~ rmatrix = [0.087405303 | 0.029924242 0.088371212 | 0.02907197   0.029545455 0.086666667]
~ xmatrix = [0.201723485 | 0.080227273 0.198522727 | 0.072897727 0.095018939 0.204166667]
~ cmatrix = [2.71134756  | -0.585011253 3.004631862 | -0.350755566 -0.920293787 2.851710072]

New linecode.5 nphases=3 BaseFreq=60
~ rmatrix = [0.088371212  |  0.029545455  0.086666667  |  0.029924242  0.02907197  0.087405303]
~ xmatrix = [0.198522727  |  0.095018939  0.204166667  |  0.080227273  0.072897727  0.201723485]
~ cmatrix = [3.004631862  | -0.920293787  2.851710072  |  -0.585011253  -0.350755566  2.71134756]

New linecode.6 nphases=3 BaseFreq=60
~ rmatrix = [0.086666667 | 0.02907197  0.087405303 | 0.029545455  0.029924242  0.088371212]
~ xmatrix = [0.204166667 | 0.072897727  0.201723485 | 0.095018939  0.080227273  0.198522727]
~ cmatrix = [2.851710072 | -0.350755566  2.71134756 | -0.920293787  -0.585011253  3.004631862]

New linecode.7 nphases=2 BaseFreq=60
~ rmatrix = [0.086666667 | 0.02907197  0.087405303]
~ xmatrix = [0.204166667 | 0.072897727  0.201723485]
~ cmatrix = [2.569829596 | -0.52995137  2.597460011]

New linecode.8 nphases=2 BaseFreq=60
~ rmatrix = [0.086666667 | 0.02907197  0.087405303]
~ xmatrix = [0.204166667 | 0.072897727  0.201723485]
~ cmatrix = [2.569829596 | -0.52995137  2.597460011]

New linecode.9 nphases=1 BaseFreq=60
~ rmatrix = [0.251742424]
~ xmatrix = [0.255208333]
~ cmatrix = [2.270366128]

New linecode.10 nphases=1 BaseFreq=60
~ rmatrix = [0.251742424]
~ xmatrix = [0.255208333]
~ cmatrix = [2.270366128]

New linecode.11 nphases=1 BaseFreq=60
~ rmatrix = [0.251742424]
~ xmatrix = [0.255208333]
~ cmatrix = [2.270366128]

New linecode.12 nphases=3 BaseFreq=60
~ rmatrix = [0.288049242 | 0.09844697  0.29032197 | 0.093257576  0.09844697  0.288049242]
~ xmatrix = [0.142443182 | 0.052556818  0.135643939 | 0.040852273  0.052556818  0.142443182]
~ cmatrix = [33.77150149 | 0  33.77150149 | 0  0  33.77150149]

! These line codes are used in the 34-node test feeder

New linecode.300 nphases=3 basefreq=60
~ rmatrix = [0.253181818   |  0.039791667     0.250719697  |   0.040340909      0.039128788     0.251780303]
~ xmatrix = [0.252708333   |  0.109450758     0.256988636  |   0.094981061      0.086950758     0.255132576]
~ CMATRIX = [2.680150309   | -0.769281006     2.5610381    |  -0.499507676     -0.312072984     2.455590387]

New linecode.301 nphases=3 basefreq=60
~ rmatrix = [0.365530303   |   0.04407197      0.36282197   |   0.04467803       0.043333333     0.363996212]
~ xmatrix = [0.267329545   |   0.122007576     0.270473485  |   0.107784091      0.099204545     0.269109848] 
~ cmatrix = [2.572492163   |  -0.72160598      2.464381882  |  -0.472329395     -0.298961096     2.368881119]

New linecode.302 nphases=1 basefreq=60
~ rmatrix = [0.530208]
~ xmatrix = [0.281345]
~ cmatrix = [2.12257]

New linecode.303 nphases=1 basefreq=60
~ rmatrix = [0.530208]
~ xmatrix = [0.281345]
~ cmatrix = [2.12257]

New linecode.304 nphases=1 basefreq=60
~ rmatrix = [0.363958]
~ xmatrix = [0.269167]
~ cmatrix = [2.1922]

! These are for the 13-node test feeder

New linecode.601 nphases=3 BaseFreq=60
~ rmatrix = [0.065625    | 0.029545455  0.063920455  | 0.029924242  0.02907197  0.064659091]
~ xmatrix = [0.192784091 | 0.095018939  0.19844697   | 0.080227273  0.072897727  0.195984848]
~ cmatrix = [3.164838036 | -1.002632425  2.993981593 | -0.632736516  -0.372608713  2.832670203]

New linecode.602 nphases=3 BaseFreq=60
~ rmatrix = [0.142537879 | 0.029924242  0.14157197   | 0.029545455  0.02907197  0.140833333]
~ xmatrix = [0.22375     | 0.080227273  0.226950758  | 0.095018939  0.072897727  0.229393939]
~ cmatrix = [2.863013423 | -0.543414918  2.602031589 | -0.8492585  -0.330962141  2.725162768]

New linecode.603 nphases=2 BaseFreq=60
~ rmatrix = [0.251780303 | 0.039128788  0.250719697]
~ xmatrix = [0.255132576 | 0.086950758  0.256988636]
~ cmatrix = [2.366017603 | -0.452083836  2.343963508]

New linecode.604 nphases=2 BaseFreq=60
~ rmatrix = [0.250719697 | 0.039128788   0.251780303]
~ xmatrix = [0.256988636  | 0.086950758  0.255132576]
~ cmatrix = [2.343963508 | -0.452083836 2.366017603]

New linecode.605 nphases=1 BaseFreq=60
~ rmatrix = [0.251742424]
~ xmatrix = [0.255208333]
~ cmatrix = [2.270366128]

New linecode.606 nphases=3 BaseFreq=60
~ rmatrix = [0.151174242 | 0.060454545  0.149450758 | 0.053958333  0.060454545  0.151174242]
~ xmatrix = [0.084526515 | 0.006212121  0.076534091 | -0.002708333  0.006212121  0.084526515]
~ cmatrix = [48.67459408 | 0  48.67459408 | 0  0  48.67459408]

New linecode.607 nphases=1 BaseFreq=60
~ rmatrix = [0.254261364]
~ xmatrix = [0.097045455]
~ cmatrix = [44.70661522]
"""
def validate_linecodes(content):
    """
    Validar específicamente que no haya parámetros basekv en LineCodes
    """
    lines = content.split('\n')
    in_linecode = False
    errors = []
    
    for i, line in enumerate(lines, start=1):
        stripped = line.strip().lower()
        
        # Detectar inicio de LineCode
        if stripped.startswith('new linecode'):
            in_linecode = True
            
        # Detectar fin de LineCode (nueva definición o línea vacía)
        elif in_linecode and (stripped.startswith('new ') or not stripped):
            in_linecode = False
            
        # Buscar basekv en LineCodes
        if in_linecode and 'basekv' in stripped:
            errors.append(f"Línea {i}: Parámetro basekv no permitido en LineCode: {line.strip()}")
    
    return errors

def clean_dss_content(dss_text: str):
    """
    Limpia el contenido de un archivo .dss eliminando parámetros inválidos
    en objetos LineCode (específicamente 'basekv').
    """
    cleaned_lines = []
    corrections = []
    
    lines = dss_text.split('\n')
    i = 0
    n = len(lines)
    
    while i < n:
        line = lines[i]
        stripped_line = line.strip()
        
        # Detectar si es un objeto LineCode
        if re.match(r'^\s*New\s+LineCode\.', stripped_line, re.IGNORECASE):
            # Procesar todas las líneas de este objeto LineCode (hasta la siguiente definición)
            linecode_lines = []
            j = i
            while j < n and (lines[j].strip().startswith('~') or 
                            (j == i) or  # La línea actual (New LineCode)
                            (j > i and not re.match(r'^\s*New\s+', lines[j].strip()))):
                linecode_lines.append(lines[j])
                j += 1
            
            # Limpiar cada línea del LineCode
            cleaned_linecode_lines = []
            for linecode_line in linecode_lines:
                # Eliminar basekv solo si está en esta línea
                if 'basekv' in linecode_line.lower():
                    original = linecode_line
                    # Eliminar el parámetro basekv y su valor
                    cleaned_line = re.sub(r'\s*basekv\s*=\s*[\d\.]+\s*', '', linecode_line, flags=re.IGNORECASE)
                    cleaned_line = re.sub(r'\s*basekv\s*[\d\.]+\s*', '', cleaned_line, flags=re.IGNORECASE)
                    if cleaned_line != original:
                        corrections.append(f"Se eliminó 'basekv' de: {original.strip()}")
                    cleaned_linecode_lines.append(cleaned_line)
                else:
                    cleaned_linecode_lines.append(linecode_line)
            
            cleaned_lines.extend(cleaned_linecode_lines)
            i = j  # Saltar al siguiente objeto
        else:
            # Para líneas que no son LineCode, mantenerlas intactas
            cleaned_lines.append(line)
            i += 1
    
    return "\n".join(cleaned_lines), corrections

def preprocess_dss_content(content):
    """
    Preprocesar el contenido DSS para IEEE 13 nodos
    """
    # Primero: buscar y solucionar específicamente LineCode.607
    processed_content, corrections_607 = find_and_fix_linecode_607(content)
    
    # Segundo: limpieza general de LineCodes
    processed_content, corrections_general = clean_dss_content(processed_content)
    
    # Combinar correcciones
    all_corrections = corrections_607 + corrections_general
    
    # Eliminar referencias a archivos externos
    processed_content = re.sub(r'(?i).*buscoords.*\.csv.*\n?', '', processed_content)
    processed_content = re.sub(r'(?i).*redirect\s+ieeelinecodes\.dss.*\n?', '', processed_content)
    
    # Buscar la línea del circuito para insertar linecodes después
    lines = processed_content.split('\n')
    circuit_line_index = -1
    
    for i, line in enumerate(lines):
        if re.search(r'(?i)^\s*new\s+circuit\.', line):
            circuit_line_index = i
            break
    
    # Limpiar y preparar linecodes por defecto
    cleaned_linecodes, linecode_corrections = clean_dss_content(DEFAULT_LINECODES)
    all_corrections.extend(linecode_corrections)
    
    if circuit_line_index >= 0:
        # Insertar linecodes después de la definición del circuito
        new_lines = lines[:circuit_line_index + 1]
        new_lines.append("")
        new_lines.append("! LineCodes integrados (reemplazan IEEELineCodes.dss)")
        new_lines.extend(cleaned_linecodes.strip().split('\n'))
        new_lines.extend(lines[circuit_line_index + 1:])
        return '\n'.join(new_lines), all_corrections
    else:
        return cleaned_linecodes + "\n\n" + processed_content, all_corrections

def initialize_dss():
    """Inicializar el motor OpenDSS"""
    engine = dss.DSS
    engine.Start(0)
    text = engine.Text
    circuit = engine.ActiveCircuit
    solution = circuit.Solution
    return engine, text, circuit, solution

def load_dss_files(main_dss_content, linecodes_content=None, busxy_content=None):
    """
    Cargar múltiples archivos DSS necesarios para la simulación
    """
    engine, text, circuit, solution = initialize_dss()
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 🔹 Preprocesamiento con correcciones
        processed_content, corrections = preprocess_dss_content(main_dss_content)
        
        # Guardar archivo procesado
        main_path = os.path.join(temp_dir, "IEEE13Nodeckt.dss")
        with open(main_path, 'w', encoding='utf-8') as main_file:
            main_file.write(processed_content)
        
        # Depuración: mostrar correcciones
        if corrections:
            print("🔧 Correcciones realizadas:")
            for correction in corrections:
                print(f"   - {correction}")
        
        # Depuración: buscar específicamente LineCode.607 en el archivo procesado
        with open(main_path, 'r') as f:
            content = f.read()
            if 'linecode.607' in content.lower():
                print("🔍 LineCode.607 encontrado en el archivo procesado:")
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'linecode.607' in line.lower():
                        print(f"   Línea {i+1}: {line.strip()}")
                        # Mostrar las siguientes 5 líneas también
                        for j in range(i+1, min(i+6, len(lines))):
                            print(f"   Línea {j+1}: {lines[j].strip()}")
                        break
        
        # Procesar linecodes adicionales si se proporcionaron
        if linecodes_content and linecodes_content.strip():
            cleaned_linecodes, linecode_corrections = clean_dss_content(linecodes_content)
            linecodes_path = os.path.join(temp_dir, "linecodes.dss")
            with open(linecodes_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_linecodes)
            
            if linecode_corrections:
                print("🔧 Correcciones en archivo de linecodes:")
                for correction in linecode_corrections:
                    print(f"   - {correction}")
        else:
            linecodes_path = None
        
        # Procesar coordenadas de buses si se proporcionaron
        if busxy_content and busxy_content.strip():
            busxy_path = os.path.join(temp_dir, "busxy.csv")
            with open(busxy_path, 'w', encoding='utf-8') as f:
                f.write(busxy_content)
        else:
            busxy_path = None
        
        # Cambiar al directorio temporal
        original_dir = os.getcwd()
        os.chdir(temp_dir)
        
        print(f"📁 Directorio temporal: {temp_dir}")
        print("📋 Archivos escritos:")
        for file in os.listdir(temp_dir):
            print(f"   - {file}")
        
        # Debug: mostrar primeras líneas del archivo DSS procesado
        print("🔍 Primeras 20 líneas del archivo DSS procesado:")
        with open(main_path, 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(lines[:20]):
                print(f"   {i+1:2d}: {line.rstrip()}")
        
        # Debug: mostrar líneas alrededor de LineCode.607
        print("🔍 Buscando LineCode.607 en el archivo:")
        for i, line in enumerate(lines):
            if 'linecode.607' in line.lower():
                start = max(0, i-2)
                end = min(len(lines), i+5)
                print(f"   LineCode.607 encontrado alrededor de la línea {i+1}:")
                for j in range(start, end):
                    marker = " >>> " if j == i else "     "
                    print(f"   {j+1:2d}{marker}{lines[j].rstrip()}")
                break
        
        # Compilar en OpenDSS
        text.Command = "Clear"
        text.Command = f"Compile {main_path}"
        
        # Si hay linecodes adicionales, compilarlos también
        if linecodes_path:
            text.Command = f"Compile {linecodes_path}"
        
        # Resolver el circuito
        solution.Solve()
        
        # Restaurar directorio original
        os.chdir(original_dir)

        return engine, text, circuit, solution, corrections
    
    except Exception as e:
        # Restaurar directorio original en caso de error
        if 'original_dir' in locals():
            os.chdir(original_dir)
        
        # Obtener información detallada del error de OpenDSS
        error_msg = str(e)
        try:
            error_msg += f"\n📋 Mensaje de OpenDSS: {text.Result}"
        except:
            pass
        
        print(f"❌ Error detallado: {error_msg}")
        
        # Depuración adicional: mostrar últimas líneas del archivo temporal
        try:
            if os.path.exists(main_path):
                print("🔍 Últimas 10 líneas del archivo DSS temporal:")
                with open(main_path, 'r') as f:
                    lines = f.readlines()
                    for line in lines[-10:]:
                        print(f"   {line.rstrip()}")
        except:
            pass
        
        raise Exception(error_msg)
    
    finally:
        # Limpiar directorio temporal
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass

def find_and_fix_linecode_607(content):
    """
    Busca específicamente LineCode.607 y elimina el parámetro basekv
    """
    lines = content.split('\n')
    cleaned_lines = []
    corrections = []
    found_linecode_607 = False
    
    for i, line in enumerate(lines):
        # Detectar LineCode.607
        if 'linecode.607' in line.lower():
            found_linecode_607 = True
            cleaned_lines.append(line)
            continue
        
        # Si estamos dentro de LineCode.607, buscar y eliminar basekv
        if found_linecode_607:
            if 'basekv' in line.lower():
                # Eliminar basekv de esta línea
                cleaned_line = re.sub(r'\s*basekv\s*=\s*[\d\.]+\s*', '', line, flags=re.IGNORECASE)
                cleaned_line = re.sub(r'\s*basekv\s*[\d\.]+\s*', '', cleaned_line, flags=re.IGNORECASE)
                if cleaned_line != line:
                    corrections.append(f"Se eliminó 'basekv' de LineCode.607 en línea {i+1}")
                cleaned_lines.append(cleaned_line)
                
                # Verificar si esta es la última línea del objeto
                if not line.strip().startswith('~'):
                    found_linecode_607 = False
            else:
                cleaned_lines.append(line)
                # Verificar si esta es la última línea del objeto
                if not line.strip().startswith('~'):
                    found_linecode_607 = False
        else:
            cleaned_lines.append(line)
    
    return "\n".join(cleaned_lines), corrections

def initialize_and_analyze(file_data):
    """
    Inicializar OpenDSS y realizar análisis con múltiples archivos
    """
    try:
        main_content = file_data.get('main_dss', '')
        if not main_content:
            raise ValueError("Se requiere el archivo principal del circuito (.dss)")
        
        # Validar LineCodes antes de procesar
        linecode_errors = validate_linecodes(main_content)
        if linecode_errors:
            print("⚠️ Advertencias de validación:")
            for error in linecode_errors:
                print(f"   - {error}")
        
        print("🔄 Cargando archivos en OpenDSS...")
        engine, text, circuit, solution, corrections = load_dss_files(
            main_content,
            file_data.get('linecodes_dss', ''),
            file_data.get('busxy_csv', '')
        )
        
        # Resto del código...
        
        print("✅ Archivos cargados exitosamente")
        print(f"📊 Circuito: {circuit.Name}")
        print(f"🏢 Número de buses: {len(circuit.AllBusNames)}")
        
        
        # Realizar análisis
        voltajes_df = analysis.obtener_perfil_voltajes(circuit)
        limites_gd, violaciones = gd_analysis.analizar_limites_gd(circuit, text)
        perdidas_sin_gd_df, resumen_sin_gd = analysis.obtener_loss_table(circuit)
        barras_fases_disponibles = analysis.obtener_fases_por_barra(circuit)
        
        analysis_data = {
            'voltajes_df': voltajes_df.to_dict('records'),
            'limites_gd': limites_gd.to_dict('records'),
            'perdidas_sin_gd_df': perdidas_sin_gd_df.to_dict('records'),
            'resumen_sin_gd': resumen_sin_gd,
            'barras': circuit.AllBusNames,
            'barras_fases_disponibles': barras_fases_disponibles,
            'circuit_info': {
                'name': circuit.Name,
                'num_buses': len(circuit.AllBusNames),
                'num_elements': circuit.NumElements,
                'converged': solution.Converged,
                'total_power_kw': circuit.TotalPower[0]/1000,
                'total_power_kvar': circuit.TotalPower[1]/1000
            },
            'corrections': corrections  # 🔹 se reportan correcciones realizadas
        }
        
        return analysis_data
    
    except Exception as e:
        print(f"❌ Error en el análisis: {str(e)}")
        try:
            engine, text, circuit, solution = initialize_dss()
            print(f"📋 Mensaje de OpenDSS: {text.Result}")
        except:
            pass
        raise e

def test_opendss_connection():
    """Función para probar la conexión con OpenDSS"""
    try:
        engine, text, circuit, solution = initialize_dss()
        print("✅ OpenDSS inicializado correctamente")
        print(f"Versión de OpenDSS: {engine.Version}")
        return True
    except Exception as e:
        print(f"❌ Error al inicializar OpenDSS: {e}")
        return False

def get_circuit_summary(circuit):
    """Obtener resumen del circuito"""
    summary = {
        'Nombre': circuit.Name,
        'Número de buses': len(circuit.AllBusNames),
        'Número de elementos': circuit.NumElements,
        'Pérdidas totales (kW)': round(circuit.Losses[0] / 1000, 2),
        'Potencia de carga total (kW)': round(circuit.TotalPower[0] / 1000, 2)
    }
    return summary