import opendssdirect as dss
import pandas as pd
import matplotlib.pyplot as plt

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

# Función para graficar voltajes
def graficar_voltajes(barra, voltajes_sin_gd, voltajes_con_gd):
    fases = [1, 2, 3]
    voltajes_sin = [voltajes_sin_gd[barra].get(f, 0) for f in fases]
    voltajes_con = [voltajes_con_gd[barra].get(f, 0) for f in fases]

    x = range(len(fases))
    width = 0.35

    fig, ax = plt.subplots()
    ax.bar([p - width/2 for p in x], voltajes_sin, width, label='Sin GD', color='skyblue')
    ax.bar([p + width/2 for p in x], voltajes_con, width, label='Con GD', color='lightgreen')

    ax.set_xlabel('Fase')
    ax.set_ylabel('Voltaje (PU)')
    ax.set_title(f'Voltajes en barra {barra}')
    ax.set_xticks(x)
    ax.set_xticklabels([str(f) for f in fases])
    ax.legend()
    plt.ylim(0, max(voltajes_sin + voltajes_con) * 1.2)
    plt.show()

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

        tipo_gd = "Ninguna"

        if potencia > 0:
            dss.Circuit.SetActiveBus(barra)
            fases = dss.Bus.Nodes()

            if barra == "634":
                kv = 0.48
            else:
                kv = 4.16

            if len(fases) == 3:
                dss.Text.Command(f"New Generator.PV Bus1={barra} Phases=3 kV={kv} kW={potencia} kvar=0.0 Model=1")
                tipo_gd = f"trifásica de {potencia} kW"
            elif len(fases) == 2:
                pot_individual = potencia / 2
                dss.Text.Command(f"New Generator.PV1 Bus1={barra}.{fases[0]} Phases=1 kV={kv/1.732:.3f} kW={pot_individual} kvar=0.0 Model=1")
                dss.Text.Command(f"New Generator.PV2 Bus1={barra}.{fases[1]} Phases=1 kV={kv/1.732:.3f} kW={pot_individual} kvar=0.0 Model=1")
                tipo_gd = f"2 monofásicas de {pot_individual} kW cada una"
            elif len(fases) == 1:
                dss.Text.Command(f"New Generator.PV Bus1={barra}.{fases[0]} Phases=1 kV={kv/1.732:.3f} kW={potencia} kvar=0.0 Model=1")
                tipo_gd = f"monofásica de {potencia} kW"
            else:
                print("⚠️ No se pudo determinar el tipo de GD por las fases disponibles.")
                continue

            dss.Text.Command("solve")

        voltajes_con_gd = obtener_voltajes_por_fase()
        perdidas_con_gd = obtener_perdidas()

        print("\n=== Resultados ===")
        print(f"Tipo de GD instalada: {tipo_gd}")
        print(f"Pérdidas sin GD: {perdidas_sin_gd} kW")
        print(f"Pérdidas con GD: {perdidas_con_gd} kW")
        print("\nVoltajes en PU por fase en la barra seleccionada:")

        for fase_key, voltaje in voltajes_con_gd[barra].items():
            if fase_key == fase:
                print(f"Fase {fase_key}: {voltaje:.4f} PU")

        # ¡Aquí va la magia visual!
        graficar_voltajes(barra, voltajes_sin_gd, voltajes_con_gd)

        continuar = input("\n¿Desea realizar otra simulación? (s/n): ").lower()
        if continuar != 's':
            print("\n🌟 ¡Gracias por jugar con los electrones! 🌟\n")
            break

if __name__ == "__main__":
    ejecutar()
