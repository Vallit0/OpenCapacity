import opendssdirect as dss
import pandas as pd
from tabulate import tabulate  # Importar tabulate para mostrar la tabla

# Cargar el circuito
dss.Text.Command("redirect IEEE13Nodeckt.dss")

# Resolver el circuito
dss.Text.Command("solve")

# Obtener nombres de nodos (barras y fases)
nodos = dss.Circuit.AllNodeNames()

# Obtener voltajes en PU para todos los nodos
voltajes_pu = dss.Circuit.AllBusMagPu()

# Crear un diccionario para almacenar los voltajes por barra
voltajes_por_barra = {}

# Procesar los nodos y voltajes
for nodo, voltaje in zip(nodos, voltajes_pu):
    # Extraer el nombre de la barra (eliminar la fase)
    barra = nodo.split('.')[0]

    # Opción 1: Calcular el promedio por barra
    if barra not in voltajes_por_barra:
        voltajes_por_barra[barra] = []
    voltajes_por_barra[barra].append(voltaje)

    # Opción 2: Seleccionar solo la fase 1 (comenta la opción 1 si usas esta)
    #if nodo.endswith('.1'):  # Solo fase 1
     #    voltajes_por_barra[barra] = voltaje

# Calcular el promedio por barra (si usaste la opción 1)
for barra in voltajes_por_barra:
    voltajes_por_barra[barra] = sum(voltajes_por_barra[barra]) / len(voltajes_por_barra[barra])

# Crear un DataFrame con los resultados
df = pd.DataFrame({
    "Barra": voltajes_por_barra.keys(),
    "Voltaje (PU)": voltajes_por_barra.values()
})

# Redondear los voltajes a 4 cifras decimales
df["Voltaje (PU)"] = df["Voltaje (PU)"].round(4)

# Exportar a CSV
df.to_csv("voltajes_por_barra.csv", index=False)
print("Resultados exportados a 'voltajes_por_barra.csv'")

# Mostrar la tabla en la consola
print("\nTabla de Voltajes por Barra:")
print(tabulate(df, headers="keys", tablefmt="pretty", showindex=False))
