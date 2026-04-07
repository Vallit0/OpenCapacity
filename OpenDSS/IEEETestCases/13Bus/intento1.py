import opendssdirect as dss
import pandas as pd

# Función para obtener todas las barras del sistema
def obtener_barras():
    dss.Text.Command("clear")
    dss.Text.Command("redirect IEEE13Nodeckt.dss")
    return dss.Circuit.AllBusNames()

# Función para obtener voltajes en PU por fase verificando las fases disponibles
def obtener_voltajes_por_fase():
    barras = dss.Circuit.AllBusNames()
    voltajes_por_fase = {}

    for barra in barras:
        dss.Circuit.SetActiveBus(barra)
        voltajes = dss.Bus.PuVoltage()
        fases_disponibles = dss.Bus.Nodes()
        
        voltajes_fase = {1: None, 2: None, 3: None}
        
        for i, fase in enumerate(fases_disponibles):
            V_real = voltajes[2 * i]
            V_imag = voltajes[2 * i + 1]
            V_pu = (V_real**2 + V_imag**2) ** 0.5
            voltajes_fase[fase] = V_pu if V_pu > 1e-3 else 0.0
        
        voltajes_por_fase[barra] = voltajes_fase

    return voltajes_por_fase

# Función para obtener las pérdidas totales del sistema
def obtener_perdidas():
    perdidas = dss.Circuit.Losses()
    P_perdidas_kW = perdidas[0] / 1000.0  # Convertir de W a kW
    return round(P_perdidas_kW, 6)

# Detección precisa de fases activas
def obtener_tipo_fases(barra):
    dss.Circuit.SetActiveBus(barra)
    voltajes = dss.Bus.PuVoltage()
    nodos = dss.Bus.Nodes()
    fases_activas = set()
    for i, nodo in enumerate(nodos):
        V_real = voltajes[2 * i]
        V_imag = voltajes[2 * i + 1]
        V_mag = (V_real**2 + V_imag**2) ** 0.5
        if V_mag > 1e-3:
            fases_activas.add(nodo)
    return len(fases_activas), sorted(fases_activas)

# Función para agregar GD según el número de fases en la barra
def agregar_generacion_distribuida(barra, potencia):
    dss.Circuit.SetActiveBus(barra)
    fases = dss.Bus.Nodes()
    n_fases = len(fases)

    if n_fases == 3:
        dss.Text.Command(f"New Generator.PV Bus1={barra} Phases=3 kV=4.16 kW={potencia} kvar=0.0 Model=1")
    elif n_fases == 2:
        pot_fase = potencia / 2.0
        for i, fase in enumerate(fases):
            dss.Text.Command(f"New Generator.PV_fase{fases[i]} Bus1={barra}.{fases[i]} Phases=1 kV=2.4 kW={pot_fase} kvar=0.0 Model=1")
    elif n_fases == 1:
        dss.Text.Command(f"New Generator.PV_fase{fases[0]} Bus1={barra}.{fases[0]} Phases=1 kV=2.4 kW={potencia} kvar=0.0 Model=1")
    else:
        print("⚠️ No se puede determinar el número de fases de la barra.")

# Evaluar una barra y encontrar su capacidad de hospedaje
def evaluar_barra(barra):
    barras_disponibles = obtener_barras()
    n_fases, fases_activas = obtener_tipo_fases(barra)
    base_perdidas = obtener_perdidas()
    base_voltajes = obtener_voltajes_por_fase()
    voltajes_base = base_voltajes.get(barra, {})

    potencia = 0
    paso = 200
    max_capacidad = 0
    perdidas_final = base_perdidas
    voltajes_final = voltajes_base

    # Iteración inicial: encontrar el punto donde la violación ocurre
    while True:
        potencia += paso
        obtener_barras()
        agregar_generacion_distribuida(barra, potencia)
        dss.Text.Command("solve")
        voltajes = obtener_voltajes_por_fase().get(barra, {})

        if hay_violaciones(voltajes):
            potencia -= paso  # Retroceder cuando se detecta una violación
            break
        max_capacidad = potencia
        perdidas_final = obtener_perdidas()
        voltajes_final = voltajes

    # Ajuste fino para encontrar el valor exacto de potencia antes de la violación
    precision = 50  # Este valor puede ser ajustado
    while True:
        potencia += precision
        obtener_barras()
        agregar_generacion_distribuida(barra, potencia)
        dss.Text.Command("solve")
        voltajes = obtener_voltajes_por_fase().get(barra, {})

        if hay_violaciones(voltajes):
            potencia -= precision  # Retroceder si se detecta violación
            break
        max_capacidad = potencia
        perdidas_final = obtener_perdidas()
        voltajes_final = voltajes

    return {
        "Barra": barra,
        "Fases": n_fases,
        "Fase(s)": ",".join(str(f) for f in fases_activas),
        "CapacidadHospedaje_kW": max_capacidad,
        "Perdidas_Base_kW": base_perdidas,
        "Perdidas_Final_kW": perdidas_final,
    }

# Verificar violaciones de voltaje
def hay_violaciones(voltajes):
    for v in voltajes.values():
        if isinstance(v, float) and (v < 0.950000 or v > 1.050000):
            return True
    return False

# Función principal
def main():
    obtener_barras()
    barras = dss.Circuit.AllBusNames()
    resultados = []

    for barra in barras:
        print(f"🔍 Evaluando barra {barra}...")
        resultado = evaluar_barra(barra)
        resultados.append(resultado)

    df = pd.DataFrame(resultados)
    df.to_excel("capacidad_hospedaje.xlsx", index=False)
    print("\n✅ Resultados guardados en 'capacidad_hospedaje.xlsx'.")

if __name__ == "__main__":
    main()
