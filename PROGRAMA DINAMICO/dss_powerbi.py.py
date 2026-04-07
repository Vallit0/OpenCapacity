import opendssdirect as dss
import pandas as pd
import sys
import json

def obtener_barras():
    dss.Text.Command("clear")
    dss.Text.Command("redirect IEEE13Nodeckt.dss")  # Asegúrate de que la ruta del .dss sea correcta
    return dss.Circuit.AllBusNames()

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
            voltajes_fase[fase] = round(V_pu, 4) if V_pu > 1e-3 else 0.0
        voltajes_por_fase[barra] = voltajes_fase
    return voltajes_por_fase

def obtener_perdidas():
    perdidas = dss.Circuit.Losses()
    return round(perdidas[0] / 1000.0, 4)  # kW

def agregar_generacion_distribuida(barra, potencia):
    dss.Circuit.SetActiveBus(barra)
    fases = dss.Bus.Nodes()
    n_fases = len(fases)
    if n_fases == 3:
        dss.Text.Command(f"New Generator.PV Bus1={barra} Phases=3 kV=4.16 kW={potencia} kvar=0.0 Model=1")
    elif n_fases == 2:
        pot_fase = potencia / 2.0
        for fase in fases:
            dss.Text.Command(f"New Generator.PV_fase{fase} Bus1={barra}.{fase} Phases=1 kV=2.4 kW={pot_fase} kvar=0.0 Model=1")
    elif n_fases == 1:
        dss.Text.Command(f"New Generator.PV_fase{fases[0]} Bus1={barra}.{fases[0]} Phases=1 kV=2.4 kW={potencia} kvar=0.0 Model=1")

def ejecutar_simulacion(barra, fase, potencia_kW):
    dss.Text.Command("clear")
    dss.Text.Command("redirect IEEE13Nodeckt.dss")
    dss.Text.Command("solve")
    
    # Caso base (sin GD)
    voltajes_sin_gd = obtener_voltajes_por_fase()
    perdidas_sin_gd = obtener_perdidas()
    
    # Caso con GD
    if potencia_kW > 0:
        agregar_generacion_distribuida(barra, potencia_kW)
        dss.Text.Command("solve")
    voltajes_con_gd = obtener_voltajes_por_fase()
    perdidas_con_gd = obtener_perdidas()
    
    # Resultados estructurados
    resultados = {
        "config": {"barra": barra, "fase": fase, "potencia_kW": potencia_kW},
        "voltajes": [],
        "perdidas": {"sin_gd": perdidas_sin_gd, "con_gd": perdidas_con_gd},
        "violaciones": []
    }
    
    for barra_name in voltajes_sin_gd.keys():
        v_sin = voltajes_sin_gd[barra_name].get(fase, 0)
        v_con = voltajes_con_gd[barra_name].get(fase, 0)
        resultados["voltajes"].append({
            "barra": barra_name,
            "voltaje_sin_gd": v_sin,
            "voltaje_con_gd": v_con
        })
        if v_con != 0 and (v_con < 0.95 or v_con > 1.05):
            resultados["violaciones"].append({"barra": barra_name, "voltaje": v_con})
    
    return resultados

if __name__ == "__main__":
    # Recibir parámetros desde Power BI (ejemplo: barra="634", fase=1, potencia_kW=50)
    params = json.loads(sys.argv[1])
    barra = params["barra"]
    fase = params["fase"]
    potencia_kW = params["potencia_kW"]
    
    # Ejecutar simulación
    resultados = ejecutar_simulacion(barra, fase, potencia_kW)
    
    # Convertir a DataFrame para Power BI
    df_voltajes = pd.DataFrame(resultados["voltajes"])
    df_perdidas = pd.DataFrame([resultados["perdidas"]])
    df_violaciones = pd.DataFrame(resultados["violaciones"])
    
    # Guardar resultados en un archivo temporal (opcional)
    with pd.ExcelWriter("resultados_temp.xlsx") as writer:
        df_voltajes.to_excel(writer, sheet_name="Voltajes", index=False)
        df_perdidas.to_excel(writer, sheet_name="Pérdidas", index=False)
        df_violaciones.to_excel(writer, sheet_name="Violaciones", index=False)
    
    # Imprimir resultados (Power BI leerá esta salida)
    print(json.dumps({
        "voltajes": df_voltajes.to_dict(orient="records"),
        "perdidas": df_perdidas.to_dict(orient="records")[0],
        "violaciones": df_violaciones.to_dict(orient="records")
    }))
