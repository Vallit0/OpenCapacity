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
    return round(P_perdidas_kW, 4)

# Función para agregar GD según el número de fases en la barra
def agregar_generacion_distribuida(barra, potencia):
    dss.Circuit.SetActiveBus(barra)
    fases = dss.Bus.Nodes()
    n_fases = len(fases)

    if n_fases == 3:
        print(f"\n✅ En la barra {barra} se introdujo una potencia trifásica de {potencia} kW")
        dss.Text.Command(f"New Generator.PV Bus1={barra} Phases=3 kV=4.16 kW={potencia} kvar=0.0 Model=1")
    elif n_fases == 2:
        pot_fase = potencia / 2.0
        print(f"\n✅ En la barra {barra} se introdujeron dos GD monofásicas de {pot_fase} kW cada una")
        for i, fase in enumerate(fases):
            dss.Text.Command(f"New Generator.PV_fase{fases[i]} Bus1={barra}.{fases[i]} Phases=1 kV=2.4 kW={pot_fase} kvar=0.0 Model=1")
    elif n_fases == 1:
        print(f"\n✅ En la barra {barra} se introdujo una GD monofásica de {potencia} kW en la fase {fases[0]}")
        dss.Text.Command(f"New Generator.PV_fase{fases[0]} Bus1={barra}.{fases[0]} Phases=1 kV=2.4 kW={potencia} kvar=0.0 Model=1")
    else:
        print("⚠️ No se puede determinar el número de fases de la barra.")

# Función principal
def ejecutar():
    barras_disponibles = obtener_barras()

    while True:
        while True:
            try:
                fase = int(input("\nIngrese la fase a visualizar (1, 2 o 3): "))
                if fase in [1, 2, 3]:
                    break
                else:
                    print("⚠️ Ingrese un número válido (1, 2 o 3).")
            except ValueError:
                print("⚠️ Entrada inválida, ingrese un número.")
        
        while True:
            barra = input("\nIngrese la barra donde se instalará la GD: ")
            if barra in barras_disponibles:
                break
            else:
                print("⚠️ Barra no existe, ingrese nuevamente.")
        
        while True:
            try:
                potencia = float(input("Ingrese la potencia de la GD en kW (0 para caso base): "))
                if potencia >= 0:
                    break
                else:
                    print("⚠️ La potencia no puede ser negativa.")
            except ValueError:
                print("⚠️ Entrada inválida, ingrese un número.")

        dss.Text.Command("clear")
        dss.Text.Command("redirect IEEE13Nodeckt.dss")
        dss.Text.Command("solve")
        voltajes_sin_gd = obtener_voltajes_por_fase()
        perdidas_sin_gd = obtener_perdidas()

        if potencia > 0:
            agregar_generacion_distribuida(barra, potencia)
            dss.Text.Command("solve")
        
        voltajes_con_gd = obtener_voltajes_por_fase()
        perdidas_con_gd = obtener_perdidas()

        datos = []
        violaciones = []
        for barra in voltajes_sin_gd.keys():
            v_sin = voltajes_sin_gd[barra][fase] if voltajes_sin_gd[barra][fase] is not None else "0"
            v_con = voltajes_con_gd[barra][fase] if voltajes_con_gd[barra][fase] is not None else "0"
            datos.append([barra, v_sin, v_con])
            
            if v_con != "0" and (float(v_con) < 0.95 or float(v_con) > 1.05):
                violaciones.append([barra, v_con])

        df = pd.DataFrame(datos, columns=["Barra", "Voltaje sin GD (PU)", "Voltaje con GD (PU)"])

        print(f"\n🔹 RESULTADOS DE VOLTAJES PARA LA FASE {fase}")
        print(df.to_string(index=False))
        print("\n🔹 PÉRDIDAS TOTALES DEL SISTEMA")
        print(f"🔻 Pérdidas sin GD: {perdidas_sin_gd} kW")
        print(f"🔻 Pérdidas con GD: {perdidas_con_gd} kW")

        if violaciones:
            df_violaciones = pd.DataFrame(violaciones, columns=["Barra", "Voltaje fuera de rango (PU)"])
            print("\n⚠️ TABLA DE VIOLACIONES DE VOLTAJE ⚠️")
            print(df_violaciones.to_string(index=False))

        continuar = input("\n¿Desea realizar otra consulta? (s/n): ").strip().lower()
        if continuar != 's':
            break

if __name__ == "__main__":
    ejecutar()
