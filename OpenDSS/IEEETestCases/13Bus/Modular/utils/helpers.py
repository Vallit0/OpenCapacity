import re

def clean_dss_content(dss_text: str) -> str:
    """
    Limpia el contenido de un archivo .dss eliminando parámetros inválidos 
    en objetos como LineCode (ejemplo: basekv).
    """
    cleaned_lines = []
    for line in dss_text.splitlines():
        # Ignorar comentarios
        if line.strip().startswith("!"):
            cleaned_lines.append(line)
            continue
        
        # Si es definición de LineCode con basekv (incorrecto en OpenDSS)
        if line.lower().startswith("new linecode") and "basekv" in line.lower():
            # Quitar el parámetro basekv usando regex
            cleaned_line = re.sub(r"\s*basekv\s*=\s*[\d\.]+", "", line, flags=re.IGNORECASE)
            cleaned_lines.append(cleaned_line.strip())
        else:
            cleaned_lines.append(line)
    
    return "\n".join(cleaned_lines)


def carga_valida(total_power_kw):
    """Validar carga para evitar división por cero"""
    if abs(total_power_kw) < 1e-3:
        return 1e-3
    return abs(total_power_kw)

def aplicar_generador(text, barra, fases, kw, tipo_gd, kv_ln, kv_ll):
    """Aplicar generador al circuito"""
    try:
        # Eliminar generador existente si existe
        if any(g.lower() == 'gd' for g in text.ActiveCircuit.Generators.AllNames):
            text.Command = "Remove Generator.GD"
    except:
        pass
    
    # Aplicar nuevo generador según el tipo
    if tipo_gd == "trifasica":
        text.Command = f"New Generator.GD Bus1={barra} Phases=3 kV={kv_ll:.3f} kW={kw} kvar=0.0 Model=1"
    elif tipo_gd == "bifasica":
        fases_str = ".".join(str(f) for f in fases)
        text.Command = f"New Generator.GD Bus1={barra}.{fases_str} Phases=2 kV={kv_ll:.3f} kW={kw} kvar=0.0 Model=1"
    else:
        text.Command = f"New Generator.GD Bus1={barra}.{fases[0]} Phases=1 kV={kv_ln:.3f} kW={kw} kvar=0.0 Model=1"
    
    text.Command = "Solve"