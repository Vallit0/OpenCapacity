import dss
import pandas as pd
import os
import tempfile
import shutil
import re

# Contenido por defecto para linecodes (tu código original)
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
def clean_dss_content(dss_text: str):
    """Limpia contenido DSS de parámetros inválidos"""
    cleaned_lines = []
    corrections = []
    
    lines = dss_text.split('\n')
    for line in lines:
        stripped = line.strip()
        
        # Eliminar basekv solo de linecodes
        if stripped.lower().startswith('new linecode') and 'basekv' in stripped.lower():
            cleaned = re.sub(r'\bbasekv\s*=\s*[\d\.]+\s*', '', stripped, flags=re.IGNORECASE)
            if cleaned != stripped:
                corrections.append(f"Removed basekv from: {stripped}")
            cleaned_lines.append(cleaned)
        else:
            cleaned_lines.append(line)
    
    return "\n".join(cleaned_lines), corrections

def preprocess_dss_content(content):
    """Preprocesa contenido DSS"""
    cleaned_content, corrections = clean_dss_content(content)
    
    # Eliminar referencias externas
    cleaned_content = re.sub(r'(?i).*buscoords.*\.csv.*\n?', '', cleaned_content)
    cleaned_content = re.sub(r'(?i).*redirect\s+ieeelinecodes\.dss.*\n?', '', cleaned_content)
    
    return cleaned_content, corrections

def initialize_dss():
    """Inicializa motor OpenDSS"""
    engine = dss.DSS
    engine.Start(0)
    return engine, engine.Text, engine.ActiveCircuit, engine.ActiveCircuit.Solution

def load_dss_files(main_dss_content, linecodes_content=None, busxy_content=None):
    """Carga archivos DSS (versión simplificada)"""
    engine, text, circuit, solution = initialize_dss()
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Preprocesar contenido
        processed_content, corrections = preprocess_dss_content(main_dss_content)
        
        # Guardar archivo principal
        main_path = os.path.join(temp_dir, "circuit.dss")
        with open(main_path, 'w', encoding='utf-8') as f:
            f.write(processed_content)
        
        # Compilar
        text.Command = "Clear"
        text.Command = f"Compile {main_path}"
        solution.Solve()
        
        return engine, text, circuit, solution, corrections
        
    except Exception as e:
        raise Exception(f"Error loading DSS files: {str(e)}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)