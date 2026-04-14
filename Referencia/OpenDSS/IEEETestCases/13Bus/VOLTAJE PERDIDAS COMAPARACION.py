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
        voltajes = dss.Bus.PuVoltage()  # Voltajes en pares (real, imaginario)
        fases_disponibles = dss.Bus.Nodes()  # Obtiene las fases reales de la barra
        
        voltajes_fase = {1: None, 2: None, 3: None}  # Inicializa las 3 fases como None

        for i, fase in enumerate(fases_disponibles):
            V_real = voltajes[2 * i]
            V_imag = voltajes[2 * i + 1]
            V_pu = (V_real**2 + V_imag**2) ** 0.5  # Magnitud del voltaje en PU
            voltajes_fase[fase] = V_pu if V_pu > 1e-3 else 0.0  # Evitar valores cercanos a 0
        
        voltajes_por_fase[barra] = voltajes_fase

    return voltajes_por_fase

# Función para obtener pérdidas por fase en cada barra
def obtener_perdidas_por_fase():
    perdidas_por_fase = {}

    # Obtener todos los elementos de línea en el sistema
    dss.Lines.First()
    while True:
        barra_origen = dss.Lines.Bus1().split('.')[0]  # Obtener nombre de la barra de origen
        barra_destino = dss.Lines.Bus2().split('.')[0]  # Obtener nombre de la barra de destino
        perdidas = dss.CktElement.Losses()  # Devuelve pérdidas en W y VARs
        P_perdida_total = perdidas[0] / 1000  # Convertir a kW

        # Distribuir pérdidas en cada fase
        fases_disponibles = dss.CktElement.NumPhases()
        P_perdida_fase = {1: 0.0, 2: 0.0, 3: 0.0}

        if fases_disponibles > 0:
            P_fase = P_perdida_total / fases_disponibles  # Dividir entre las fases activas
            for i in range(1, fases_disponibles + 1):
                P_perdida_fase[i] = round(P_fase, 4)

        # Guardar pérdidas por barra
        perdidas_por_fase[barra_origen] = P_perdida_fase
        perdidas_por_fase[barra_destino] = P_perdida_fase

        if not dss.Lines.Next():
            break

    return perdidas_por_fase

# Función principal
def ejecutar():
    barras_disponibles = obtener_barras()

    while True:
        # Pedir barra válida
        while True:
            barra = input("\nIngrese la barra donde se instalará la GD: ")
            if barra in barras_disponibles:
                break
            else:
                print("⚠️ Barra no existe, ingrese nuevamente.")

        # Pedir potencia de la GD (permitir 0 para ver caso base)
        while True:
            try:
                potencia = float(input("Ingrese la potencia de la GD en kW (0 para caso base): "))
                if potencia >= 0:
                    break
                else:
                    print("⚠️ La potencia no puede ser negativa.")
            except ValueError:
                print("⚠️ Entrada inválida, ingrese un número.")

        # --- Obtener voltajes y pérdidas sin GD ---
        dss.Text.Command("clear")
        dss.Text.Command("redirect IEEE13Nodeckt.dss")
        dss.Text.Command("solve")
        voltajes_sin_gd = obtener_voltajes_por_fase()
        perdidas_sin_gd = obtener_perdidas_por_fase()

        # --- Agregar GD si la potencia es mayor a 0 ---
        if potencia > 0:
            dss.Text.Command(f"New Generator.PV Bus1={barra} Phases=3 kV=4.16 kW={potencia} kvar=0.0 Model=1")
            dss.Text.Command("solve")

        # --- Obtener voltajes y pérdidas con GD ---
        voltajes_con_gd = obtener_voltajes_por_fase()
        perdidas_con_gd = obtener_perdidas_por_fase()

        # --- Crear tabla de comparación de pérdidas ---
        datos_perdidas = []
        for barra in perdidas_sin_gd.keys():
            for fase in [1, 2, 3]:
                p_sin = perdidas_sin_gd[barra][fase] if barra in perdidas_sin_gd else "0"
                p_con = perdidas_con_gd[barra][fase] if barra in perdidas_con_gd else "0"
                datos_perdidas.append([barra, fase, p_sin, p_con])

        df_perdidas = pd.DataFrame(datos_perdidas, columns=["Barra", "Fase", "Pérdida sin GD (kW)", "Pérdida con GD (kW)"])

        # --- Calcular pérdidas totales ---
        perdida_total_sin_gd = sum(sum(perdidas_sin_gd[barra].values()) for barra in perdidas_sin_gd)
        perdida_total_con_gd = sum(sum(perdidas_con_gd[barra].values()) for barra in perdidas_con_gd)

        print("\n🔹 COMPARACIÓN DE PÉRDIDAS POR BARRA Y FASE")
        print(df_perdidas.to_string(index=False))

        print("\n🔹 PÉRDIDAS TOTALES DEL SISTEMA")
        print(f"🔻 Pérdidas sin GD: {perdida_total_sin_gd:.4f} kW")
        print(f"🔻 Pérdidas con GD: {perdida_total_con_gd:.4f} kW")

        # --- Preguntar si continuar ---
        continuar = input("\n¿Desea realizar otra consulta? (s/n): ").strip().lower()
        if continuar != 's':
            break

# Ejecutar el programa
if __name__ == "__main__":
    ejecutar()
