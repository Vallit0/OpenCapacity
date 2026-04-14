import pandas as pd
import dss

def analizar_limites_gd(circuit, text):
    """Analizar límites de generación distribuida sin causar violaciones"""
    from ..utils.helpers import carga_valida
    
    # Pre-cache de información de líneas
    lineas_info = []
    for nombre in circuit.Lines.AllNames:
        circuit.Lines.Name = nombre
        fases = circuit.Lines.Phases
        norm_amps = circuit.Lines.EmergAmps or 1.0
        bus1 = circuit.Lines.Bus1.split('.')[0]
        circuit.SetActiveBus(bus1)
        kv_base = circuit.ActiveBus.kVBase or 1.0
        kv = kv_base * 1.732 if fases > 1 else kv_base
        s_nom = kv * norm_amps
        lineas_info.append((nombre, norm_amps, round(s_nom, 2)))
    
    barras = circuit.AllBusNames
    limites_gd = []
    violaciones_corriente_por_barra_fase = {}
    
    for barra_gd in barras:
        circuit.SetActiveBus(barra_gd)
        nodos = sorted(circuit.ActiveBus.Nodes)
        kv_ln = circuit.ActiveBus.kVBase
        num_fases = len(nodos)
        
        # Determinar el tipo de GD según las fases disponibles
        if num_fases == 3:
            tipo_gd = "trifasica"
            kv = kv_ln * (3**0.5)
        elif num_fases == 2:
            tipo_gd = "bifasica"
            kv = kv_ln * 2
        else:
            tipo_gd = "monofasica"
            kv = kv_ln

        # Búsqueda binaria para encontrar el límite máximo
        low = 0
        high = 10000000
        best_kw = 0
        
        while low <= high:
            mid = (low + high) // 2
            reiniciar_circuito_partial(text)
            
            # Aplicar GD según el tipo
            if tipo_gd == "trifasica":
                text.Command = f"New Generator.GD Bus1={barra_gd} Phases=3 kV={kv:.3f} kW={mid} kvar=0 Model=1"
            elif tipo_gd == "bifasica":
                fases_str = ".".join(str(f) for f in nodos)
                text.Command = f"New Generator.GD Bus1={barra_gd}.{fases_str} Phases=2 kV={kv:.3f} kW={mid} kvar=0 Model=1"
            else:
                text.Command = f"New Generator.GD Bus1={barra_gd}.{nodos[0]} Phases=1 kV={kv:.3f} kW={mid} kvar=0 Model=1"
            
            text.Command = "Solve"
            
            # Verificación de violaciones
            violacion_voltaje = verificar_violaciones_voltaje(circuit, barras)
            violacion_corriente, violacion_potencia = verificar_violaciones_corriente_potencia(circuit, lineas_info)
            
            if not violacion_voltaje and not violacion_corriente and not violacion_potencia:
                best_kw = mid
                low = mid + 1
            else:
                high = mid - 1
        
        # Guardar resultados
        if num_fases == 1:
            limites_gd.append({"Barra": barra_gd, "Fase": nodos[0], "Max GD sin violacion (kW)": best_kw})
        else:
            for fase in nodos:
                limites_gd.append({"Barra": barra_gd, "Fase": fase, "Max GD sin violacion (kW)": best_kw})
    
    return pd.DataFrame(limites_gd), violaciones_corriente_por_barra_fase

def reiniciar_circuito_partial(text):
    """Reiniciar parcialmente el circuito"""
    text.Command = "Clear"
    text.Command = "Redirect IEEE13Nodeckt.dss"
    text.Command = "Solve"

def verificar_violaciones_voltaje(circuit, barras):
    """Verificar violaciones de voltaje"""
    violacion_voltaje = False
    for b in barras:
        circuit.SetActiveBus(b)
        pu = circuit.ActiveBus.puVoltages
        for mag in [round((pu[2*i]**2 + pu[2*i+1]**2)**0.5, 6) for i in range(len(circuit.ActiveBus.Nodes))]:
            if mag < 0.95 or mag > 1.05:
                violacion_voltaje = True
                break
        if violacion_voltaje:
            break
    return violacion_voltaje

def verificar_violaciones_corriente_potencia(circuit, lineas_info):
    """Verificar violaciones de corriente y potencia"""
    violacion_corriente = False
    violacion_potencia = False
    
    for nombre, norm_amps, s_nom in lineas_info:
        circuit.Lines.Name = nombre
        circuit.SetActiveElement(f"Line.{nombre}")
        mags = circuit.ActiveCktElement.CurrentsMagAng[::2]
        
        # Obtener información de la línea
        bus1 = circuit.Lines.Bus1.split('.')[0]
        circuit.SetActiveBus(bus1)
        kv_base = circuit.ActiveBus.kVBase or 1.0
        fases_linea = circuit.Lines.Phases
        
        # Calcular potencia aparente
        for i, mag in enumerate(mags):
            # Verificación de corriente
            if mag > norm_amps:
                violacion_corriente = True
            
            # Verificación de potencia
            if fases_linea > 1:
                s_real = (3**0.5) * kv_base * mag
            else:
                s_real = kv_base * mag
            
            if s_real > s_nom:
                violacion_potencia = True
        
        if violacion_corriente or violacion_potencia:
            break
    
    return violacion_corriente, violacion_potencia