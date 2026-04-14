import pandas as pd

def obtener_perfil_voltajes(circuit):
    """Obtiene perfil de voltajes del circuito"""
    voltajes_dict = {}
    barras = circuit.AllBusNames
    
    for barra in barras:
        circuit.SetActiveBus(barra)
        pu_volt = circuit.ActiveBus.puVoltages
        nodos = circuit.ActiveBus.Nodes
        
        for idx in range(len(nodos)):
            fase = nodos[idx]
            real = pu_volt[2*idx]
            imag = pu_volt[2*idx + 1]
            mag = round((real**2 + imag**2)**0.5, 6)
            key = f"{barra}.{fase}"
            voltajes_dict[key] = mag
    
    # DataFrame completo
    all_keys = [f"{b}.{f}" for b in barras for f in [1, 2, 3]]
    voltajes_completos = {k: voltajes_dict.get(k, None) for k in all_keys}
    
    return pd.DataFrame({
        "Barra.Fase": list(voltajes_completos.keys()), 
        "VoltajePU": list(voltajes_completos.values())
    })

def obtener_fases_por_barra(circuit):
    """Obtiene fases disponibles por barra"""
    barras_fases = {}
    for barra in circuit.AllBusNames:
        circuit.SetActiveBus(barra)
        barras_fases[barra] = circuit.ActiveBus.Nodes
    return barras_fases