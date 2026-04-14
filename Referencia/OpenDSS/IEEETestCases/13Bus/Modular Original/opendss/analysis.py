import pandas as pd
import dss

def carga_valida(total_power_kw):
    """Evitar división por cero en cálculos de porcentaje"""
    if abs(total_power_kw) < 1e-3:
        return 1e-3
    return abs(total_power_kw)

def obtener_loss_table(circuit):
    """Obtener tabla de pérdidas del circuito"""
    elementos = []
    tipos = ["Lines", "Transformers", "Capacitors"]

    total_kw = round(circuit.Losses[0] / 1000, 6)
    total_kvar = round(circuit.Losses[1] / 1000, 6)
    carga_total_kw = round(circuit.TotalPower[0] / 1000, 6)

    for tipo in tipos:
        coleccion = getattr(circuit, tipo)
        nombres = list(coleccion.AllNames)
        for nombre in nombres:
            full_name = f"{tipo[:-1]}.{nombre}"
            circuit.SetActiveElement(full_name)
            try:
                perdidas = circuit.ActiveCktElement.Losses
                kw = round(perdidas[0] / 1000, 5)
                kvar = round(perdidas[1] / 1000, 5)
                porcentaje = round((kw / carga_valida(carga_total_kw)) * 100, 2) if carga_total_kw else 0
            except:
                kw = kvar = porcentaje = 0.0

            elementos.append([tipo, nombre, kw, porcentaje, kvar])

    resumen = {
        "Pérdidas Totales (kW)": f"{total_kw}",
        "Pérdidas Totales (kvar)": f"{total_kvar}",
        "Potencia Total de Carga (kW)": f"{carga_total_kw}"
    }

    columnas = ["Tipo", "Elemento", "kW Pérdida", "% of Power", "kvar Pérdida"]
    return pd.DataFrame(elementos, columns=columnas), resumen

def obtener_perfil_voltajes(circuit):
    """Obtener perfil de voltajes de todas las barras"""
    barras = circuit.AllBusNames
    voltajes_dict = {}
    
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

    all_keys = [f"{b}.{f}" for b in barras for f in [1, 2, 3]]
    voltajes_completos = {k: voltajes_dict.get(k, None) for k in all_keys}
    return pd.DataFrame({"Barra.Fase": voltajes_completos.keys(), "VoltajePU": voltajes_completos.values()})

def obtener_fases_por_barra(circuit):
    """Obtener las fases disponibles por barra"""
    barras = circuit.AllBusNames
    barras_fases_disponibles = {}
    
    for barra in barras:
        circuit.SetActiveBus(barra)
        nodos = circuit.ActiveBus.Nodes
        barras_fases_disponibles[barra] = nodos
        
    return barras_fases_disponibles

def reiniciar_circuito(engine):
    """Reiniciar el circuito OpenDSS"""
    text = engine.Text
    text.Command = "Clear"
    text.Command = "Redirect IEEE13Nodeckt.dss"
    text.Command = "Solve"