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

# Función principal
def ejecutar():
    barras_disponibles = obtener_barras()

    while True:
        # Elegir tipo de visualización
        print("\nOpciones de visualización:")
        print("1. Mostrar voltajes de una fase específica")
        print("2. Mostrar voltajes de todas las fases")
        print("3. Mostrar voltaje total por barra")
        
        while True:
            try:
                opcion = int(input("Seleccione una opción (1, 2 o 3): "))
                if opcion in [1, 2, 3]:
                    break
                else:
                    print("⚠️ Ingrese un número válido (1, 2 o 3).")
            except ValueError:
                print("⚠️ Entrada inválida, ingrese un número.")

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

        # --- Voltajes sin GD ---
        dss.Text.Command("clear")
        dss.Text.Command("redirect IEEE13Nodeckt.dss")
        dss.Text.Command("solve")
        voltajes_sin_gd = obtener_voltajes_por_fase()

        # --- Agregar GD si la potencia es mayor a 0 ---
        if potencia > 0:
            dss.Text.Command(f"New Generator.PV Bus1={barra} Phases=3 kV=4.16 kW={potencia} kvar=0.0 Model=1")
            dss.Text.Command("solve")

        voltajes_con_gd = obtener_voltajes_por_fase()

        # --- Crear tabla de comparación ---
        datos = []

        if opcion == 1:
            # Mostrar solo una fase específica
            while True:
                try:
                    fase = int(input("\nIngrese la fase a visualizar (1, 2 o 3): "))
                    if fase in [1, 2, 3]:
                        break
                    else:
                        print("⚠️ Ingrese un número válido (1, 2 o 3).")
                except ValueError:
                    print("⚠️ Entrada inválida, ingrese un número.")

            for barra in voltajes_sin_gd.keys():
                v_sin = voltajes_sin_gd[barra][fase] if voltajes_sin_gd[barra][fase] is not None else "--------"
                v_con = voltajes_con_gd[barra][fase] if voltajes_con_gd[barra][fase] is not None else "--------"
                datos.append([barra, v_sin, v_con])

            df = pd.DataFrame(datos, columns=["Barra", f"Voltaje sin GD Fase {fase} (PU)", f"Voltaje con GD Fase {fase} (PU)"])

        elif opcion == 2:
            # Mostrar todas las fases
            for barra in voltajes_sin_gd.keys():
                v_sin_1 = voltajes_sin_gd[barra][1] if voltajes_sin_gd[barra][1] is not None else "--------"
                v_sin_2 = voltajes_sin_gd[barra][2] if voltajes_sin_gd[barra][2] is not None else "--------"
                v_sin_3 = voltajes_sin_gd[barra][3] if voltajes_sin_gd[barra][3] is not None else "--------"

                v_con_1 = voltajes_con_gd[barra][1] if voltajes_con_gd[barra][1] is not None else "--------"
                v_con_2 = voltajes_con_gd[barra][2] if voltajes_con_gd[barra][2] is not None else "--------"
                v_con_3 = voltajes_con_gd[barra][3] if voltajes_con_gd[barra][3] is not None else "--------"

                datos.append([barra, v_sin_1, v_sin_2, v_sin_3, v_con_1, v_con_2, v_con_3])

            df = pd.DataFrame(datos, columns=["Barra", "Fase 1 sin GD", "Fase 2 sin GD", "Fase 3 sin GD",
                                              "Fase 1 con GD", "Fase 2 con GD", "Fase 3 con GD"])

        elif opcion == 3:
            # Mostrar voltaje total por barra (promedio de fases disponibles)
            for barra in voltajes_sin_gd.keys():
                fases_sin_gd = [v for v in voltajes_sin_gd[barra].values() if v is not None]
                fases_con_gd = [v for v in voltajes_con_gd[barra].values() if v is not None]

                v_sin_total = sum(fases_sin_gd) / len(fases_sin_gd) if fases_sin_gd else "--------"
                v_con_total = sum(fases_con_gd) / len(fases_con_gd) if fases_con_gd else "--------"

                datos.append([barra, v_sin_total, v_con_total])

            df = pd.DataFrame(datos, columns=["Barra", "Voltaje total sin GD (PU)", "Voltaje total con GD (PU)"])

        print("\n🔹 RESULTADOS DE VOLTAJES")
        print(df.to_string(index=False))

        # --- Preguntar si continuar ---
        continuar = input("\n¿Desea realizar otra consulta? (s/n): ").strip().lower()
        if continuar != 's':
            break

# Ejecutar el programa
if __name__ == "__main__":
    ejecutar()
